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
    create_adapter_host,
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


async def test_host_api_requires_authentication_for_adapter_inventory(tmp_path):
    app = create_adapter_host(state_dir=str(tmp_path), token=TOKEN)
    registration = Registration(manifest=manifest("http"), endpoint="http://127.0.0.1:9001")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        registered = await client.post("/v1/registrations", json=registration.model_dump(mode="json"))
        denied = await client.get("/v1/adapters")
        listed = await client.get("/v1/adapters", headers={"Authorization": f"Bearer {TOKEN}"})
    assert registered.status_code == 200
    assert denied.status_code == 401
    assert listed.json()[0]["state"] == "discovered"
