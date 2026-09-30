"""Local adapter host. It never listens beyond loopback."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator


def now() -> datetime:
    return datetime.now(timezone.utc)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Parameter(Model):
    type: Literal["string", "integer", "number", "boolean", "enum", "string_array"]
    min_length: int | None = Field(default=None, ge=0, le=4096)
    max_length: int | None = Field(default=None, ge=1, le=4096)
    minimum: float | None = None
    maximum: float | None = None
    values: list[str] | None = Field(default=None, min_length=1, max_length=64)
    max_items: int | None = Field(default=None, ge=1, le=64)

    @model_validator(mode="after")
    def validate_constraints(self):
        if self.type == "enum" and not self.values:
            raise ValueError("enum parameters require values")
        if self.type != "enum" and self.values is not None:
            raise ValueError("only enum parameters may define values")
        if self.type not in {"string", "enum"} and (self.min_length is not None or self.max_length is not None):
            raise ValueError("length constraints require string or enum parameters")
        if self.type not in {"integer", "number"} and (self.minimum is not None or self.maximum is not None):
            raise ValueError("numeric constraints require integer or number parameters")
        if self.type != "string_array" and self.max_items is not None:
            raise ValueError("max_items requires a string_array parameter")
        if self.min_length is not None and self.max_length is not None and self.min_length > self.max_length:
            raise ValueError("min_length cannot exceed max_length")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")
        return self


class InputSchema(Model):
    properties: dict[str, Parameter] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def required_parameters_must_exist(self):
        if len(set(self.required)) != len(self.required) or not set(self.required).issubset(self.properties):
            raise ValueError("required parameters must be unique declared properties")
        return self


class Operation(Model):
    operation_id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
    display_name: str = Field(min_length=1, max_length=64)
    mode: Literal["read", "mutating"]
    timeout_seconds: int = Field(ge=1, le=30)
    job_allowed: bool
    input_schema: InputSchema


class Manifest(Model):
    schema_version: Literal["1"]
    adapter_id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
    version: str = Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
    display_name: str = Field(min_length=1, max_length=64)
    aliases: list[str] = Field(default_factory=list, max_length=8)
    transport: Literal["http", "cli", "application"]
    operations: list[Operation] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def operation_ids_must_be_unique(self):
        ids = [operation.operation_id for operation in self.operations]
        if len(set(ids)) != len(ids):
            raise ValueError("operation IDs must be unique")
        return self


class Registration(Model):
    manifest: Manifest
    endpoint: str | None = None
    argv: list[str] | None = Field(default=None, max_length=16)
    cwd: str | None = None


class Invocation(Model):
    invocation_id: str = Field(min_length=1, max_length=128)
    device_id: str = Field(pattern=r"^[a-zA-Z0-9._-]{1,64}$")
    adapter_id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
    operation_id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
    parameters: dict[str, Any] = Field(default_factory=dict)
    deadline: datetime


class AdapterResult(Model):
    status: Literal["completed", "accepted", "rejected", "failed"]
    title: str = Field(min_length=1, max_length=32)
    body: str = Field(default="", max_length=240)
    severity: Literal["normal", "notice", "warning", "critical"] = "normal"
    job_id: str | None = None


def canonical_registration(registration: Registration) -> str:
    return json.dumps(registration.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def fingerprint(registration: Registration) -> str:
    return hashlib.sha256(canonical_registration(registration).encode()).hexdigest()


def ensure_local_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("adapter endpoint must be an HTTP loopback URL")
    return value.rstrip("/")


def validate_registration(registration: Registration) -> None:
    if registration.manifest.transport == "http":
        if not registration.endpoint or registration.argv:
            raise ValueError("HTTP adapters require endpoint and forbid argv")
        ensure_local_url(registration.endpoint)
    elif registration.manifest.transport == "cli":
        if registration.endpoint or not registration.argv:
            raise ValueError("CLI adapters require argv and forbid endpoint")
        if not os.path.isabs(registration.argv[0]):
            raise ValueError("CLI executable must be an absolute path")
        if not os.path.isfile(registration.argv[0]):
            raise ValueError("CLI executable must exist")
        if registration.cwd and not os.path.isabs(registration.cwd):
            raise ValueError("CLI cwd must be an absolute path")
    else:
        if registration.manifest.adapter_id not in application_definitions():
            raise ValueError("application transport is reserved for NikOS application adapters")
        if registration.endpoint or registration.argv or registration.cwd:
            raise ValueError("application adapters forbid endpoint, argv, and cwd")


def application_definitions() -> dict[str, dict[str, Any]]:
    """Load the fixed NikOS adapter catalog from its packaged JSON definition."""
    source = Path(__file__).with_name("nikos_applications.json")
    data = json.loads(source.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1" or not isinstance(data.get("applications"), list):
        raise ValueError("invalid NikOS application adapter catalog")
    definitions = {item["adapter_id"]: item for item in data["applications"]}
    if len(definitions) != len(data["applications"]):
        raise ValueError("NikOS application adapter IDs must be unique")
    for adapter_id, item in definitions.items():
        if not isinstance(item.get("display_name"), str) or not isinstance(item.get("platforms"), list):
            raise ValueError(f"invalid NikOS application adapter: {adapter_id}")
        command = item.get("command")
        if command is not None and (not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command)):
            raise ValueError(f"invalid NikOS application command: {adapter_id}")
    return definitions


def current_platform() -> str:
    return "win" if sys.platform.startswith("win") else sys.platform


def spoken_application_requests() -> dict[str, str]:
    return {
        alias: adapter_id
        for adapter_id, item in application_definitions().items()
        if current_platform() in item["platforms"]
        for alias in item.get("aliases", [])
    }


def application_command(adapter_id: str) -> tuple[str, ...] | None:
    definition = application_definitions()[adapter_id]
    command = definition.get("macos_command") if sys.platform == "darwin" else definition.get("command")
    return tuple(command) if command is not None else None


def nikos_application_registrations() -> list[Registration]:
    """Return fixed NikOS application adapters for the current operating system."""
    platform = current_platform()
    definitions = application_definitions()
    adapter_ids = [adapter_id for adapter_id, item in definitions.items() if platform in item["platforms"]]
    return [Registration(
        manifest=Manifest(
            schema_version="1", adapter_id=adapter_id, version="1.0.0", display_name=definitions[adapter_id]["display_name"],
            transport="application", operations=browser_operations() if adapter_id == "nikos-browser" else [Operation(
                operation_id="app.open", display_name=f"Open {definitions[adapter_id]['display_name']}", mode="mutating",
                timeout_seconds=5, job_allowed=False, input_schema=InputSchema(),
            )],
        ),
    ) for adapter_id in adapter_ids]


def browser_operations() -> list[Operation]:
    return [
        Operation(operation_id="browser.open", display_name="Open default browser", mode="mutating",
                  timeout_seconds=5, job_allowed=False, input_schema=InputSchema()),
        Operation(operation_id="browser.open-url", display_name="Open browser URL", mode="mutating",
                  timeout_seconds=5, job_allowed=False,
                  input_schema=InputSchema(properties={"url": Parameter(type="string", min_length=1, max_length=2048)}, required=["url"])),
    ]


async def launch_application(adapter_id: str, url: str | None = None) -> AdapterResult:
    display_name, command = application_definitions()[adapter_id]["display_name"], application_command(adapter_id)
    if command is None:
        target = "about:blank" if url is None else ensure_browser_url(url)
        if not webbrowser.open_new_tab(target):
            raise RuntimeError("APPLICATION_UNAVAILABLE: browser")
    else:
        if not await application_available(command):
            raise RuntimeError(f"APPLICATION_UNAVAILABLE: {display_name}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *command, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL, start_new_session=True,
            )
        except OSError as exc:
            raise RuntimeError(f"APPLICATION_UNAVAILABLE: {display_name}") from exc
        if proc.returncode not in (None, 0):
            raise RuntimeError(f"APPLICATION_UNAVAILABLE: {display_name}")
    return AdapterResult(status="completed", title="Application opened", body=display_name)


async def application_available(command: tuple[str, ...]) -> bool:
    if not shutil.which(command[0]):
        return False
    if sys.platform != "darwin" or command[:2] != ("open", "-a"):
        return True
    probe = await asyncio.create_subprocess_exec(
        "open", "-Ra", command[2], stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        return await asyncio.wait_for(probe.wait(), timeout=5) == 0
    except asyncio.TimeoutError:
        probe.kill()
        await probe.wait()
        return False


def ensure_browser_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("browser URL must be an absolute HTTP or HTTPS URL")
    return value


def validate_parameters(operation: Operation, values: dict[str, Any]) -> None:
    schema = operation.input_schema
    unknown = set(values) - set(schema.properties)
    missing = set(schema.required) - set(values)
    if unknown or missing:
        raise ValueError("unknown or missing parameters")
    for name, definition in schema.properties.items():
        if name not in values:
            continue
        value = values[name]
        if definition.type in {"string", "enum"}:
            if not isinstance(value, str):
                raise ValueError(f"{name} must be a string")
            if definition.min_length is not None and len(value) < definition.min_length:
                raise ValueError(f"{name} is too short")
            if definition.max_length is not None and len(value) > definition.max_length:
                raise ValueError(f"{name} is too long")
            if definition.type == "enum" and value not in (definition.values or []):
                raise ValueError(f"{name} is not an allowed value")
        elif definition.type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be boolean")
        elif definition.type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{name} must be an integer")
        elif definition.type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{name} must be a number")
        else:
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"{name} must be a string array")
            if len(value) > (definition.max_items or 0):
                raise ValueError(f"{name} has too many values")
        if definition.minimum is not None and value < definition.minimum:
            raise ValueError(f"{name} is below minimum")
        if definition.maximum is not None and value > definition.maximum:
            raise ValueError(f"{name} is above maximum")


class Registry:
    def __init__(self, state_dir: Path, token: str):
        if len(token) < 32:
            raise ValueError("adapter host token must contain at least 32 characters")
        state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(state_dir, 0o700)
        self.token = token
        self.db = sqlite3.connect(state_dir / "adapters.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS adapters (
              adapter_id TEXT PRIMARY KEY, manifest TEXT NOT NULL, fingerprint TEXT NOT NULL,
              state TEXT NOT NULL, endpoint TEXT, argv TEXT, cwd TEXT, adapter_token TEXT
            );
            CREATE TABLE IF NOT EXISTS grants (adapter_id TEXT NOT NULL, device_id TEXT NOT NULL,
              PRIMARY KEY(adapter_id, device_id));
            CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, adapter_id TEXT NOT NULL,
              device_id TEXT NOT NULL, operation_id TEXT NOT NULL, state TEXT NOT NULL,
              created_at TEXT NOT NULL, result TEXT, expires_at TEXT NOT NULL);
            """
        )
        registrations = nikos_application_registrations()
        self._retire_missing_builtin_applications({registration.manifest.adapter_id for registration in registrations})
        for registration in registrations:
            self.register(registration, builtin=True)

    def _retire_missing_builtin_applications(self, adapter_ids: set[str]) -> None:
        """Disable removed built-ins so an old approved launcher cannot remain callable."""
        rows = self.db.execute("SELECT adapter_id,manifest FROM adapters").fetchall()
        retired = [
            row["adapter_id"] for row in rows
            if json.loads(row["manifest"]).get("transport") == "application"
            and row["adapter_id"] not in adapter_ids
        ]
        for adapter_id in retired:
            self.db.execute("DELETE FROM grants WHERE adapter_id=?", (adapter_id,))
            self.db.execute("UPDATE adapters SET state='disabled',adapter_token=NULL WHERE adapter_id=?", (adapter_id,))
        if retired:
            self.db.commit()

    def register(self, registration: Registration, *, builtin: bool = False) -> dict[str, str]:
        if registration.manifest.transport == "application" and not builtin:
            raise ValueError("application adapters are built in and cannot be registered over HTTP")
        validate_registration(registration)
        adapter_id = registration.manifest.adapter_id
        digest = fingerprint(registration)
        existing = self.db.execute("SELECT fingerprint FROM adapters WHERE adapter_id=?", (adapter_id,)).fetchone()
        changed = not existing or existing["fingerprint"] != digest
        state = "discovered" if changed else self.db.execute(
            "SELECT state FROM adapters WHERE adapter_id=?", (adapter_id,)
        ).fetchone()["state"]
        self.db.execute(
            "INSERT INTO adapters(adapter_id,manifest,fingerprint,state,endpoint,argv,cwd,adapter_token) VALUES(?,?,?,?,?,?,?,COALESCE((SELECT adapter_token FROM adapters WHERE adapter_id=?),NULL)) "
            "ON CONFLICT(adapter_id) DO UPDATE SET manifest=excluded.manifest,fingerprint=excluded.fingerprint,state=excluded.state,endpoint=excluded.endpoint,argv=excluded.argv,cwd=excluded.cwd",
             (adapter_id, json.dumps(registration.manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":")), digest, state, registration.endpoint,
             json.dumps(registration.argv) if registration.argv else None, registration.cwd, adapter_id),
        )
        if changed and existing:
            self.db.execute("DELETE FROM grants WHERE adapter_id=?", (adapter_id,))
            self.db.execute("UPDATE adapters SET adapter_token=NULL WHERE adapter_id=?", (adapter_id,))
        self.db.commit()
        return {"adapter_id": adapter_id, "state": state, "fingerprint": digest}

    def _row(self, adapter_id: str) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM adapters WHERE adapter_id=?", (adapter_id,)).fetchone()
        if row is None:
            raise KeyError(adapter_id)
        return row

    def approve(self, adapter_id: str, digest: str) -> str:
        row = self._row(adapter_id)
        if not secrets.compare_digest(row["fingerprint"], digest):
            raise ValueError("adapter fingerprint does not match")
        token = secrets.token_urlsafe(32)
        self.db.execute("UPDATE adapters SET state='approved', adapter_token=? WHERE adapter_id=?", (token, adapter_id))
        self.db.commit()
        return token

    def grant(self, adapter_id: str, device_id: str) -> None:
        self._row(adapter_id)
        self.db.execute("INSERT OR IGNORE INTO grants(adapter_id,device_id) VALUES(?,?)", (adapter_id, device_id))
        self.db.execute("UPDATE adapters SET state='active' WHERE adapter_id=? AND state='approved'", (adapter_id,))
        self.db.commit()

    def revoke(self, adapter_id: str, device_id: str) -> None:
        self._row(adapter_id)
        self.db.execute("DELETE FROM grants WHERE adapter_id=? AND device_id=?", (adapter_id, device_id))
        self.db.execute(
            "UPDATE adapters SET state='approved' WHERE adapter_id=? AND state='active' "
            "AND NOT EXISTS(SELECT 1 FROM grants WHERE adapter_id=?)",
            (adapter_id, adapter_id),
        )
        self.db.commit()

    def disable(self, adapter_id: str) -> None:
        self._row(adapter_id)
        self.db.execute("UPDATE adapters SET state='disabled' WHERE adapter_id=?", (adapter_id,))
        self.db.commit()

    def jobs(self, device_id: str | None = None) -> list[dict[str, Any]]:
        self.db.execute("DELETE FROM jobs WHERE expires_at <= ?", (now().isoformat(),))
        query = "SELECT job_id,adapter_id,device_id,operation_id,state,created_at,result FROM jobs"
        args: tuple[str, ...] = ()
        if device_id:
            query += " WHERE device_id=?"
            args = (device_id,)
        self.db.commit()
        return [dict(row) for row in self.db.execute(query, args).fetchall()]

    def list(self, device_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT a.adapter_id,a.manifest,a.fingerprint,a.state FROM adapters a"
        args: tuple[str, ...] = ()
        if device_id:
            query += " JOIN grants g ON g.adapter_id=a.adapter_id WHERE g.device_id=? AND a.state='active'"
            args = (device_id,)
        rows = self.db.execute(query, args).fetchall()
        return [{"adapter_id": row["adapter_id"], "manifest": json.loads(row["manifest"]), "fingerprint": row["fingerprint"], "state": row["state"]} for row in rows]

    async def invoke(self, invocation: Invocation) -> AdapterResult:
        row = self._row(invocation.adapter_id)
        granted = self.db.execute("SELECT 1 FROM grants WHERE adapter_id=? AND device_id=?", (invocation.adapter_id, invocation.device_id)).fetchone()
        if row["state"] != "active" or not granted:
            raise PermissionError("adapter is not active for this device")
        manifest = Manifest.model_validate_json(row["manifest"])
        operation = next((item for item in manifest.operations if item.operation_id == invocation.operation_id), None)
        if operation is None:
            raise KeyError("unknown adapter operation")
        validate_parameters(operation, invocation.parameters)
        if invocation.deadline <= now():
            raise TimeoutError("invocation deadline expired")
        payload = invocation.model_dump(mode="json")
        if manifest.transport == "http":
            async with httpx.AsyncClient(timeout=operation.timeout_seconds) as client:
                response = await client.post(f"{row['endpoint']}/v1/invoke", json=payload, headers={"Authorization": f"Bearer {row['adapter_token']}"})
                response.raise_for_status()
                result = AdapterResult.model_validate(response.json())
        elif manifest.transport == "cli":
            proc = await asyncio.create_subprocess_exec(*json.loads(row["argv"]), cwd=row["cwd"], stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=65_536)
            try:
                output, _ = await asyncio.wait_for(
                    proc.communicate(json.dumps(payload).encode()), timeout=operation.timeout_seconds
                )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                if proc.returncode is None:
                    proc.kill()
                    await proc.wait()
                raise
            if proc.returncode != 0:
                raise RuntimeError("CLI adapter failed")
            if len(output) > 65_536:
                raise RuntimeError("CLI adapter response is too large")
            result = AdapterResult.model_validate_json(output)
        else:
            result = await launch_application(invocation.adapter_id, invocation.parameters.get("url"))
        if result.status == "accepted":
            if not operation.job_allowed or not result.job_id:
                raise ValueError("adapter returned invalid job result")
            expires = now() + timedelta(days=7)
            self.db.execute("INSERT OR REPLACE INTO jobs(job_id,adapter_id,device_id,operation_id,state,created_at,result,expires_at) VALUES(?,?,?,?,?,?,?,?)", (result.job_id, invocation.adapter_id, invocation.device_id, invocation.operation_id, "accepted", now().isoformat(), result.model_dump_json(), expires.isoformat()))
            self.db.commit()
        return result


def create_adapter_host(*, state_dir: str, token: str) -> FastAPI:
    registry = Registry(Path(state_dir).expanduser(), token)
    app = FastAPI(title="InkMate local adapter host")
    app.state.registry = registry

    def admin(authorization: str | None = Header(default=None)) -> None:
        if not authorization or not authorization.startswith("Bearer ") or not secrets.compare_digest(authorization[7:], registry.token):
            raise HTTPException(401, "invalid adapter host authentication")

    @app.get("/healthz")
    async def healthz(): return {"status": "ok"}

    @app.post("/v1/registrations")
    async def register(registration: Registration):
        try: return registry.register(registration)
        except ValueError as exc: raise HTTPException(422, str(exc)) from exc

    @app.get("/v1/adapters")
    async def adapters(device_id: str | None = None, _admin: None = Depends(admin)):
        return registry.list(device_id)

    @app.post("/v1/adapters/{adapter_id}/approve")
    async def approve(adapter_id: str, fingerprint: str, _admin: None = Depends(admin)):
        try: return {"adapter_token": registry.approve(adapter_id, fingerprint)}
        except KeyError as exc: raise HTTPException(404, "unknown adapter") from exc
        except ValueError as exc: raise HTTPException(409, str(exc)) from exc

    @app.post("/v1/adapters/{adapter_id}/grants/{device_id}")
    async def grant(adapter_id: str, device_id: str, _admin: None = Depends(admin)):
        try: registry.grant(adapter_id, device_id)
        except KeyError as exc: raise HTTPException(404, "unknown adapter") from exc
        return {"status": "active"}

    @app.delete("/v1/adapters/{adapter_id}/grants/{device_id}")
    async def revoke(adapter_id: str, device_id: str, _admin: None = Depends(admin)):
        try: registry.revoke(adapter_id, device_id)
        except KeyError as exc: raise HTTPException(404, "unknown adapter") from exc
        return {"status": "revoked"}

    @app.post("/v1/adapters/{adapter_id}/disable")
    async def disable(adapter_id: str, _admin: None = Depends(admin)):
        try: registry.disable(adapter_id)
        except KeyError as exc: raise HTTPException(404, "unknown adapter") from exc
        return {"status": "disabled"}

    @app.get("/v1/jobs")
    async def jobs(device_id: str | None = None, _admin: None = Depends(admin)):
        return registry.jobs(device_id)

    @app.post("/v1/invocations")
    async def invoke(invocation: Invocation, _admin: None = Depends(admin)):
        try: return await registry.invoke(invocation)
        except KeyError as exc: raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except (ValueError, TimeoutError) as exc: raise HTTPException(422, str(exc)) from exc
        except (RuntimeError, httpx.HTTPError) as exc: raise HTTPException(502, "adapter unavailable") from exc

    return app


def main() -> None:
    import uvicorn
    token = os.environ.get("INKMATE_ADAPTER_HOST_TOKEN", "")
    state_dir = os.environ.get("INKMATE_ADAPTER_STATE_DIR", "~/.local/state/inkmate/adapters")
    port = int(os.environ.get("INKMATE_ADAPTER_HOST_PORT", "8764"))
    uvicorn.run(create_adapter_host(state_dir=state_dir, token=token), host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
