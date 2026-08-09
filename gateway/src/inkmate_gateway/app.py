import hashlib
import hmac
import time

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response

from .developer import ConfirmationService, GitHubIssueService, WorkItemService, classify_voice_intent
from .config import Settings, get_settings
from .models import ActionResult, Card, ErrorDetail, InteractionResponse, Snapshot
from .services import ActionService, AudioStore, FasterWhisperSTT, HttpTTS, OllamaProvider, SilentTTS, UnavailableSTT, host_health
def _default_stt(cfg: Settings):
    return FasterWhisperSTT(cfg.stt_model) if cfg.stt_backend == "faster-whisper" else UnavailableSTT()


def _default_tts(cfg: Settings):
    return HttpTTS(cfg.tts_url) if cfg.tts_url else SilentTTS()



def create_app(settings: Settings | None = None, *, stt=None, tts=None, chat=None, actions=None, confirmations=None, work_items=None, github=None) -> FastAPI:
    cfg = settings or get_settings()
    app = FastAPI(title="InkMate Gateway", version="0.2.0")
    app.state.settings = cfg
    configured_work_items = work_items
    if configured_work_items is None and cfg.work_item_root and cfg.projects:
        configured_work_items = WorkItemService(cfg.work_item_root, cfg.projects, cfg.default_project)
    app.state.work_items = configured_work_items
    app.state.confirmations = confirmations or ConfirmationService(cfg.action_ttl_seconds)
    app.state.github = github or GitHubIssueService(
        cfg.github_token, cfg.github_api_url, cfg.github_repositories, cfg.github_labels
    )
    app.state.captured_items = {}
    app.state.stt = stt or _default_stt(cfg)
    app.state.tts = tts or _default_tts(cfg)
    app.state.chat = chat or OllamaProvider(cfg.ollama_url, cfg.ollama_model)
    app.state.actions = actions or ActionService(cfg.safe_commands, ttl=cfg.action_ttl_seconds)
    app.state.audio = AudioStore(cfg.audio_ttl_seconds)

    async def authenticate(
        request: Request,
        x_inkmate_device: str | None = Header(default=None),
        x_inkmate_timestamp: str | None = Header(default=None),
        x_inkmate_signature: str | None = Header(default=None),
    ) -> str:
        secret = cfg.devices.get(x_inkmate_device or "")
        try:
            timestamp = int(x_inkmate_timestamp or "")
        except ValueError:
            timestamp = 0
        if not secret or abs(int(time.time()) - timestamp) > cfg.max_clock_skew_seconds:
            raise HTTPException(401, "invalid device authentication")
        body_hash = hashlib.sha256(await request.body()).hexdigest()
        canonical = f"{request.method}\n{request.url.path}\n{timestamp}\n{body_hash}".encode()
        expected = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, x_inkmate_signature or ""):
            raise HTTPException(401, "invalid device authentication")
        return x_inkmate_device or ""

    @app.get("/healthz")
    async def healthz(): return {"status": "ok"}

    @app.post("/v1/interactions", response_model=InteractionResponse)
    async def interaction(
        request: Request,
        audio: bytes = Body(..., media_type="audio/wav"),
        device_id: str = Depends(authenticate),
    ):
        if not audio or len(audio) > cfg.max_audio_bytes:
            raise HTTPException(413, "audio is empty or too large")
        try:
            transcript = await app.state.stt.transcribe(audio, request.headers.get("content-type", "audio/wav"))
            answer = await app.state.chat.query(transcript)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        card = Card(kind="answer", title="InkMate", body=answer[:240], continuation=len(answer) > 240)
        speech = await app.state.tts.synthesize(answer)
        speech_url = None
        if speech:
            key = app.state.audio.put(*speech)
            speech_url = f"/v1/audio/{key}"
        return InteractionResponse(
            device_id=device_id,
            transcript=transcript,
            card=card,
            speech_url=speech_url,
        )

    @app.get("/v1/devices/{requested_device_id}/snapshot", response_model=Snapshot)
    async def snapshot(requested_device_id: str, device_id: str = Depends(authenticate)):
        if requested_device_id != device_id:
            raise HTTPException(403, "device identity mismatch")
        ai = await app.state.chat.health()
        host = host_health()
        gateway = {"status": host["status"], "load_1m": host["load_1m"], "ai_status": ai.get("status", "unknown"), "ai_model": ai.get("model")}
        card = Card(kind="home", title="InkMate", body=f"Gateway {gateway['status']} · AI {gateway['ai_status']}")
        return Snapshot(device_id=device_id, cards=[card], gateway=gateway)

    @app.post("/v1/actions/{request_id}/confirm", response_model=ActionResult)
    async def confirm(request_id: str, device_id: str = Depends(authenticate)):
        try:
            output = await app.state.actions.confirm(request_id, device_id=device_id)
        except KeyError:
            try:
                output = await app.state.confirmations.confirm(request_id, device_id)
            except KeyError as exc:
                raise HTTPException(404, "unknown or already used action") from exc
            except TimeoutError as exc:
                raise HTTPException(410, "action expired") from exc
            except PermissionError as exc:
                raise HTTPException(403, "action belongs to another device") from exc
        except TimeoutError as exc:
            raise HTTPException(410, "action expired") from exc
        except PermissionError as exc:
            raise HTTPException(403, "action belongs to another device") from exc
        except RuntimeError as exc:
            raise HTTPException(502, str(exc)) from exc
        return ActionResult(request_id=request_id, status="executed", output=output)

    @app.post("/v1/actions/{request_id}/cancel", response_model=ActionResult)
    async def cancel(request_id: str, device_id: str = Depends(authenticate)):
        try:
            app.state.actions.cancel(request_id, device_id=device_id)
        except KeyError:
            try:
                app.state.confirmations.cancel(request_id, device_id)
            except KeyError as exc:
                raise HTTPException(404, "unknown or already used action") from exc
            except PermissionError as exc:
                raise HTTPException(403, "action belongs to another device") from exc
        return ActionResult(request_id=request_id, status="cancelled")

    @app.post("/v1/captures", response_model=InteractionResponse)
    async def capture(
        payload: dict = Body(...),
        device_id: str = Depends(authenticate),
    ):
        if app.state.work_items is None:
            raise HTTPException(503, "WORK_ITEMS_UNAVAILABLE")
        transcript = str(payload.get("transcript", "")).strip()
        if not transcript or len(transcript) > 4096:
            raise HTTPException(422, "transcript is required and must be at most 4096 characters")
        project = payload.get("project")
        if project is not None and not isinstance(project, str):
            raise HTTPException(422, "project must be a string")
        try:
            intent = classify_voice_intent(transcript, cfg.projects)
            project = project or intent.project
            summary = (await app.state.chat.query(
                "Summarize this voice capture in one concise paragraph with the next action: " + transcript
            )).strip()[:600]
            name, _ = app.state.work_items.project_root(project)
        except KeyError as exc:
            raise HTTPException(422, "UNKNOWN_PROJECT") from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc

        async def save() -> str:
            item = app.state.work_items.create(
                transcript=transcript, summary=summary, project=name, device_id=device_id
            )
            app.state.captured_items[item.id] = item
            return item.path

        proposal = app.state.confirmations.propose(
            "save_capture", f"{name}: voice capture", device_id, save
        )
        return InteractionResponse(
            device_id=device_id,
            transcript=transcript,
            card=Card(
                kind="confirmation", title="Save capture",
                body=summary[:240], footer="Short press: save · Hold: cancel",
            ),
            pending_action=proposal,
        )

    @app.get("/v1/work-items")
    async def work_items(project: str | None = None, device_id: str = Depends(authenticate)):
        if app.state.work_items is None:
            raise HTTPException(503, "WORK_ITEMS_UNAVAILABLE")
        try:
            return app.state.work_items.recent(project)
        except KeyError as exc:
            raise HTTPException(422, "UNKNOWN_PROJECT") from exc

    @app.post("/v1/work-items/{item_id}/issue", response_model=InteractionResponse)
    async def propose_issue(item_id: str, device_id: str = Depends(authenticate)):
        item = app.state.captured_items.get(item_id)
        if item is None:
            try:
                item = app.state.work_items.load(item_id)
            except KeyError as exc:
                raise HTTPException(404, "unknown work item") from exc
        if item.issue_url:
            raise HTTPException(409, "work item already has a GitHub issue")
        repository = cfg.github_repositories.get(item.project)
        if not cfg.github_token or not repository:
            raise HTTPException(503, "GITHUB_ISSUES_UNAVAILABLE")

        async def create_issue() -> str:
            issue_url = await app.state.github.create(item)
            app.state.work_items.attach_issue(item, issue_url)
            app.state.captured_items[item.id] = item.model_copy(update={"issue_url": issue_url})
            return issue_url

        proposal = app.state.confirmations.propose(
            "create_github_issue", repository, device_id, create_issue
        )
        return InteractionResponse(
            device_id=device_id,
            transcript="",
            card=Card(
                kind="confirmation", title="Create GitHub issue",
                body=item.title[:240], footer="Short press: create · Hold: cancel",
            ),
            pending_action=proposal,
        )



    @app.get("/v1/audio/{response_id}")
    async def audio(response_id: str, _device_id: str = Depends(authenticate)):
        try: data, media_type = app.state.audio.get(response_id)
        except KeyError as exc: raise HTTPException(404, "audio unavailable") from exc
        return Response(data, media_type=media_type, headers={"Cache-Control": "private, no-store"})
    return app


app = create_app()
