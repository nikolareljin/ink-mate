import pytest
import hashlib
import hmac
import time

from httpx import ASGITransport, AsyncClient

from inkmate_gateway.app import create_app
from inkmate_gateway.config import Settings
from inkmate_gateway.discovery import discovery_reply
from inkmate_gateway.services import ActionService, SafeCommand
from inkmate_gateway.services import AdapterHostClient


class STT:
    async def transcribe(self, audio, content_type): return "hello"
class TTS:
    async def synthesize(self, text): return b"voice", "audio/wav"
class Chat:
    async def query(self, text): return f"answer: {text}"
    async def health(self): return {"status": "ok", "model": "test"}


@pytest.fixture
def app():
    settings = Settings(device_secrets="desk:secret", max_audio_bytes=100)
    actions = ActionService({"echo": SafeCommand(("/bin/echo", "safe"), "Say safe")})
    return create_app(settings, stt=STT(), tts=TTS(), chat=Chat(), actions=actions)


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c: yield c
async def signed(client, method, path, content=b"", headers=None, *, device="desk", secret=b"secret"):
    timestamp = str(int(time.time()))
    body_hash = hashlib.sha256(content).hexdigest()
    canonical = f"{method}\n{path}\n{timestamp}\n{body_hash}".encode()
    signature = hmac.new(secret, canonical, hashlib.sha256).hexdigest()
    auth = {"X-InkMate-Device": device, "X-InkMate-Timestamp": timestamp,
            "X-InkMate-Signature": signature}
    auth.update(headers or {})
    return await client.request(method, path, content=content, headers=auth)



def test_default_settings_enroll_no_devices():
    settings = Settings(_env_file=None)
    assert settings.devices == {}


def test_adapter_host_client_refuses_non_loopback_url():
    assert not AdapterHostClient("http://192.0.2.20:8764", "x" * 32).configured


def test_discovery_reply_uses_selected_address_and_enrolled_secret():
    reply = discovery_reply(
        b"INKMATE/1 DISCOVER desk 0123456789abcdef0123456789abcdef",
        "192.0.2.20",
        {"desk": "secret"},
        8080,
        "192.0.2.10",
        now=1_700_000_000,
    )
    assert reply is not None
    fields = reply.decode().split()
    assert fields[:4] == ["INKMATE/1", "GATEWAY", "0123456789abcdef0123456789abcdef", "http://192.0.2.10:8080"]
    assert fields[4] == "1700000000"
    canonical = "DISCOVER\n0123456789abcdef0123456789abcdef\nhttp://192.0.2.10:8080\n1700000000"
    assert fields[5] == hmac.new(b"secret", canonical.encode(), hashlib.sha256).hexdigest()


def test_discovery_rejects_unknown_devices_and_bad_nonces():
    assert discovery_reply(b"INKMATE/1 DISCOVER unknown 0123456789abcdef0123456789abcdef", "192.0.2.20", {"desk": "secret"}, 8080) is None
    assert discovery_reply(b"INKMATE/1 DISCOVER desk not-a-nonce", "192.0.2.20", {"desk": "secret"}, 8080) is None


def test_discovery_rejects_device_outside_selected_network():
    request = b"INKMATE/1 DISCOVER desk 0123456789abcdef0123456789abcdef"
    assert discovery_reply(request, "192.0.3.20", {"desk": "secret"}, 8080, gateway_network="192.0.2.0/24") is None


