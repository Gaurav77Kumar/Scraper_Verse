"""Configuration loading for the Scrape-Verse pipeline."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
TARGETS_PATH = ROOT / "config" / "targets.json"


@dataclass(frozen=True)
class Target:
    """A single site we monitor, mapped to its Bright Data Collector ID."""

    name: str
    url: str
    collector_id: str
    description: str = ""
    # Plain-language field descriptions used when healing a broken scraper.
    fields: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Settings:
    brightdata_api_token: str | None
    discord_webhook_url: str | None
    db_path: Path
    min_rows_expected: int
    heal_on_failure: bool


def load_targets(path: Path = TARGETS_PATH) -> list[Target]:
    raw: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return [Target(**item) for item in raw]


def load_settings() -> Settings:
    return Settings(
        brightdata_api_token=os.getenv("BRIGHTDATA_API_TOKEN"),
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
        db_path=Path(os.getenv("DB_PATH", str(ROOT / "data" / "intel.db"))),
        min_rows_expected=int(os.getenv("MIN_ROWS_EXPECTED", "3")),
        heal_on_failure=os.getenv("HEAL_ON_FAILURE", "true").lower() == "true",
    )
