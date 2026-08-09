from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx

from .models import ActionProposal, WorkItem, utcnow


@dataclass(frozen=True)
class VoiceIntent:
    kind: str
    project: str | None = None


def classify_voice_intent(transcript: str, projects: dict[str, str]) -> VoiceIntent:
    text = transcript.casefold().strip()
    project = next((name for name in projects if name.casefold() in text), None)
    if "create issue" in text or "open issue" in text:
        return VoiceIntent("create_issue", project)
    if any(phrase in text for phrase in ("what's next", "what is next", "next step")):
        return VoiceIntent("next", project)
    if "ci status" in text or "build status" in text:
        return VoiceIntent("ci_status", project)
    if "repository status" in text or "repo status" in text:
        return VoiceIntent("repo_status", project)
    return VoiceIntent("capture", project)


class ConfirmationService:
    """Single-use, device-bound confirmations for typed operations."""

    def __init__(self, ttl: int):
        self.ttl = ttl
        self.pending: dict[str, tuple[ActionProposal, str, Callable[[], Awaitable[str]]]] = {}
        self.used: dict[str, datetime] = {}

    def _prune(self) -> None:
        now = utcnow()
        self.used = {request_id: expires_at for request_id, expires_at in self.used.items() if expires_at > now}
        # Retain expired proposals for one TTL interval so their owners receive
        # an expiry response rather than an indistinguishable unknown-ID error.
        self.pending = {
            request_id: item
            for request_id, item in self.pending.items()
            if item[0].expires_at + timedelta(seconds=self.ttl) > now
        }

    def propose(self, action: str, target: str, device_id: str, operation: Callable[[], Awaitable[str]]) -> ActionProposal:
        self._prune()
        request_id = str(uuid4())
        proposal = ActionProposal(
            request_id=request_id,
            action=action,
            target=target,
            expires_at=utcnow() + timedelta(seconds=self.ttl),
        )
        self.pending[request_id] = (proposal, device_id, operation)
        return proposal

    async def confirm(self, request_id: str, device_id: str) -> str:
        self._prune()
        if request_id in self.used or request_id not in self.pending:
            raise KeyError(request_id)
        proposal, owner, operation = self.pending[request_id]
        if owner != device_id:
            raise PermissionError(request_id)
        self.pending.pop(request_id)
        self.used[request_id] = utcnow() + timedelta(seconds=self.ttl)
        if proposal.expires_at <= utcnow():
            raise TimeoutError(request_id)
        return await operation()

    def cancel(self, request_id: str, device_id: str) -> None:
        self._prune()
        if request_id in self.used or request_id not in self.pending:
            raise KeyError(request_id)
        _, owner, _ = self.pending[request_id]
        if owner != device_id:
            raise PermissionError(request_id)
        self.pending.pop(request_id)
        self.used[request_id] = utcnow() + timedelta(seconds=self.ttl)


