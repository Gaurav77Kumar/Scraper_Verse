"""Thin wrapper around the Bright Data CLI (`bdata`) and DCA trigger API.

Every function here shells out to `npx -p @brightdata/cli bdata ...` so the
whole workflow stays in the terminal — no dashboard hopping.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


from typing import Any


def _find_npx() -> list[str]:
    """Windows: subprocess needs npx.cmd, not npx."""
    for name in ("npx.cmd", "npx.exe", "npx"):
        path = shutil.which(name)
        if path:
            return [path]
    return ["npx"]  # let it fail with a clear error downstream




_npx = _find_npx()
if os.name == "nt":
    # Windows quirk: spawn via cmd so npm resolves the package binary correctly
    BD_CLI = ["cmd", "/c", _npx[0], "-y", "-p", "@brightdata/cli", "bdata"]
else:
    BD_CLI = _npx + ["-y", "-p", "@brightdata/cli", "bdata"]

    
class BrightDataError(RuntimeError):
    """Raised when a bdata command fails or returns unusable output."""


@dataclass(frozen=True)
class RunResult:
    target_name: str
    collector_id: str
    rows: list[dict[str, Any]]
    raw: str


def _run(args: list[str], timeout: int = 600) -> str:
    try:
        proc = subprocess.run(
            BD_CLI + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:  # node/npx missing
        raise BrightDataError("Node.js/npx not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise BrightDataError(f"bdata {' '.join(args[:3])} timed out") from exc
    if proc.returncode != 0:
        raise BrightDataError(
            f"bdata {' '.join(args[:3])} failed "
            f"(exit {proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def run_collector(name: str, collector_id: str, url: str) -> RunResult:
    """Run a collector and parse its JSON output."""
    out = _run(["scraper", "run", collector_id, url])
    rows = _parse_rows(out)
    return RunResult(target_name=name, collector_id=collector_id, rows=rows, raw=out)


def heal_collector(collector_id: str, what_broke: str) -> None:
    """Ask Scraper Studio to repair the extraction from a plain-language description."""
    _run(["scraper", "heal", collector_id, what_broke], timeout=900)


def trigger_collector_api(collector_id: str, url: str, api_token: str) -> dict[str, Any]:
    """Trigger via POST /dca/trigger — proves the Collector ID is a production API."""
    import urllib.request

    req = urllib.request.Request(
        f"https://api.brightdata.com/dca/trigger?collector={collector_id}",
        data=json.dumps({"url": url}).encode(),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def _parse_rows(out: str) -> list[dict[str, Any]]:
    text = out.strip()
    if not text:
        return []
    start = text.find("[")
    end = text.rfind("]")
    candidate = text[start : end + 1] if start != -1 and end != -1 else text
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        for key in ("data", "result", "results", "items"):
            if key in parsed and isinstance(parsed[key], list):
                return parsed[key]
        return [parsed]
    return parsed if isinstance(parsed, list) else []