async def test_auth_required(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/v1/devices/a/snapshot")).status_code == 401


async def test_interaction_and_short_lived_audio(client):
    response = await signed(client, "POST", "/v1/interactions", b"123", {"Content-Type": "audio/wav"})
    assert response.status_code == 200
    body = response.json(); assert body["transcript"] == "hello" and body["card"]["body"] == "answer: hello"
    audio = await signed(client, "GET", body["speech_url"])
    assert audio.content == b"voice" and audio.headers["cache-control"] == "private, no-store"


async def test_audio_size_limit(client):
    response = await signed(client, "POST", "/v1/interactions", b"x" * 101, {"Content-Type": "audio/wav"})
    assert response.status_code == 413


async def test_adapter_request_uses_typed_parameters_without_chat():
    class AdapterHost:
        async def operation(self, **kwargs):
            assert kwargs == {"device_id": "desk", "adapter_id": "workflow", "operation_id": "work.next"}
            return {"mode": "read", "input_schema": {"properties": {"project": {"type": "enum"}}}}
        async def invoke(self, **kwargs):
            assert kwargs == {"device_id": "desk", "adapter_id": "workflow", "operation_id": "work.next", "parameters": {"project": "inbox"}}
            return {"title": "Workflow", "body": "One task", "severity": "normal"}
    class AdapterSTT:
        async def transcribe(self, audio, content_type): return "adapter workflow work.next project=inbox"
    app = create_app(Settings(device_secrets="desk:secret"), stt=AdapterSTT(), tts=TTS(), chat=Chat(), adapter_host=AdapterHost())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as adapter_client:
        response = await signed(adapter_client, "POST", "/v1/interactions", b"123", {"Content-Type": "audio/wav"})
    assert response.status_code == 200
    assert response.json()["card"]["title"] == "Workflow"
    assert response.json()["card"]["body"] == "One task"


async def test_mutating_adapter_request_requires_confirmation():
    class AdapterHost:
        async def operation(self, **kwargs):
            return {"mode": "mutating", "input_schema": {"properties": {}}}
        async def invoke(self, **kwargs):
            return {"title": "Workflow", "body": "Changed", "severity": "normal"}
    class AdapterSTT:
        async def transcribe(self, audio, content_type): return "adapter workflow work.change"
    app = create_app(Settings(device_secrets="desk:secret"), stt=AdapterSTT(), tts=TTS(), chat=Chat(), adapter_host=AdapterHost())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as adapter_client:
        response = await signed(adapter_client, "POST", "/v1/interactions", b"123", {"Content-Type": "audio/wav"})
    assert response.status_code == 200
    assert response.json()["card"]["kind"] == "confirmation"


async def test_unavailable_adapter_returns_an_error_card():
    class AdapterHost:
        async def operation(self, **kwargs): raise RuntimeError("ADAPTER_HOST_UNAVAILABLE")
    class AdapterSTT:
        async def transcribe(self, audio, content_type): return "adapter workflow work.next"
    app = create_app(Settings(device_secrets="desk:secret"), stt=AdapterSTT(), tts=TTS(), chat=Chat(), adapter_host=AdapterHost())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as adapter_client:
        response = await signed(adapter_client, "POST", "/v1/interactions", b"123", {"Content-Type": "audio/wav"})
    assert response.status_code == 200
    assert response.json()["card"]["kind"] == "error"


async def test_snapshot(client):
    body = (await signed(client, "GET", "/v1/devices/desk/snapshot")).json()
    assert body["device_id"] == "desk" and body["gateway"]["ai_status"] == "ok"


async def test_action_confirm_is_single_use(client, app):
    proposal = app.state.actions.propose("echo", device_id="desk")
    response = await signed(client, "POST", f"/v1/actions/{proposal.request_id}/confirm")
    assert response.json()["output"] == "safe\n"
    assert (await signed(client, "POST", f"/v1/actions/{proposal.request_id}/confirm")).status_code == 404


async def test_action_cancel(client, app):
    proposal = app.state.actions.propose("echo", device_id="desk")
    assert (await signed(client, "POST", f"/v1/actions/{proposal.request_id}/cancel")).json()["status"] == "cancelled"
    assert (await signed(client, "POST", f"/v1/actions/{proposal.request_id}/confirm")).status_code == 404


async def test_action_confirmation_is_forbidden_to_another_device():
    settings = Settings(device_secrets="desk:secret,other:other-secret")
    actions = ActionService({"echo": SafeCommand(("/bin/echo", "safe"), "Say safe")})
    app = create_app(settings, stt=STT(), tts=TTS(), chat=Chat(), actions=actions)
    proposal = actions.propose("echo", device_id="desk")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        rejected = await signed(
            client, "POST", f"/v1/actions/{proposal.request_id}/confirm",
            device="other", secret=b"other-secret",
        )
        accepted = await signed(client, "POST", f"/v1/actions/{proposal.request_id}/confirm")
    assert rejected.status_code == 403
