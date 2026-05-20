"""
Demo-only schedule persistence.

Schedules are saved to data/schedules.json as plain JSON records.
No background execution happens — this is display-only for demo purposes.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta

_SCHEDULES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "schedules.json"
)


def _load() -> list[dict]:
    if not os.path.exists(_SCHEDULES_PATH):
        return []
    try:
        with open(_SCHEDULES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(schedules: list[dict]) -> None:
    os.makedirs(os.path.dirname(_SCHEDULES_PATH), exist_ok=True)
    with open(_SCHEDULES_PATH, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)


def _calc_next_run(preferred_time: str, frequency: str) -> str:
    """Calculate a display-only next-run datetime string."""
    now = datetime.now()
    try:
        hour, minute = [int(x) for x in preferred_time.split(":")]
    except Exception:
        hour, minute = 9, 0

    base = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if base <= now:
        base += timedelta(days=1)

    if frequency == "Daily":
        next_dt = base
    elif frequency == "Weekly":
        next_dt = base + timedelta(weeks=1)
    elif frequency == "Monthly":
        next_dt = base + timedelta(days=30)
    else:  # One-off
        next_dt = base

    return next_dt.strftime("%Y-%m-%d %H:%M")


def list_schedules() -> list[dict]:
    return _load()


def create_schedule(
    name: str,
    account_list: str,
    role: str,
    agents: list[str],
    frequency: str,
    preferred_time: str,
    lookback_days: int,
) -> dict:
    schedules = _load()
    record = {
        "id": str(uuid.uuid4()),
        "name": name,
        "account_list": account_list,
        "role": role,
        "agents": agents,
        "frequency": frequency,
        "preferred_time": preferred_time,
        "lookback_days": lookback_days,
        "status": "Active",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "last_run": "Demo only — not executed",
        "next_run": _calc_next_run(preferred_time, frequency),
    }
    schedules.append(record)
    _save(schedules)
    return record


def update_status(schedule_id: str, status: str) -> None:
    schedules = _load()
    for s in schedules:
        if s["id"] == schedule_id:
            s["status"] = status
            break
    _save(schedules)


def delete_schedule(schedule_id: str) -> None:
    schedules = [s for s in _load() if s["id"] != schedule_id]
    _save(schedules)
