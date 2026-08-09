import hashlib
import hmac
import json
import time

from httpx import ASGITransport, AsyncClient

from inkmate_gateway.app import create_app
from inkmate_gateway.config import Settings


class STT:
    async def transcribe(self, audio, content_type):
        return "capture plan for inbox"


class TTS:
    async def synthesize(self, text):
        return None


class Chat:
    async def query(self, text):
        return "Implement the reviewed change and run the gateway checks."

    async def health(self):
        return {"status": "ok", "model": "test"}


async def signed(client, method, path, content=b"", headers=None):
    timestamp = str(int(time.time()))
    digest = hashlib.sha256(content).hexdigest()
    signature = hmac.new(
        b"secret", f"{method}\n{path}\n{timestamp}\n{digest}".encode(), hashlib.sha256
    ).hexdigest()
    auth = {
        "X-InkMate-Device": "desk",
        "X-InkMate-Timestamp": timestamp,
        "X-InkMate-Signature": signature,
    }
    auth.update(headers or {})
    return await client.request(method, path, content=content, headers=auth)


async def test_capture_requires_confirmation_before_writing(tmp_path):
    settings = Settings(
        device_secrets="desk:secret",
        work_item_root=str(tmp_path),
        default_project="inbox",
        projects_json=json.dumps({"inbox": str(tmp_path)}),
    )
    app = create_app(settings, stt=STT(), tts=TTS(), chat=Chat())
    payload = json.dumps({"transcript": "Capture plan for inbox"}).encode()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        proposed = await signed(
            client, "POST", "/v1/captures", payload, {"Content-Type": "application/json"}
        )
        assert proposed.status_code == 200
        proposal = proposed.json()["pending_action"]
        assert not list(tmp_path.glob(".inkmate/captures/*.md"))

        confirmed = await signed(
            client, "POST", f"/v1/actions/{proposal['request_id']}/confirm"
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "executed"

        items = await signed(client, "GET", "/v1/work-items")
        assert items.status_code == 200
        assert items.json()[0]["project"] == "inbox"
        assert "Capture plan" in (tmp_path / confirmed.json()["output"]).read_text()
