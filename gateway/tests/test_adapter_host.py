import json
import sys
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from inkmate_gateway.adapter_host import (
    Invocation,
    Manifest,
    Operation,
    Parameter,
    InputSchema,
    Registration,
    Registry,
    application_definitions,
    create_adapter_host,
    ensure_browser_url,
    nikos_application_registrations,
    validate_parameters,
)


TOKEN = "x" * 32


def manifest(transport="cli"):
    return Manifest(
        schema_version="1", adapter_id="workflow", version="1.0.0", display_name="Workflow",
        transport=transport,
        operations=[Operation(
            operation_id="work.next", display_name="Next work", mode="read", timeout_seconds=5,
            job_allowed=False,
            input_schema=InputSchema(properties={"project": Parameter(type="enum", values=["inbox"])}, required=["project"]),
        )],
    )


def test_register_requires_local_http_endpoint(tmp_path):
    registry = Registry(tmp_path, TOKEN)
    with pytest.raises(ValueError):
        registry.register(Registration(manifest=manifest("http"), endpoint="http://192.0.2.1:8080"))


def test_nikos_adapters_are_discovered_and_require_approval(tmp_path):
    registry = Registry(tmp_path, TOKEN)
    adapter = next(item for item in registry.list() if item["adapter_id"] == "nikos-ubuntu-gedit")
    assert adapter["state"] == "discovered"
    assert registry.list("desk") == []
    registry.approve("nikos-ubuntu-gedit", adapter["fingerprint"])
    registry.grant("nikos-ubuntu-gedit", "desk")
    assert registry.list("desk")[0]["adapter_id"] == "nikos-ubuntu-gedit"


def test_nikos_application_catalog_is_json_with_platform_examples():
    definitions = application_definitions()
    assert definitions["nikos-ubuntu-gedit"]["command"] == ["gedit"]
    assert definitions["nikos-macos-textedit"]["command"] == ["open", "-a", "TextEdit"]
    assert definitions["nikos-windows-notepad"]["command"] == ["notepad.exe"]
    assert definitions["nikos-browser"]["command"] is None


def test_application_transport_is_reserved_for_the_builtin_adapter(tmp_path):
    registry = Registry(tmp_path, TOKEN)
    registration = nikos_application_registrations()[0]
    registration.manifest.adapter_id = "other-apps"
    with pytest.raises(ValueError): registry.register(registration)


def test_nikos_adapters_match_the_current_os(monkeypatch):
    monkeypatch.setattr("inkmate_gateway.adapter_host.sys.platform", "darwin")
    assert [registration.manifest.adapter_id for registration in nikos_application_registrations()] == [
        "nikos-macos-textedit", "nikos-macos-finder", "nikos-vscode", "nikos-browser",
    ]


def test_browser_url_refuses_non_web_schemes():
    assert ensure_browser_url("https://example.com/path") == "https://example.com/path"
    with pytest.raises(ValueError): ensure_browser_url("file:///etc/passwd")


def test_manifest_change_requires_new_approval(tmp_path):
    registry = Registry(tmp_path, TOKEN)
    first = registry.register(Registration(manifest=manifest(), argv=[sys.executable, "-c", "pass"]))
    registry.approve("workflow", first["fingerprint"])
    registry.grant("workflow", "desk")
    changed = manifest()
    changed.version = "1.0.1"
    second = registry.register(Registration(manifest=changed, argv=[sys.executable, "-c", "pass"]))
    assert second["state"] == "discovered"
    assert registry.list("desk") == []


def test_transport_change_requires_new_approval(tmp_path):
    registry = Registry(tmp_path, TOKEN)
    first = registry.register(Registration(manifest=manifest(), argv=[sys.executable, "-c", "pass"]))
    registry.approve("workflow", first["fingerprint"])
    registry.grant("workflow", "desk")
    changed = registry.register(Registration(manifest=manifest(), argv=[sys.executable, "-c", "print('changed')"]))
    assert changed["state"] == "discovered"
    assert registry.list("desk") == []
    registry.approve("workflow", changed["fingerprint"])
    assert registry.list("desk") == []


def test_parameter_validation_refuses_unknown_and_bad_enum():
    operation = manifest().operations[0]
    with pytest.raises(ValueError): validate_parameters(operation, {"unknown": "x"})
    with pytest.raises(ValueError): validate_parameters(operation, {"project": "other"})
    validate_parameters(operation, {"project": "inbox"})


