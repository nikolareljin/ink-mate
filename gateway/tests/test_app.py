import pytest
import hashlib
import hmac
import time

from httpx import ASGITransport, AsyncClient

from inkmate_gateway.app import create_app
from inkmate_gateway.config import Settings
from inkmate_gateway.services import ActionService, SafeCommand


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
