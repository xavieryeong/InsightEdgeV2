from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "results")
_PARTIAL_SUFFIX = "_INPROGRESS.json"


def _folder(role: str) -> str:
    subfolder = "ent" if "Territory" in role else "velocity"
    return os.path.join(_DATA_DIR, subfolder)


def _safe(name: str) -> str:
    return name.replace(" ", "_").replace("/", "_")


def _atomic_write_json(path: str, payload: dict) -> None:
    folder = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + ".", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def begin_run(role: str, source_filename: str) -> dict:
    """Open a new run for incremental writes.

    Returns a handle dict with ``folder``, ``partial_path``, ``final_path``,
    and base ``metadata``. The partial file is not created until the first
    ``save_checkpoint`` call.
    """
    folder = _folder(role)
    os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = _safe(source_filename)
    return {
        "folder": folder,
        "partial_path": os.path.join(folder, f"{timestamp}_{safe}{_PARTIAL_SUFFIX}"),
        "final_path": os.path.join(folder, f"{timestamp}_{safe}.json"),
        "metadata": {
            "source_filename": source_filename,
            "role": role,
            "date": datetime.now().isoformat(),
        },
    }


def save_checkpoint(handle: dict, results: list) -> None:
    """Atomically rewrite the in-progress file with the current results list."""
    payload = {
        "metadata": {
            **handle["metadata"],
            "company_count": len(results),
            "in_progress": True,
        },
        "results": results,
    }
    _atomic_write_json(handle["partial_path"], payload)


def finalize_run(handle: dict, results: list) -> str:
    """Write the final file and remove the in-progress one. Returns final path."""
    payload = {
        "metadata": {**handle["metadata"], "company_count": len(results)},
        "results": results,
    }
    _atomic_write_json(handle["final_path"], payload)
    if os.path.exists(handle["partial_path"]):
        try:
            os.remove(handle["partial_path"])
        except OSError:
            pass
    return handle["final_path"]


def load_partial_run(partial_path: str) -> tuple[list, dict]:
    """Read an in-progress run file. Returns ``(results, metadata)``."""
    with open(partial_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("results", []), data.get("metadata", {})


def find_partial_run(role: str, source_filename: str) -> str | None:
    """Return the newest in-progress run file matching this source, or None."""
    folder = _folder(role)
    if not os.path.exists(folder):
        return None
    safe = _safe(source_filename)
    suffix = f"_{safe}{_PARTIAL_SUFFIX}"
    candidates = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.endswith(suffix)
    ]
    return sorted(candidates, reverse=True)[0] if candidates else None


def save_run(results: list, role: str, source_filename: str) -> str:
    """Write a completed run in one shot (no checkpoint)."""
    handle = begin_run(role, source_filename)
    return finalize_run(handle, results)


def delete_run(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


def load_run(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_runs(role: str) -> list[dict]:
    folder = _folder(role)
    if not os.path.exists(folder):
        return []
    runs = []
    for filename in os.listdir(folder):
        if not filename.endswith(".json") or filename.endswith(_PARTIAL_SUFFIX):
            continue
        path = os.path.join(folder, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("metadata", {})
            raw_date = meta.get("date", "")
            display_date = raw_date[:16].replace("T", " ") if raw_date else "—"
            runs.append({
                "path": path,
                "source_filename": meta.get("source_filename", filename),
                "date": raw_date,
                "display_date": display_date,
                "company_count": meta.get("company_count", 0),
                "role": meta.get("role", ""),
            })
        except Exception:
            pass
    return sorted(runs, key=lambda x: x["date"], reverse=True)
