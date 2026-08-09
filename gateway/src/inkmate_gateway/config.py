from __future__ import annotations

import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from .services import SafeCommand


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INKMATE_", env_file=".env", extra="ignore")

    # No implicit credential. Operators must explicitly enroll every device.
    device_secrets: str = ""
    max_clock_skew_seconds: int = 300
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    stt_backend: str = "unavailable"
    stt_model: str = "base"
    tts_url: str = ""
    audio_ttl_seconds: int = 300
    action_ttl_seconds: int = 60
    max_audio_bytes: int = 4 * 1024 * 1024
    safe_commands_json: str = "{}"
    action_phrases_json: str = "{}"
    workspace_allowlist: str = ""
    work_item_root: str = ""
    default_project: str = "inbox"
    projects_json: str = "{}"
    github_token: str = ""
    github_api_url: str = "https://api.github.com"
    github_repositories_json: str = "{}"
    github_labels_json: str = "{}"
    enable_coding_agents: bool = False

    @property
    def devices(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for item in self.device_secrets.split(","):
            device_id, separator, secret = item.strip().partition(":")
            if separator and device_id and secret:
                result[device_id] = secret
        return result

    @property
    def safe_commands(self) -> dict[str, SafeCommand]:
        data = json.loads(self.safe_commands_json)
        return {
            name: SafeCommand(tuple(value["argv"]), value["description"], value.get("cwd"))
            for name, value in data.items()
        }

    @property
    def action_phrases(self) -> dict[str, str]:
        return {key.casefold().strip(): value for key, value in json.loads(self.action_phrases_json).items()}

    @property
    def workspaces(self) -> tuple[str, ...]:
        return tuple(x.strip() for x in self.workspace_allowlist.split(",") if x.strip())
    @property
    def projects(self) -> dict[str, str]:
        data = json.loads(self.projects_json)
        if not isinstance(data, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in data.items()
        ):
            raise ValueError("INKMATE_PROJECTS_JSON must map project names to paths")
        return data

    @property
    def github_repositories(self) -> dict[str, str]:
        data = json.loads(self.github_repositories_json)
        if not isinstance(data, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in data.items()
        ):
            raise ValueError("INKMATE_GITHUB_REPOSITORIES_JSON must map projects to owner/repository")
        return data

    @property
    def github_labels(self) -> dict[str, list[str]]:
        data = json.loads(self.github_labels_json)
        if not isinstance(data, dict) or not all(
            isinstance(key, str) and isinstance(value, list)
            and all(isinstance(label, str) for label in value)
            for key, value in data.items()
        ):
            raise ValueError("INKMATE_GITHUB_LABELS_JSON must map projects to label lists")
        return data


@lru_cache
def get_settings() -> Settings:
    return Settings()