def test_manifest_refuses_undeclared_required_parameter():
    with pytest.raises(ValueError):
        InputSchema(properties={}, required=["missing"])


def test_parameter_refuses_constraints_for_another_type():
    with pytest.raises(ValueError):
        Parameter(type="boolean", minimum=0)


async def test_cli_adapter_runs_only_after_approval_and_grant(tmp_path):
    registry = Registry(tmp_path, TOKEN)
    response = json.dumps({"status": "completed", "title": "Workflow", "body": "Ready"})
    registration = Registration(manifest=manifest(), argv=[sys.executable, "-c", f"import sys; sys.stdin.read(); print({response!r})"])
    record = registry.register(registration)
    invocation = Invocation(
        invocation_id="request-1", device_id="desk", adapter_id="workflow", operation_id="work.next",
        parameters={"project": "inbox"}, deadline=__import__("inkmate_gateway.adapter_host", fromlist=["now"]).now() + timedelta(seconds=5),
    )
    with pytest.raises(PermissionError): await registry.invoke(invocation)
    registry.approve("workflow", record["fingerprint"])
    registry.grant("workflow", "desk")
    result = await registry.invoke(invocation)
    assert result.body == "Ready"


async def test_browser_url_opens_only_after_approval_and_grant(tmp_path, monkeypatch):
    registry = Registry(tmp_path, TOKEN)
    adapter = next(item for item in registry.list() if item["adapter_id"] == "nikos-browser")
    registry.approve("nikos-browser", adapter["fingerprint"])
    registry.grant("nikos-browser", "desk")
    opened = []
    monkeypatch.setattr("inkmate_gateway.adapter_host.webbrowser.open_new_tab", lambda url: opened.append(url) or True)
    invocation = Invocation(
        invocation_id="request-1", device_id="desk", adapter_id="nikos-browser", operation_id="browser.open-url",
        parameters={"url": "https://example.com/path"}, deadline=__import__("inkmate_gateway.adapter_host", fromlist=["now"]).now() + timedelta(seconds=5),
    )
    result = await registry.invoke(invocation)
    assert result.status == "completed"
    assert opened == ["https://example.com/path"]


async def test_unavailable_application_is_not_reported_as_opened(tmp_path, monkeypatch):
    registry = Registry(tmp_path, TOKEN)
    adapter = next(item for item in registry.list() if item["adapter_id"] == "nikos-vscode")
    registry.approve("nikos-vscode", adapter["fingerprint"])
    registry.grant("nikos-vscode", "desk")
    monkeypatch.setattr("inkmate_gateway.adapter_host.shutil.which", lambda _: None)
    invocation = Invocation(
        invocation_id="request-1", device_id="desk", adapter_id="nikos-vscode", operation_id="app.open",
        parameters={}, deadline=__import__("inkmate_gateway.adapter_host", fromlist=["now"]).now() + timedelta(seconds=5),
    )
    with pytest.raises(RuntimeError, match="APPLICATION_UNAVAILABLE"):
        await registry.invoke(invocation)


async def test_cli_adapter_timeout_stops_invocation(tmp_path):
    timed_out = manifest()
    timed_out.operations[0].timeout_seconds = 1
    registry = Registry(tmp_path, TOKEN)
    record = registry.register(Registration(manifest=timed_out, argv=[sys.executable, "-c", "import time; time.sleep(5)"]))
    registry.approve("workflow", record["fingerprint"])
    registry.grant("workflow", "desk")
    invocation = Invocation(
        invocation_id="request-1", device_id="desk", adapter_id="workflow", operation_id="work.next",
        parameters={"project": "inbox"}, deadline=__import__("inkmate_gateway.adapter_host", fromlist=["now"]).now() + timedelta(seconds=5),
    )
    with pytest.raises(TimeoutError):
        await registry.invoke(invocation)


async def test_host_api_requires_authentication_for_adapter_inventory(tmp_path):
    app = create_adapter_host(state_dir=str(tmp_path), token=TOKEN)
    registration = Registration(manifest=manifest("http"), endpoint="http://127.0.0.1:9001")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        registered = await client.post("/v1/registrations", json=registration.model_dump(mode="json"))
        denied = await client.get("/v1/adapters")
        listed = await client.get("/v1/adapters", headers={"Authorization": f"Bearer {TOKEN}"})
    assert registered.status_code == 200
    assert denied.status_code == 401
    assert any(adapter["adapter_id"] == "workflow" and adapter["state"] == "discovered" for adapter in listed.json())
