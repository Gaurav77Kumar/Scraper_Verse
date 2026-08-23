"""The self-healing orchestrator: run → validate → heal → re-run → diff → notify."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .brightdata import BrightDataError, heal_collector, run_collector
from .config import Settings, Target
from .notify import format_changes, send_discord
from .store import connect, diff_rows, has_changes, latest_snapshot, record_healing, save_snapshot

log = logging.getLogger(__name__)


@dataclass
class TargetReport:
    target: str
    status: str  # "ok" | "healed" | "failed"
    row_count: int = 0
    diff: dict[str, Any] | None = None
    healing_events: list[str] = field(default_factory=list)
    error: str | None = None


def validate(rows: list[dict[str, Any]], min_rows: int) -> str | None:
    """Return a plain-language description of what broke, or None if healthy."""
    if not rows:
        return "Extraction returned zero rows where data was expected."
    if len(rows) < min_rows:
        return f"Extraction returned only {len(rows)} rows; expected at least {min_rows}."
    empty_fields = {
        k for row in rows[:5] for k, v in row.items() if v in (None, "", "N/A")
    }
    if len(empty_fields) >= 2:
        names = ", ".join(sorted(empty_fields))
        return f"Fields {names} came back empty — the page layout likely changed."
    return None


def process_target(target: Target, settings: Settings) -> TargetReport:
    report = TargetReport(target=target.name, status="failed")
    try:
        result = run_collector(target.name, target.collector_id, target.url)
    except BrightDataError as exc:
        report.error = str(exc)
        return report

    report.row_count = len(result.rows)
    issue = validate(result.rows, settings.min_rows_expected)

    if issue and settings.heal_on_failure:
        log.warning("[%s] broken: %s — healing", target.name, issue)
        try:
            heal_collector(target.collector_id, issue)
            rerun = run_collector(target.name, target.collector_id, target.url)
            report.row_count = len(rerun.rows)
            issue2 = validate(rerun.rows, settings.min_rows_expected)
            recovered = issue2 is None
            report.healing_events.append(f"Healed: {issue} → recovered={recovered}")
            report.status = "healed" if recovered else "failed"
            if not recovered:
                report.error = f"Still broken after heal: {issue2}"
                return report
            result = rerun
        except BrightDataError as exc:
            report.healing_events.append(f"Heal attempt failed: {exc}")
            report.error = str(exc)
            return report
    elif issue:
        report.error = issue
        return report
    else:
        report.status = "ok"

    with connect(settings.db_path) as conn:
        save_snapshot(conn, target.name, result.rows)
        prev = latest_snapshot_before(conn, target.name)
        if prev:
            diff = diff_rows(prev, result.rows)
            report.diff = diff
            if has_changes(diff):
                report.status = report.status or "ok"
        if report.healing_events:
            for event in report.healing_events:
                record_healing(conn, target.name, event, report.status != "failed")

    _notify(target, report, settings)
    return report


def latest_snapshot_before(conn: Any, target: str) -> list[dict[str, Any]] | None:
    """Snapshot from the previous run (excluding the one just inserted)."""
    cur = conn.execute(
        "SELECT payload FROM snapshots WHERE target = ? ORDER BY id DESC LIMIT 1 OFFSET 1",
        (target,),
    )
    row = cur.fetchone()
    return __import__("json").loads(row[0]) if row else None


def _notify(target: Target, report: TargetReport, settings: Settings) -> None:
    if not settings.discord_webhook_url:
        return
    if report.diff and has_changes(report.diff) or report.healing_events:
        try:
            send_discord(
                settings.discord_webhook_url,
                format_changes(target.name, report.diff or {}, report.healing_events),
            )
        except OSError as exc:
            log.error("Notification failed: %s", exc)


def run_pipeline(settings: Settings, targets: list[Target]) -> list[TargetReport]:
    return [process_target(t, settings) for t in targets]
