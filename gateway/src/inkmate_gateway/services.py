import asyncio
import os
import subprocess
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import httpx

from .models import ActionProposal, Card, utcnow


class SpeechToText(Protocol):
    async def transcribe(self, audio: bytes, content_type: str) -> str: ...


class TextToSpeech(Protocol):
    async def synthesize(self, text: str) -> tuple[bytes, str] | None: ...


class ChatProvider(Protocol):
    async def query(self, text: str) -> str: ...
    async def health(self) -> dict: ...


class UnavailableSTT:
    async def transcribe(self, audio: bytes, content_type: str) -> str:
        raise RuntimeError("STT_UNAVAILABLE")


class SilentTTS:
    async def synthesize(self, text: str) -> tuple[bytes, str] | None:
        return None

class HttpTTS:
    """Adapter for a trusted-LAN Piper-compatible HTTP service."""

    def __init__(self, url: str):
        self.url = url

    async def synthesize(self, text: str) -> tuple[bytes, str] | None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.url, json={"text": text})
            response.raise_for_status()
        return response.content, response.headers.get("content-type", "audio/wav")

class FasterWhisperSTT:
    def __init__(self, model: str = "base"):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(model, device="cpu", compute_type="int8")

    async def transcribe(self, audio: bytes, content_type: str) -> str:
        import tempfile
        def run() -> str:
            suffix = ".wav" if "wav" in content_type else ".audio"
            with tempfile.NamedTemporaryFile(suffix=suffix) as f:
                f.write(audio); f.flush()
                segments, _ = self.model.transcribe(f.name)
                return " ".join(s.text.strip() for s in segments).strip()
        return await asyncio.to_thread(run)


class OllamaProvider:
    def __init__(self, base_url: str, model: str):
        self.base_url, self.model = base_url.rstrip("/"), model

    async def query(self, text: str) -> str:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(f"{self.base_url}/api/chat", json={"model": self.model, "stream": False, "messages": [{"role": "user", "content": text}]})
            response.raise_for_status()
            return response.json()["message"]["content"].strip()

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
            return {"status": "ok", "model": self.model}
        except Exception:
            return {"status": "unavailable", "model": self.model}


@dataclass(frozen=True)
class SafeCommand:
    argv: tuple[str, ...]
    description: str
    cwd: str | None = None


class ActionService:
    def __init__(self, commands: dict[str, SafeCommand] | None = None, ttl: int = 60):
        self.commands = commands or {}
        self.ttl = ttl
        self.pending: dict[str, tuple[ActionProposal, SafeCommand, str]] = {}
        self.used: set[str] = set()

    def propose(self, name: str, device_id: str, target: str = "local") -> ActionProposal:
        if name not in self.commands:
            raise KeyError(name)
        request_id = str(uuid4())
        cmd = self.commands[name]
        proposal = ActionProposal(request_id=request_id, action=name, target=target, expires_at=utcnow() + timedelta(seconds=self.ttl))
        self.pending[request_id] = (proposal, cmd, device_id)
        return proposal

    async def confirm(self, request_id: str, device_id: str) -> str:
        if request_id in self.used or request_id not in self.pending:
            raise KeyError(request_id)
        proposal, command, owner = self.pending[request_id]
        if owner != device_id:
            raise PermissionError(request_id)
        self.pending.pop(request_id)
        self.used.add(request_id)
        if proposal.expires_at <= utcnow():
            raise TimeoutError(request_id)
        proc = await asyncio.create_subprocess_exec(*command.argv, cwd=command.cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode:
            raise RuntimeError(f"command exited {proc.returncode}: {output.decode(errors='replace')[:1000]}")
        return output.decode(errors="replace")[:4000]

    def cancel(self, request_id: str, device_id: str) -> None:
        if request_id in self.used or request_id not in self.pending:
            raise KeyError(request_id)
        _, _, owner = self.pending[request_id]
        if owner != device_id:
            raise PermissionError(request_id)
        self.pending.pop(request_id); self.used.add(request_id)


class AudioStore:
    def __init__(self, ttl: int):
        self.ttl, self.items = ttl, {}

    def put(self, data: bytes, media_type: str) -> str:
        key = str(uuid4()); self.items[key] = (utcnow() + timedelta(seconds=self.ttl), data, media_type); return key

    def get(self, key: str) -> tuple[bytes, str]:
        item = self.items.get(key)
        if not item or item[0] <= utcnow():
            self.items.pop(key, None); raise KeyError(key)
        return item[1], item[2]


def host_health() -> dict:
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
    return {"status": "ok", "load_1m": load}


async def git_health(path: str) -> dict:
    root = Path(path).resolve()
    try:
        proc = await asyncio.create_subprocess_exec("git", "-C", str(root), "status", "--porcelain", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(proc.communicate(), 3)
        return {"status": "ok" if proc.returncode == 0 else "error", "dirty": bool(out)}
    except Exception:
        return {"status": "error"}


async def http_health(url: str, token: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(url, headers=headers)
        return {"status": "ok" if response.is_success else "error", "code": response.status_code}
    except Exception:
        return {"status": "unavailable"}


class CodingAgentAdapter:
    """Disabled-by-default foundation; never accepts shell strings."""
    def __init__(self, enabled: bool, workspaces: tuple[str, ...]):
        self.enabled, self.workspaces = enabled, tuple(str(Path(p).resolve()) for p in workspaces)

    def validate(self, workspace: str) -> Path:
        if not self.enabled:
            raise PermissionError("coding agents are disabled")
        path = Path(workspace).resolve()
        if not any(path == Path(root) or Path(root) in path.parents for root in self.workspaces):
            raise PermissionError("workspace is not allowlisted")
        return path