class WorkItemService:
    def __init__(self, root: str, projects: dict[str, str], default_project: str):
        self.root = Path(root).resolve() if root else None
        self.projects = {name: Path(path).resolve() for name, path in projects.items()}
        self.default_project = default_project
        if self.root and not self.root.is_dir():
            raise ValueError("INKMATE_WORK_ITEM_ROOT must exist")
        if default_project not in self.projects:
            raise ValueError("INKMATE_DEFAULT_PROJECT must be configured in INKMATE_PROJECTS_JSON")

    def project_root(self, project: str | None) -> tuple[str, Path]:
        name = project or self.default_project
        root = self.projects.get(name)
        if root is None or not root.is_dir():
            raise KeyError(name)
        if self.root and not (root == self.root or self.root in root.parents):
            raise PermissionError("project is outside INKMATE_WORK_ITEM_ROOT")
        return name, root

    def create(self, *, transcript: str, summary: str, project: str | None, device_id: str) -> WorkItem:
        name, root = self.project_root(project)
        item_id = str(uuid4())
        title = self._title(transcript)
        next_steps = self._next_steps(summary)
        directory = (root / ".inkmate" / "captures").resolve()
        if root not in directory.parents:
            raise PermissionError("work-item path escaped project")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{utcnow():%Y-%m-%d}-{item_id}.md"
        body = self._markdown(item_id, name, title, transcript, summary, next_steps, device_id)
        path.write_text(body, encoding="utf-8")
        return WorkItem(
            id=item_id, project=name, title=title, summary=summary[:600],
            next_steps=next_steps, path=str(path.relative_to(root)),
        )

    def recent(self, project: str | None, limit: int = 5) -> list[WorkItem]:
        name, root = self.project_root(project)
        directory = root / ".inkmate" / "captures"
        paths = sorted(directory.glob("*.md"), reverse=True)[:limit] if directory.is_dir() else []
        return [self._read(path, name, root) for path in paths]

    def load(self, item_id: str) -> WorkItem:
        if not re.fullmatch(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", item_id):
            raise KeyError(item_id)
        for name, root in self.projects.items():
            directory = root / ".inkmate" / "captures"
            for path in directory.glob(f"*-{item_id}.md") if directory.is_dir() else []:
                resolved = path.resolve()
                if root in resolved.parents and resolved.is_file():
                    return self._read(resolved, name, root)
        raise KeyError(item_id)

    @staticmethod
    def _read(path: Path, project: str, root: Path) -> WorkItem:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        title = next((line[2:] for line in lines if line.startswith("# ")), path.stem)
        item_id = next((line.removeprefix("- ID: ") for line in lines if line.startswith("- ID: ")), path.stem[-36:])

        def section(name: str) -> list[str]:
            try:
                start = lines.index(f"## {name}") + 1
            except ValueError:
                return []
            end = next((index for index in range(start, len(lines)) if lines[index].startswith("## ")), len(lines))
            return [line for line in lines[start:end] if line]

        summary = " ".join(section("Summary"))[:600]
        next_steps = [line.removeprefix("- ")[:160] for line in section("Next steps") if line.startswith("- ")]
        issue_url = next((line.removeprefix("GitHub issue: ") for line in lines if line.startswith("GitHub issue: ")), None)
        return WorkItem(
            id=item_id, project=project, title=title[:120], summary=summary,
            next_steps=next_steps[:5], path=str(path.relative_to(root)), issue_url=issue_url,
        )

    def attach_issue(self, item: WorkItem, issue_url: str) -> None:
        _, root = self.project_root(item.project)
        path = (root / item.path).resolve()
        if root not in path.parents or not path.is_file():
            raise PermissionError("work-item path escaped project")
        path.write_text(path.read_text(encoding="utf-8") + f"\nGitHub issue: {issue_url}\n", encoding="utf-8")

    @staticmethod
    def _title(transcript: str) -> str:
        words = re.sub(r"\s+", " ", transcript).strip().split()
        return " ".join(words[:12]).rstrip(".,;:") or "Voice capture"

    @staticmethod
    def _next_steps(summary: str) -> list[str]:
        sentence = re.split(r"[.!?]", summary.strip())[0].strip()
        return [sentence[:160]] if sentence else []

    @staticmethod
    def _markdown(item_id: str, project: str, title: str, transcript: str, summary: str, next_steps: list[str], device_id: str) -> str:
        steps = "\n".join(f"- {step}" for step in next_steps) or "- Review capture"
        return (
            f"# {title}\n\n"
            f"- ID: {item_id}\n- Project: {project}\n- Captured: {utcnow().isoformat()}\n- Device: {device_id}\n\n"
            f"## Summary\n\n{summary}\n\n## Next steps\n\n{steps}\n\n## Transcript\n\n{transcript}\n"
        )


class GitHubIssueService:
    def __init__(self, token: str, api_url: str, repositories: dict[str, str], labels: dict[str, list[str]]):
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.repositories = repositories
        self.labels = labels

    async def create(self, item: WorkItem) -> str:
        repository = self.repositories.get(item.project)
        if not self.token or not repository:
            raise PermissionError("GitHub issue creation is not configured for this project")
        body = f"## Summary\n\n{item.summary}\n\n## Next steps\n\n" + "\n".join(f"- {step}" for step in item.next_steps)
        headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}"}
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{self.api_url}/repos/{repository}/issues",
                headers=headers,
                json={"title": item.title, "body": body, "labels": self.labels.get(item.project, [])},
            )
            response.raise_for_status()
        return response.json()["html_url"]
