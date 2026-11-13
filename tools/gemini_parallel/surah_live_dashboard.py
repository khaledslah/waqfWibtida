#!/usr/bin/env python3
"""Generalized Live Surah Parallel-Runner & Telemetry Dashboard (auto-refreshing browser UI).

Features:
- Generalized for any Surah (`?surah=6`, `?surah=5`, `?surah=4`, `?surah=3`, etc.)
- 12-hour AM/PM time formatting everywhere (live clock, reset times, step timestamps)
- Displays all 5 accounts (default, qoun, abod, smallbusiness, quyn) with:
  - Dynamic Pro / 4 Argon High capability badge (detected from Chrome mode picker)
  - Plan Limit bucket explanation (2,400 = 5h reset vs 48,384 = weekly pool vs 12,096 = Free/Auto Pool)
  - Live Thinking/Pro remaining / plan limit credits & % of plan used
  - Rolling quota reset countdown & 12-hour reset timestamp (`Resets in Xh Ym (at HH:MM AM/PM)`)
- Surah Run Quota, Token & Cost Summary card + per-account breakdown
- Per-batch quota credits used, estimated tokens (new input, same-chat context, thinking, output), and estimated cost ($USD)
- Groups batches by the account that handled them (`qoun`, `abod`, `smallbusiness`, etc.) with a toggle for Ayah order
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

SCRATCH = Path(__file__).resolve().parent
if str(SCRATCH) not in sys.path:
    sys.path.insert(0, str(SCRATCH))

from surah_telemetry_ledger import (  # noqa: E402
    LEDGER_FILE,
    SURAH_NAMES_AR,
    build_all_surahs_ledger,
    explain_plan_limit,
    merge_quota_pools,
    fmt_12h,
    fmt_iso_to_12h,
)

PROTO = Path(r"D:\AI_Projects\waqfWibtida2\data\llm_prototype")
QUOTAS_LIVE_FILE = SCRATCH / "quotas_live.json"
TURNS_FILE = SCRATCH / "turns.jsonl"
EVENTS_FILE = SCRATCH / "timing_events.jsonl"
HOST = "127.0.0.1"
PORT = 8787


def _log_file_for(surah: int) -> Path:
    preferred = SCRATCH / f"surah{surah}_launch.log"
    if preferred.exists():
        return preferred
    # Backward-compat aliases used by earlier per-surah copies
    for alt in (SCRATCH / f"surah{surah}_parallel.log", SCRATCH / "surah6_launch.log"):
        if alt.exists() and surah in (6,) and alt.name.startswith("surah6"):
            return alt
    return preferred

ALL_PROFILES = ["default", "qoun", "abod", "smallbusiness", "quyn"]

_state_lock = threading.Lock()
_quota_state: dict[str, Any] = {
    "updatedAt": None,
    "updatedAt_12h": None,
    "lastRpcPollAt": None,
    "lastRpcPollAt_12h": None,
    "profiles": {},
    "source": "init",
    "error": None,
    "runnerAlive": False,
}
_ledger_cache: dict[str, Any] = {"mtime": 0.0, "data": {}}


def _read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _fmt_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return "—"
    s = max(0, int(round(seconds)))
    if s == 0:
        return "now"
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m:02d}m"
    if m > 0:
        return f"{m}m {sec:02d}s"
    return f"{sec}s"


def _pct(rem: int, denom: int) -> tuple[float, float]:
    if denom <= 0:
        return 0.0, 100.0
    left = round(100.0 * rem / denom, 1)
    used = round(100.0 * (denom - rem) / denom, 1)
    return used, left


def _check_runner_alive() -> bool:
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.Name -match 'python' -and $_.CommandLine -match 'surah.*_parallel_runner' } | "
                "Select-Object -First 1 -ExpandProperty ProcessId",
            ],
            text=True,
            timeout=6,
        )
        return bool(out.strip())
    except Exception:
        return False


def _merge_all_quota_sources(runner_alive: bool = False) -> dict[str, dict[str, Any]]:
    """Combine quotas_live.json with live reset countdown and 12-hour AM/PM formatting."""
    busy_profiles: set[str] = set()
    if runner_alive:
        for st_file in SCRATCH.glob("surah*_parallel_status.json"):
            st_data = _read_json(st_file)
            if isinstance(st_data, dict):
                bmap = st_data.get("batches") if isinstance(st_data.get("batches"), dict) else st_data
                for v in bmap.values():
                    if isinstance(v, dict) and v.get("stage") in ("step_a", "step_b") and v.get("profile"):
                        busy_profiles.add(str(v["profile"]))

    live_data = _read_json(QUOTAS_LIVE_FILE)
    live_profs = live_data.get("profiles") if isinstance(live_data, dict) else {}
    merged: dict[str, dict[str, Any]] = {}
    if isinstance(live_profs, dict):
        for p, d in live_profs.items():
            if not isinstance(d, dict):
                continue
            entry = dict(d)
            if entry.get("remaining") is not None and entry.get("limit"):
                u_pct, l_pct = _pct(int(entry["remaining"]), int(entry["limit"]))
                entry["used_pct"] = u_pct
                entry["left_pct"] = l_pct
            merged[p] = entry

    now_local = datetime.now().astimezone()
    ordered: dict[str, dict[str, Any]] = {}
    all_keys = list(ALL_PROFILES) + [k for k in merged if k not in ALL_PROFILES]
    for p in all_keys:
        if p not in merged:
            continue
        entry = dict(merged[p])
        if entry.get("status") == "active_busy" and p not in busy_profiles:
            entry["status"] = "ready_pro"
            entry["current_batch"] = None
        elif p in busy_profiles and entry.get("argon_high_ok") is not False:
            entry["status"] = "active_busy"
        reset_at_str = entry.get("reset_at")
        if reset_at_str:
            try:
                dt_reset = datetime.fromisoformat(str(reset_at_str)).astimezone()
                rem_s = max(0, int(round((dt_reset - now_local).total_seconds())))
                entry["reset_in_s"] = rem_s
                entry["reset_in_human"] = _fmt_duration(rem_s)
                entry["reset_at_12h"] = dt_reset.strftime("%I:%M %p")
            except Exception:
                pass
        if entry.get("lastSeenAt") and not entry.get("lastSeenAt_12h"):
            entry["lastSeenAt_12h"] = fmt_iso_to_12h(entry.get("lastSeenAt"))
        entry["plan_limit_info"] = explain_plan_limit(entry.get("limit"), entry.get("argon_high_ok"))
        prev_pools = entry.get("pools") if isinstance(entry.get("pools"), dict) else {}
        entry["pools"] = merge_quota_pools(entry, prev_pools)
        # Always recompute each pool's countdown from its own reset_at.
        # Cached non-binding pools otherwise freeze with a stale reset_in_human.
        for _pk, pool in list((entry.get("pools") or {}).items()):
            if not isinstance(pool, dict):
                continue
            pool_reset = pool.get("reset_at")
            if not pool_reset:
                continue
            try:
                dt_p = datetime.fromisoformat(str(pool_reset))
                if dt_p.tzinfo is None:
                    dt_p = dt_p.replace(tzinfo=now_local.tzinfo)
                else:
                    dt_p = dt_p.astimezone()
                rem_s = int(round((dt_p - now_local).total_seconds()))
                elapsed = rem_s <= 0
                pool["reset_in_s"] = max(0, rem_s)
                pool["reset_in_human"] = "due" if elapsed else _fmt_duration(rem_s)
                pool["reset_at_12h"] = dt_p.strftime("%I:%M %p")
                pool["reset_elapsed"] = elapsed
                # After timer elapses, cached remaining is likely stale until this
                # pool is binding again in qpEbW.
                if elapsed and not pool.get("binding"):
                    pool["remaining_stale"] = True
            except Exception:
                pass
        ordered[p] = entry
    return ordered


def _get_or_refresh_ledger() -> dict[str, Any]:
    turns_m = TURNS_FILE.stat().st_mtime if TURNS_FILE.exists() else 0.0
    events_m = EVENTS_FILE.stat().st_mtime if EVENTS_FILE.exists() else 0.0
    status_m = 0.0
    for st_file in SCRATCH.glob("surah*_parallel_status.json"):
        try:
            status_m = max(status_m, st_file.stat().st_mtime)
        except Exception:
            pass
    latest_m = max(turns_m, events_m, status_m)
    if not _ledger_cache["data"] or latest_m > _ledger_cache["mtime"] or not LEDGER_FILE.exists():
        try:
            data = build_all_surahs_ledger()
            _ledger_cache["data"] = data
            _ledger_cache["mtime"] = max(latest_m, time.time())
        except Exception:
            _ledger_cache["data"] = _read_json(LEDGER_FILE)
    return _ledger_cache["data"]


def _parse_ayah_label(batch_id: str) -> str:
    m = re.match(r"^s\d{3}_a(\d+)_(\d+)$", batch_id)
    if not m:
        return batch_id
    return f"{int(m.group(1))}–{int(m.group(2))}"


def _step_kind(label: str | None) -> str:
    """Coarse step family for Gantt splits (A vs B vs other)."""
    s = str(label or "").strip().lower()
    if "step a" in s:
        return "A"
    if "step b" in s:
        return "B"
    if not s:
        return "other"
    return f"x:{s[:48]}"


def _parse_flexible_ts(raw: Any) -> datetime | None:
    """Parse ISO timestamps; return naive local wall-clock for Gantt math."""
    if not raw:
        return None
    s = str(raw).strip()
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def _build_batch_gantt(surah: int, batches: list[dict[str, Any]]) -> dict[str, Any]:
    """Account-swimlane Gantt: one lane per profile, batch chips as segments."""
    prefix = f"s{surah:03d}_"
    by_turns: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if TURNS_FILE.exists():
        try:
            for line in TURNS_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    t = json.loads(line)
                except Exception:
                    continue
                bid = str(t.get("batch") or "")
                if bid.startswith(prefix):
                    by_turns[bid].append(t)
        except Exception:
            pass

    batch_meta = {str(b.get("batch")): b for b in batches if b.get("batch")}
    all_ids = sorted(set(batch_meta) | set(by_turns))
    now_local = datetime.now().astimezone().replace(tzinfo=None)

    # Flatten to per-(batch,profile,ok) work chips, merged across nearby turns.
    chips: list[dict[str, Any]] = []
    for bid in all_ids:
        meta = batch_meta.get(bid) or {}
        stage = str(meta.get("stage") or "pending")
        turns = sorted(by_turns.get(bid) or [], key=lambda x: str(x.get("ts") or ""))
        pieces: list[dict[str, Any]] = []
        for t in turns:
            end_dt = _parse_flexible_ts(t.get("ts"))
            if end_dt is None:
                continue
            if end_dt.tzinfo is not None:
                end_dt = end_dt.replace(tzinfo=None)
            secs = float(t.get("secs") or 0)
            start_dt = end_dt - timedelta(seconds=max(0.0, secs))
            pieces.append(
                {
                    "batch": bid,
                    "ayah": _parse_ayah_label(bid),
                    "profile": str(t.get("profile") or meta.get("profile") or "unassigned"),
                    "ok": str(t.get("outcome") or "ok") == "ok",
                    "label": str(t.get("label") or t.get("step") or ""),
                    "start_dt": start_dt,
                    "end_dt": end_dt,
                    "secs": secs,
                }
            )
        if not pieces and meta:
            t0 = _parse_flexible_ts(meta.get("updatedAt"))
            if t0 is None:
                continue
            if t0.tzinfo is not None:
                t0 = t0.replace(tzinfo=None)
            t1 = t0 + timedelta(seconds=float(meta.get("total_s") or 60))
            if stage in ("step_a", "step_b"):
                t1 = max(t1, now_local)
            pieces.append(
                {
                    "batch": bid,
                    "ayah": _parse_ayah_label(bid),
                    "profile": str(meta.get("profile") or "unassigned"),
                    "ok": stage not in ("error", "failed_step_b", "failed_validate"),
                    "label": stage,
                    "start_dt": t0,
                    "end_dt": t1,
                    "secs": (t1 - t0).total_seconds(),
                }
            )

        # Chronological — never group by profile first (that hid Step A→B splits).
        pieces.sort(key=lambda p: (p["start_dt"], p["end_dt"]))
        merged: list[dict[str, Any]] = []
        for p in pieces:
            p = dict(p)
            p["step_kind"] = _step_kind(p.get("label"))
            # Only glue true retries of the *same* step label. Keep Step A | Step B
            # (and B c1 | c2 | …) as separate chips so hover/dividers stay honest.
            if (
                merged
                and merged[-1]["batch"] == p["batch"]
                and merged[-1]["profile"] == p["profile"]
                and merged[-1]["ok"] == p["ok"]
                and merged[-1].get("label") == p.get("label")
                and (p["start_dt"] - merged[-1]["end_dt"]).total_seconds() <= 8.0
            ):
                merged[-1]["end_dt"] = max(merged[-1]["end_dt"], p["end_dt"])
                merged[-1]["secs"] = float(merged[-1]["secs"]) + float(p["secs"])
            else:
                merged.append(p)
        chips.extend(merged)

    if not chips:
        return {
            "mode": "both",
            "lanes": [],
            "batch_rows": [],
            "rows": [],
            "ticks": [],
            "tMin": None,
            "tMax": None,
            "tMin_12h": None,
            "tMax_12h": None,
            "span_s": 0,
        }

    t_min = min(c["start_dt"] for c in chips)
    t_max = max(c["end_dt"] for c in chips)
    span = max(1.0, (t_max - t_min).total_seconds())

    def _pct(start: datetime, end: datetime) -> tuple[float, float]:
        left = 100.0 * (start - t_min).total_seconds() / span
        width = max(0.45, 100.0 * max(0.8, (end - start).total_seconds()) / span)
        return round(left, 3), round(width, 3)

    # Assign stack lane 0/1 inside each profile for overlapping concurrent chats.
    by_prof: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in chips:
        left, width = _pct(c["start_dt"], c["end_dt"])
        by_prof[c["profile"]].append(
            {
                "batch": c["batch"],
                "ayah": c["ayah"],
                "profile": c["profile"],
                "ok": c["ok"],
                "outcome": "ok" if c["ok"] else "fail",
                "label": c["label"],
                "step_kind": c.get("step_kind") or _step_kind(c.get("label")),
                "start": c["start_dt"].isoformat(timespec="seconds"),
                "end": c["end_dt"].isoformat(timespec="seconds"),
                "start_12h": c["start_dt"].strftime("%I:%M %p").lstrip("0"),
                "end_12h": c["end_dt"].strftime("%I:%M %p").lstrip("0"),
                "secs": round(float(c["secs"]), 1),
                "left_pct": left,
                "width_pct": width,
                "stack": 0,
            }
        )

    lane_order = [p for p in ("qoun", "abod", "smallbusiness", "quyn", "default") if p in by_prof]
    lane_order += [p for p in sorted(by_prof) if p not in lane_order]

    lanes: list[dict[str, Any]] = []
    for prof in lane_order:
        segs = sorted(by_prof[prof], key=lambda s: (s["start"], s["end"]))
        # Greedy 2-lane packing for overlaps.
        lane_ends = [-1e18, -1e18]
        for seg in segs:
            s = datetime.fromisoformat(seg["start"]).timestamp()
            e = datetime.fromisoformat(seg["end"]).timestamp()
            if s >= lane_ends[0] - 0.5:
                seg["stack"] = 0
                lane_ends[0] = e
            elif s >= lane_ends[1] - 0.5:
                seg["stack"] = 1
                lane_ends[1] = e
            else:
                # Prefer the earlier-finishing stack.
                if lane_ends[0] <= lane_ends[1]:
                    seg["stack"] = 0
                    lane_ends[0] = e
                else:
                    seg["stack"] = 1
                    lane_ends[1] = e
        stacks_used = 1 + max((seg["stack"] for seg in segs), default=0)
        ok_n = sum(1 for seg in segs if seg["ok"])
        fail_n = sum(1 for seg in segs if not seg["ok"])
        lanes.append(
            {
                "profile": prof,
                "segments": segs,
                "stacks": stacks_used,
                "ok_segments": ok_n,
                "fail_segments": fail_n,
                "active_s": round(sum(seg["secs"] for seg in segs if seg["ok"]), 1),
            }
        )

    ticks: list[dict[str, Any]] = []
    cur = t_min.replace(second=0, microsecond=0)
    add = (10 - cur.minute % 10) % 10
    if add:
        cur = cur + timedelta(minutes=add)
    while cur <= t_max:
        ticks.append(
            {
                "at": cur.isoformat(timespec="seconds"),
                "label": cur.strftime("%I:%M %p").lstrip("0"),
                "left_pct": round(100.0 * (cur - t_min).total_seconds() / span, 3),
            }
        )
        cur += timedelta(minutes=10)

    open_wave: dict[str, int] = defaultdict(int)
    seen_open: set[tuple[str, str]] = set()
    for lane in lanes:
        for seg in lane["segments"]:
            s = datetime.fromisoformat(seg["start"])
            if (s - t_min).total_seconds() <= 15:
                key = (lane["profile"], seg["batch"])
                if key not in seen_open:
                    seen_open.add(key)
                    open_wave[lane["profile"]] += 1

    # One row per batch, bar split into account chunks (handoffs / retries).
    by_batch_chips: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in chips:
        left, width = _pct(c["start_dt"], c["end_dt"])
        by_batch_chips[c["batch"]].append(
            {
                "batch": c["batch"],
                "ayah": c["ayah"],
                "profile": c["profile"],
                "ok": c["ok"],
                "outcome": "ok" if c["ok"] else "fail",
                "label": c["label"],
                "step_kind": c.get("step_kind") or _step_kind(c.get("label")),
                "start": c["start_dt"].isoformat(timespec="seconds"),
                "end": c["end_dt"].isoformat(timespec="seconds"),
                "start_12h": c["start_dt"].strftime("%I:%M %p").lstrip("0"),
                "end_12h": c["end_dt"].strftime("%I:%M %p").lstrip("0"),
                "secs": round(float(c["secs"]), 1),
                "left_pct": left,
                "width_pct": width,
            }
        )

    batch_rows: list[dict[str, Any]] = []
    for bid in sorted(by_batch_chips.keys(), key=lambda x: x):
        segs = sorted(by_batch_chips[bid], key=lambda s: (s["start"], s["end"]))
        t0 = datetime.fromisoformat(segs[0]["start"])
        t1 = max(datetime.fromisoformat(s["end"]) for s in segs)
        tags: list[str] = []
        for s in segs:
            if s["profile"] not in tags:
                tags.append(s["profile"])
        meta = batch_meta.get(bid) or {}
        stage = str(meta.get("stage") or "pending")
        has_fail = any(not s["ok"] for s in segs) or stage in ("error", "failed_step_b", "failed_validate")
        left, width = _pct(t0, t1)
        batch_rows.append(
            {
                "batch": bid,
                "label": _parse_ayah_label(bid),
                "tags": tags,
                "status_profile": meta.get("profile"),
                "stage": stage,
                "has_fail": has_fail,
                "start": t0.isoformat(timespec="seconds"),
                "end": t1.isoformat(timespec="seconds"),
                "start_12h": t0.strftime("%I:%M %p").lstrip("0"),
                "end_12h": t1.strftime("%I:%M %p").lstrip("0"),
                "wall_s": round(max(1.0, (t1 - t0).total_seconds()), 1),
                "active_s": round(sum(s["secs"] for s in segs if s["ok"]), 1),
                "left_pct": left,
                "width_pct": width,
                "segments": segs,
            }
        )
    batch_rows.sort(key=lambda r: (r["start"], r["label"]))

    return {
        "mode": "both",
        "lanes": lanes,
        "batch_rows": batch_rows,
        "rows": batch_rows,  # alias
        "open_wave": dict(open_wave),
        "ticks": ticks,
        "tMin": t_min.isoformat(timespec="seconds"),
        "tMax": t_max.isoformat(timespec="seconds"),
        "tMin_12h": t_min.strftime("%I:%M %p").lstrip("0"),
        "tMax_12h": t_max.strftime("%I:%M %p").lstrip("0"),
        "span_s": round(span, 1),
    }


def _turn_workers_by_batch(surah: int) -> dict[str, dict[str, Any]]:
    """Who actually ran turns for each batch (matches Gantt swimlanes)."""
    prefix = f"s{surah:03d}_"
    out: dict[str, dict[str, Any]] = {}
    if not TURNS_FILE.exists():
        return out
    try:
        lines = TURNS_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return out
    secs_map: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    order_map: dict[str, list[str]] = defaultdict(list)
    for line in lines:
        if not line.strip():
            continue
        try:
            t = json.loads(line)
        except Exception:
            continue
        bid = str(t.get("batch") or "")
        if not bid.startswith(prefix):
            continue
        prof = str(t.get("profile") or "").strip()
        if not prof:
            continue
        secs = float(t.get("secs") or 0)
        # Count both ok and fail so handoffs/errors still attribute the worker.
        secs_map[bid][prof] += max(0.0, secs)
        if prof not in order_map[bid]:
            order_map[bid].append(prof)
    for bid, by_prof in secs_map.items():
        workers = order_map.get(bid) or list(by_prof.keys())
        primary = max(by_prof.items(), key=lambda kv: kv[1])[0] if by_prof else (workers[0] if workers else None)
        out[bid] = {
            "worked_by": workers,
            "primary_profile": primary,
            "secs_by_profile": {k: round(v, 1) for k, v in by_prof.items()},
        }
    return out


def _stage_progress(stage: str | None, steps: list[dict[str, Any]]) -> tuple[int, str]:
    stage = stage or "pending"
    if stage in ("validated_ready", "done_cached"):
        return 100, "Done"
    if stage in ("error", "failed_step_b", "failed_validate"):
        ok = sum(1 for s in steps if s.get("outcome") == "ok")
        if ok:
            return min(90, 15 + ok * 10), "Error (partial)"
        return 0, "Error"
    if stage == "step_a":
        has_a_ok = any(s.get("step", "").startswith("Step A") and s.get("outcome") == "ok" for s in steps)
        return (28 if has_a_ok else 14), "Step A (unified extract)"
    if stage == "step_b":
        b_ok = [s for s in steps if s.get("step", "").startswith("Step B") and s.get("outcome") == "ok"]
        total_chunks = 3
        for s in b_ok:
            m = re.search(r"c(\d+)/(\d+)", s.get("step", ""))
            if m:
                total_chunks = max(1, int(m.group(2)))
        c_done = sum(1 for s in b_ok if re.search(r"c\d+/\d+", s.get("step", "")))
        r_done = sum(1 for s in b_ok if "repair" in s.get("step", ""))
        base = 30 + int(55 * min(1.0, c_done / max(1, total_chunks)))
        pct = min(95, base + r_done * 3)
        return pct, f"Step B ({c_done}/{total_chunks} chunks, {r_done} repairs)"
    return 0, "Queued"


def collect_state(surah: int = 6) -> dict[str, Any]:
    ledger = _get_or_refresh_ledger()
    surahs_map = ledger.get("surahs") or {}
    available_surahs = [
        {
            "surah": int(k),
            "name_ar": v.get("surah_name_ar", SURAH_NAMES_AR.get(int(k), f"سورة {k}")),
            "batches_done": v.get("batches_done", 0),
            "batches_total": v.get("batches_total", 0),
            "quota_credits_used": v.get("quota_credits_used", 0),
            "total_tokens": v.get("total_tokens", 0),
            "estimated_cost_usd": v.get("estimated_cost_usd", 0.0),
        }
        for k, v in sorted(surahs_map.items(), key=lambda kv: int(kv[0]), reverse=True)
    ]

    s_data = surahs_map.get(str(surah)) or {}
    # Never silently switch away from an explicitly requested Surah (e.g. mid-run
    # before any turns.jsonl lines exist yet). Merge live status if ledger is thin.
    status_path = SCRATCH / f"surah{surah}_parallel_status.json"
    status_doc = _read_json(status_path)
    status_batches = (
        status_doc.get("batches")
        if isinstance(status_doc, dict) and isinstance(status_doc.get("batches"), dict)
        else {}
    )
    if not any(int(a["surah"]) == surah for a in available_surahs):
        available_surahs.insert(
            0,
            {
                "surah": surah,
                "name_ar": (status_doc.get("surah_name_ar") if isinstance(status_doc, dict) else None)
                or SURAH_NAMES_AR.get(surah, f"سورة {surah}"),
                "batches_done": 0,
                "batches_total": len(status_batches) or (s_data.get("batches_total") or 0),
                "quota_credits_used": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
            },
        )
    if not s_data and status_batches:
        s_data = {
            "surah": surah,
            "surah_name_ar": status_doc.get("surah_name_ar") or SURAH_NAMES_AR.get(surah, f"سورة {surah}"),
            "batches": {
                bid: dict(v) if isinstance(v, dict) else {"batch": bid, "stage": "pending"}
                for bid, v in status_batches.items()
            },
            "batches_total": len(status_batches),
            "batches_done": 0,
        }
    elif not s_data and surahs_map:
        # Only fall back when the requested Surah has no ledger AND no status file.
        first_key = sorted(surahs_map.keys(), key=int, reverse=True)[0]
        surah = int(first_key)
        s_data = surahs_map[first_key]
        status_path = SCRATCH / f"surah{surah}_parallel_status.json"
        status_doc = _read_json(status_path)
        status_batches = (
            status_doc.get("batches")
            if isinstance(status_doc, dict) and isinstance(status_doc.get("batches"), dict)
            else {}
        )

    batches_dict = dict(s_data.get("batches") or {})
    for bid, st in status_batches.items():
        if not isinstance(st, dict):
            continue
        cur = dict(batches_dict.get(bid) or {"batch": bid})
        for k, v in st.items():
            if v is not None:
                cur[k] = v
        batches_dict[bid] = cur

    batches_out: list[dict[str, Any]] = []
    counts = {"done": 0, "running": 0, "queued": 0, "error": 0}
    workers_map = _turn_workers_by_batch(surah)

    for bid, b in batches_dict.items():
        steps = b.get("steps") or []
        stage = b.get("stage") or "pending"
        pct, stage_label = _stage_progress(stage, steps)
        if stage in ("validated_ready", "done_cached"):
            counts["done"] += 1
        elif stage in ("step_a", "step_b"):
            counts["running"] += 1
        elif stage in ("error", "failed_step_b", "failed_validate"):
            counts["error"] += 1
        else:
            counts["queued"] += 1

        ayah_range = b.get("ayahRange")
        if not ayah_range:
            m_ay = re.match(r"^s\d{3}_a(\d+)_(\d+)$", str(bid))
            if m_ay:
                ayah_range = f"{int(m_ay.group(1))}–{int(m_ay.group(2))}"
        status_profile = b.get("profile")
        winfo = workers_map.get(bid) or {}
        worked_by = list(winfo.get("worked_by") or ([] if not status_profile else [str(status_profile)]))
        secs_by = winfo.get("secs_by_profile") or {}
        batches_out.append(
            {
                **b,
                "batch": bid,
                "ayahRange": ayah_range,
                "pct": pct,
                "stageLabel": stage_label,
                "lastStep": steps[-1] if steps else None,
                # Cards group by final status owner (one batch → one card group).
                # worked_by is metadata for tags + chunked Gantt handoffs.
                "status_profile": status_profile,
                "profile": status_profile,
                "worked_by": worked_by,
                "secs_by_profile": secs_by,
            }
        )

    log_tail: list[str] = []
    log_file = _log_file_for(surah)
    if log_file.exists():
        try:
            raw_lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-35:]
            for ln in raw_lines:
                # Convert any leading [HH:MM:SS] 24h timestamp in log tail to 12h AM/PM
                m_ts = re.match(r"^\[(\d{2}:\d{2}:\d{2})\](.*)$", ln)
                if m_ts:
                    ln = f"[{fmt_iso_to_12h(m_ts.group(1))}]{m_ts.group(2)}"
                log_tail.append(ln)
        except Exception:
            pass

    with _state_lock:
        quotas_copy = dict(_quota_state)

    now_dt = datetime.now().astimezone()
    return {
        "now": now_dt.isoformat(timespec="seconds"),
        "now_12h": fmt_12h(now_dt),
        "selectedSurah": surah,
        "surahNameAr": s_data.get("surah_name_ar") or SURAH_NAMES_AR.get(surah, f"سورة {surah}"),
        "availableSurahs": available_surahs,
        "pricingModel": ledger.get("pricing_model") or {},
        "surahTotals": {
            "batches_total": s_data.get("batches_total", len(batches_out)),
            "batches_done": s_data.get("batches_done", counts["done"]),
            "extractions_total": s_data.get("extractions_total", 0),
            "demos_total": s_data.get("demos_total", 0),
            "quota_credits_used": s_data.get("quota_credits_used", 0),
            "quota_burst_windows_equiv": s_data.get("quota_burst_windows_equiv", 0.0),
            "quota_macro_pct_equiv": s_data.get("quota_macro_pct_equiv", 0.0),
            "new_input_tokens": s_data.get("new_input_tokens", 0),
            "context_input_tokens": s_data.get("context_input_tokens", 0),
            "thinking_tokens": s_data.get("thinking_tokens", 0),
            "output_tokens": s_data.get("output_tokens", 0),
            "total_tokens": s_data.get("total_tokens", 0),
            "estimated_cost_usd": s_data.get("estimated_cost_usd", 0.0),
            "by_account": s_data.get("by_account") or {},
        },
        "counts": counts,
        "totalBatches": len(batches_out),
        "batches": batches_out,
        "gantt": _build_batch_gantt(surah, batches_out),
        "quotas": quotas_copy,
        "logTail": log_tail,
    }


def _quota_poller() -> None:
    """Refresh quota state every 3s from disk/logs, and poll qpEbW RPC every 60s."""
    last_rpc_poll = 0.0
    last_alive_check = 0.0
    runner_alive = False

    while True:
        now_m = time.monotonic()
        if now_m - last_alive_check >= 10.0:
            runner_alive = _check_runner_alive()
            last_alive_check = now_m

        if now_m - last_rpc_poll >= 60.0:
            last_rpc_poll = now_m
            try:
                probe_py = Path(r"C:\Users\Khaled\AppData\Roaming\uv\tools\gemini-web-mcp-cli\Scripts\python.exe")
                probe_script = SCRATCH / "probe_profile_quotas.py"
                if probe_py.exists() and probe_script.exists():
                    subprocess.run(
                        [str(probe_py), str(probe_script), "--no-picker", "--no-launch", "--json"],
                        capture_output=True,
                        text=True,
                        timeout=45,
                    )
                    now_dt = datetime.now().astimezone()
                    with _state_lock:
                        _quota_state["lastRpcPollAt"] = now_dt.isoformat(timespec="seconds")
                        _quota_state["lastRpcPollAt_12h"] = fmt_12h(now_dt)
                        _quota_state["error"] = None
            except Exception as exc:
                with _state_lock:
                    _quota_state["error"] = f"{type(exc).__name__}: {exc}"

        try:
            merged = _merge_all_quota_sources(runner_alive=runner_alive)
            now_dt = datetime.now().astimezone()
            with _state_lock:
                _quota_state["profiles"] = merged
                _quota_state["updatedAt"] = now_dt.isoformat(timespec="seconds")
                _quota_state["updatedAt_12h"] = fmt_12h(now_dt)
                _quota_state["runnerAlive"] = runner_alive
                _quota_state["source"] = (
                    "live-rpc + runner-live (active)"
                    if runner_alive
                    else "live-rpc + quotas_live.json (runner idle)"
                )
        except Exception as exc:
            with _state_lock:
                _quota_state["error"] = str(exc)

        time.sleep(3)


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Waqf &amp; Ibtida — Generalized Surah Parallel Runner &amp; Quota Dashboard</title>
<style>
  :root {
    --bg: #0b1020;
    --panel: #131b33;
    --panel-2: #192342;
    --border: #26335d;
    --text: #e8eeff;
    --muted: #93a3cc;
    --green: #22c55e;
    --blue: #3b82f6;
    --amber: #f59e0b;
    --red: #ef4444;
    --purple: #a855f7;
    --cyan: #06b6d4;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 18px 22px 44px;
  }
  header {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
  }
  h1 {
    font-size: 20px;
    margin: 0;
    font-weight: 700;
    letter-spacing: -0.01em;
  }
  .sub {
    color: var(--muted);
    font-size: 13px;
    margin-top: 3px;
  }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    background: var(--panel-2);
    border: 1px solid var(--border);
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 8px var(--green);
  }
  .toolbar-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 14px;
  }
  .btn-group {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }
  .tab-btn {
    background: var(--panel-2);
    color: var(--muted);
    border: 1px solid var(--border);
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .tab-btn:hover {
    color: var(--text);
    border-color: #3b5398;
  }
  .tab-btn.active {
    background: rgba(59,130,246,.22);
    color: #93c5fd;
    border-color: rgba(59,130,246,.55);
  }
  .grid-top {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(195px, 1fr));
    gap: 10px;
    margin-bottom: 14px;
  }
  .card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
  }
  .card-title {
    color: var(--muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
  }
  .card-val {
    font-size: 21px;
    font-weight: 700;
  }
  .card-sub {
    color: var(--muted);
    font-size: 11.5px;
    margin-top: 4px;
    line-height: 1.35;
  }
  .section-title {
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
    margin: 18px 0 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }
  .quotas-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(255px, 1fr));
    gap: 10px;
  }
  .plan-explainer {
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 14px;
    margin-top: 10px;
    font-size: 12px;
    color: #cbd5e1;
    line-height: 1.5;
  }
  .plan-explainer strong { color: #93c5fd; }
  .bar {
    height: 8px;
    background: #0d1428;
    border-radius: 999px;
    overflow: hidden;
    margin-top: 8px;
    border: 1px solid var(--border);
  }
  .bar > div {
    height: 100%;
    border-radius: 999px;
    transition: width 0.35s ease;
  }
  .account-group-box {
    background: rgba(19, 27, 51, 0.55);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 14px;
  }
  .account-group-header {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    padding-bottom: 10px;
    margin-bottom: 12px;
    border-bottom: 1px solid var(--border);
  }
  .batches-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(390px, 1fr));
    gap: 12px;
  }
  .batch-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 13px 15px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .batch-card.running {
    border-color: var(--blue);
    box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.35);
  }
  .batch-card.done { border-color: rgba(34, 197, 94, 0.45); }
  .batch-card.error { border-color: rgba(239, 68, 68, 0.6); }
  .batch-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }
  .batch-id { font-weight: 700; font-size: 15px; }
  .badge {
    font-size: 11px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
    text-transform: uppercase;
  }
  .badge.done { background: rgba(34,197,94,.16); color: #4ade80; border: 1px solid rgba(34,197,94,.35); }
  .badge.running { background: rgba(59,130,246,.18); color: #60a5fa; border: 1px solid rgba(59,130,246,.4); }
  .badge.queued { background: rgba(147,163,204,.12); color: var(--muted); border: 1px solid var(--border); }
  .badge.error { background: rgba(239,68,68,.18); color: #f87171; border: 1px solid rgba(239,68,68,.4); }
  .badge.warn { background: rgba(245,158,11,.18); color: #fbbf24; border: 1px solid rgba(245,158,11,.4); }
  .quota-rings {
    display: flex;
    flex-wrap: wrap;
    gap: 12px 14px;
    align-items: flex-start;
    margin-top: 10px;
  }
  .ring-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
    min-width: 76px;
  }
  .ring-wrap.time { min-width: 58px; }
  .ring {
    --p: 0;
    --c: var(--muted);
    position: relative;
    width: 78px;
    height: 78px;
    border-radius: 50%;
    background: conic-gradient(var(--c) calc(var(--p) * 1%), rgba(38, 51, 93, 0.95) 0);
    display: grid;
    place-items: center;
    box-shadow: 0 0 0 1px rgba(255,255,255,0.04), 0 0 18px color-mix(in srgb, var(--c) 28%, transparent);
  }
  .ring::before {
    content: "";
    position: absolute;
    inset: 9px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 30%, #1b2748 0%, #10182d 70%);
    border: 1px solid rgba(255,255,255,0.05);
  }
  .ring > .ring-core {
    position: relative;
    z-index: 1;
    text-align: center;
    line-height: 1.15;
    padding: 0 4px;
  }
  .ring .ring-main {
    display: block;
    font-size: 13px;
    font-weight: 800;
    color: var(--text);
  }
  .ring .ring-sub {
    display: block;
    font-size: 9.5px;
    color: var(--muted);
    margin-top: 1px;
  }
  .ring.sm {
    width: 54px;
    height: 54px;
  }
  .ring.sm::before { inset: 7px; }
  .ring.sm .ring-main { font-size: 10px; }
  .ring.sm .ring-sub { font-size: 8px; }
  .ring-label {
    font-size: 11px;
    font-weight: 700;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .ring-meta {
    font-size: 10px;
    color: var(--muted);
    text-align: center;
    max-width: 90px;
    line-height: 1.25;
  }
  .ring-wrap.burst .ring { --tone: var(--cyan); }
  .ring-wrap.weekly .ring { --tone: #a855f7; }
  .ring-wrap.free .ring { --tone: #94a3b8; }
  .ring-wrap.other .ring { --tone: var(--blue); }
  .ring-wrap.time .ring { --tone: var(--amber); }
  .profile-tag {
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 5px;
    background: rgba(168,85,247,.16);
    color: #d8b4fe;
    border: 1px solid rgba(168,85,247,.35);
    font-weight: 600;
  }
  .meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    font-size: 12px;
    color: var(--muted);
  }
  .meta-row strong { color: var(--text); }
  .cost-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 6px 9px;
    border-radius: 7px;
    background: rgba(6, 182, 212, 0.09);
    border: 1px solid rgba(6, 182, 212, 0.28);
    font-size: 11.5px;
    color: #a5f3fc;
  }
  .steps-list {
    margin-top: 4px;
    border-top: 1px solid var(--border);
    padding-top: 6px;
    font-size: 11.5px;
    max-height: 165px;
    overflow-y: auto;
  }
  .step-item {
    display: grid;
    grid-template-columns: 1fr auto auto auto auto;
    gap: 7px;
    padding: 2.5px 0;
    color: var(--muted);
    border-bottom: 1px dashed rgba(38,51,93,0.45);
  }
  .step-item.ok { color: #cbd5f5; }
  .step-item.fail { color: #fca5a5; }
  pre.logbox {
    background: #070b17;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px;
    font-size: 11.5px;
    line-height: 1.45;
    color: #cbd5f5;
    max-height: 280px;
    overflow-y: auto;
    margin: 0;
    white-space: pre-wrap;
  }
  .gantt-panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px;
    margin-bottom: 8px;
  }
  .gantt-legend {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }
  .gantt-legend .lg {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--muted);
    font-size: 12px;
  }
  .gantt-legend .lg i {
    width: 12px;
    height: 12px;
    border-radius: 3px;
    display: inline-block;
  }
  .gantt-axis {
    position: relative;
    height: 26px;
    margin-left: 130px;
    margin-right: 74px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 8px;
  }
  .gantt-tick {
    position: absolute;
    top: 0;
    bottom: 0;
    border-left: 1px dashed rgba(148,163,184,.22);
  }
  .gantt-tick span {
    position: absolute;
    top: 2px;
    left: 4px;
    font-size: 10px;
    color: var(--muted);
    white-space: nowrap;
  }
  .gantt-lane {
    display: grid;
    grid-template-columns: 120px 1fr 64px;
    gap: 10px;
    align-items: stretch;
    margin: 8px 0;
  }
  .gantt-lane-lab {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 2px;
    min-width: 0;
  }
  .gantt-lane-lab .name {
    font-weight: 700;
    font-size: 13px;
  }
  .gantt-lane-lab .hint {
    font-size: 10px;
    color: var(--muted);
  }
  .gantt-track {
    position: relative;
    min-height: 44px;
    background:
      linear-gradient(180deg, rgba(255,255,255,.03), transparent 40%),
      rgba(7,11,23,.72);
    border: 1px solid rgba(38,51,93,.8);
    border-radius: 8px;
    overflow: hidden;
  }
  .gantt-track.stacks-2 { min-height: 58px; }
  .gantt-chip {
    position: absolute;
    border-radius: 6px;
    min-width: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 5px;
    overflow: hidden;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,.14);
    z-index: 1;
    cursor: default;
  }
  .gantt-chip .txt { position: relative; z-index: 1; }
  .gantt-chip .txt {
    font-size: 10px;
    font-weight: 700;
    color: #0b1020;
    white-space: nowrap;
    text-overflow: ellipsis;
    overflow: hidden;
    max-width: 100%;
  }
  /* Same-account Step A|B (or B chunk) boundary — thin line, not a gap. */
  .gantt-chip.step-split {
    box-shadow:
      inset 2px 0 0 0 rgba(255,255,255,.92),
      inset 3px 0 0 0 rgba(15,23,42,.55),
      inset 0 0 0 1px rgba(255,255,255,.14);
  }
  .gantt-chip.step-split.fail {
    box-shadow:
      inset 2px 0 0 0 rgba(254,202,202,.95),
      inset 3px 0 0 0 rgba(127,29,29,.65),
      inset 0 0 0 1px rgba(255,255,255,.12),
      0 0 0 1px rgba(127,29,29,.55);
  }
  .gantt-chip.fail {
    z-index: 2;
    /* Keep account color; mark failure with dotted red surround only. */
    outline: 2px dotted rgba(248,113,113,.95);
    outline-offset: 1px;
    box-shadow:
      inset 0 0 0 1px rgba(255,255,255,.12),
      0 0 0 1px rgba(127,29,29,.55);
    filter: saturate(0.85);
  }
  .gantt-chip.fail::after {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: repeating-linear-gradient(
      -45deg,
      transparent,
      transparent 4px,
      rgba(239,68,68,.22) 4px,
      rgba(239,68,68,.22) 8px
    );
    pointer-events: none;
  }
  .gantt-batch-row {
    display: grid;
    grid-template-columns: 120px 1fr 64px;
    gap: 10px;
    align-items: center;
    margin: 5px 0;
  }
  .gantt-batch-lab {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }
  .gantt-batch-lab .ayah { font-weight: 700; font-size: 13px; }
  .gantt-batch-tags { display: flex; flex-wrap: wrap; gap: 3px; }
  .gantt-batch-tag {
    font-size: 9.5px;
    padding: 1px 5px;
    border-radius: 4px;
    border: 1px solid rgba(255,255,255,.14);
    line-height: 1.25;
  }
  .gantt-batch-track {
    position: relative;
    height: 28px;
    background: rgba(7,11,23,.72);
    border: 1px solid rgba(38,51,93,.8);
    border-radius: 8px;
    overflow: hidden;
  }
  .gantt-meta {
    font-size: 11px;
    color: var(--muted);
    text-align: right;
    display: flex;
    align-items: center;
    justify-content: flex-end;
  }
  .gantt-empty {
    color: var(--muted);
    font-size: 13px;
    padding: 10px 4px;
  }
  .gantt-block-title {
    font-size: 12px;
    font-weight: 700;
    color: var(--muted);
    margin: 4px 0 8px;
    letter-spacing: 0.02em;
  }
</style>
</head>
<body>
  <header>
    <div>
      <h1 id="main-title">Waqf &amp; Ibtida — Surah 6 (الأنعام) Parallel Argon High Dashboard</h1>
      <div class="sub">5-Account Dynamic Pool (<code>default</code> · <code>qoun</code> · <code>abod</code> · <code>smallbusiness</code> · <code>quyn</code>) · 12-Hour AM/PM Clock · Quota, Tokens &amp; Cost Ledger</div>
    </div>
    <div style="display:flex;gap:8px;align-items:center;">
      <span class="pill" id="runner-pill"><span class="dot"></span> <span id="clock">Loading…</span></span>
    </div>
  </header>

  <div class="toolbar-row">
    <div class="btn-group" id="surah-tabs">
      <span style="font-size:12px;color:var(--muted);margin-right:4px;">Select Surah:</span>
    </div>
    <div class="btn-group">
      <span style="font-size:12px;color:var(--muted);margin-right:4px;">Batch View:</span>
      <button class="tab-btn active" id="btn-group-account" onclick="setGrouping('account')">Group by Account Handled</button>
      <button class="tab-btn" id="btn-group-ayah" onclick="setGrouping('ayah')">Order by Ayah Range</button>
    </div>
  </div>

  <div class="grid-top" id="summary-cards"></div>

  <div class="section-title">
    <span>Account Quotas, Dynamic 4 Argon High Tier &amp; 12-Hour Reset Countdown</span>
    <span id="quota-updated" style="font-size:11px;font-weight:400;"></span>
  </div>
  <div class="quotas-grid" id="quotas-grid"></div>
  <div class="plan-explainer">
    <strong>What does "Plan Limit" (<code>2,400</code> vs <code>48,384</code> vs <code>12,096</code>) mean?</strong><br/>
    • Every <strong>4 Argon High</strong> turn deducts exactly <strong>120 credits</strong> in Google's <code>qpEbW</code> usage RPC.<br/>
    • Each Google AI Pro account has <strong>two concurrent rolling quota buckets</strong>, and Google's RPC automatically returns whichever bucket currently has the <strong>higher % used</strong>:<br/>
    &nbsp;&nbsp;1. <strong><code>2,400</code> = 5-hour reset</strong> (~20 Argon High turns @ 120 credits/turn).<br/>
    &nbsp;&nbsp;2. <strong><code>48,384</code> = weekly Pro pool</strong> (~403 Argon High turns @ 120 credits/turn).<br/>
    Each Pro account card always shows <strong>both</strong> pools. Google's RPC returns only the currently binding bucket's credits; the other is the last-seen cached reading (or — until first seen).<br/>
    The RPC <strong>reset timer is always the 5-hour clock</strong> (even when the binding credits are the weekly 48,384 pool) — weekly has no countdown ring.<br/>
    &nbsp;&nbsp;3. <strong><code>12,096</code> = Free / Auto Tier Pool</strong> (seen on <code>default</code>, which dynamically tested as lacking <code>4 Argon High</code> in the Chrome mode picker).
  </div>

  <div class="section-title">
    <span>Wall-Clock Gantt</span>
    <span id="gantt-sub" style="font-size:11px;font-weight:400;"></span>
  </div>
  <div class="gantt-panel" id="gantt-panel"><div class="gantt-empty">Loading timeline…</div></div>

  <div class="section-title">
    <span id="batches-section-label">Batches Grouped by Account Handled</span>
    <span id="batches-sub" style="font-size:11px;font-weight:400;"></span>
  </div>
  <div id="batches-container"></div>

  <div class="section-title">
    <span>Recent Runner Log Tail (<code>surah6_launch.log</code> — 12h AM/PM)</span>
  </div>
  <pre class="logbox" id="log-box">Loading…</pre>

<script>
let currentSurah = new URLSearchParams(window.location.search).get('surah') || '6';
let currentGrouping = 'account';
let lastState = null;

function setSurah(s) {
  currentSurah = String(s);
  const url = new URL(window.location.href);
  url.searchParams.set('surah', currentSurah);
  window.history.replaceState({}, '', url);
  tick();
}

function setGrouping(mode) {
  currentGrouping = mode;
  document.getElementById('btn-group-account').classList.toggle('active', mode === 'account');
  document.getElementById('btn-group-ayah').classList.toggle('active', mode === 'ayah');
  document.getElementById('batches-section-label').textContent =
    mode === 'account' ? 'Batches Grouped by Account Handled' : 'Batches Ordered by Ayah Range';
  if (lastState) renderBatches(lastState);
}

function fmtSec(s) {
  if (s === null || s === undefined) return '—';
  s = Number(s);
  if (s >= 60) return (s / 60).toFixed(1) + 'm';
  return s.toFixed(0) + 's';
}

function fmtNum(n) {
  if (n === null || n === undefined) return '—';
  return Number(n).toLocaleString();
}

function renderBatchCard(b) {
  const cls = b.pct === 100 ? 'done' : (b.stage === 'step_a' || b.stage === 'step_b' ? 'running' : (b.stageLabel.startsWith('Error') ? 'error' : 'queued'));
  const barCol = cls === 'done' ? 'var(--green)' : (cls === 'running' ? 'var(--blue)' : (cls === 'error' ? 'var(--red)' : 'var(--muted)'));
  const stepsHtml = (b.steps || []).slice(-8).map(s => {
    const sc = s.outcome === 'ok' ? 'ok' : 'fail';
    const modeTag = s.mode === 'same_chat' ? 'same' : 'fresh';
    return `<div class="step-item ${sc}">
      <span><strong>[${s.profile}]</strong> ${s.step} <span style="opacity:.75;">(${modeTag})</span></span>
      <span>${s.outcome === 'ok' ? '✓' : '✗'} ${fmtSec(s.elapsed_s)}</span>
      <span>${s.quota_credits || 0}cr</span>
      <span>${((s.total_tokens || 0)/1000).toFixed(1)}k tok</span>
      <span>${s.ts_12h || ''}</span>
    </div>`;
  }).join('');

  const owner = b.status_profile || b.profile;
  const workers = (b.worked_by && b.worked_by.length) ? b.worked_by : (owner ? [owner] : []);
  const handoff = workers.length > 1
    ? `<span style="font-size:11px;color:var(--muted);">chunks: ${workers.join(' → ')}</span>`
    : '';
  return `<div class="batch-card ${cls}">
    <div class="batch-head">
      <div>
        <span class="batch-id">${b.batch}</span>
        <span style="color:var(--muted);font-size:12px;margin-left:6px;">Ayahs ${b.ayahRange || '—'}</span>
      </div>
      <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end;">
        ${owner ? `<span class="profile-tag">${owner}</span>` : ''}
        ${handoff}
        <span class="badge ${cls}">${b.stageLabel}</span>
      </div>
    </div>
    <div class="bar"><div style="width:${b.pct}%;background:${barCol};"></div></div>
    <div class="meta-row">
      <span>Progress: <strong>${b.pct}%</strong></span>
      <span>Stops: <strong>${b.extractions ?? '—'}</strong></span>
      <span>Demos: <strong>${b.demos ?? '—'}</strong></span>
      <span>Turns: <strong>${b.turns_ok} ok / ${b.turns_fail} fail</strong></span>
      <span>Time: <strong>${fmtSec(b.total_s)}</strong> (A:${fmtSec(b.step_a_s)} B:${fmtSec(b.step_b_s)})</span>
    </div>
    <div class="cost-strip">
      <span>Quota Used: <strong>${fmtNum(b.quota_credits_used || 0)} cr</strong></span>
      <span>·</span>
      <span>Est. Tokens: <strong>${fmtNum(b.total_tokens || 0)}</strong> <span style="opacity:.8;">(in:${((b.new_input_tokens||0)/1000).toFixed(1)}k ctx:${((b.context_input_tokens||0)/1000).toFixed(1)}k thk:${((b.thinking_tokens||0)/1000).toFixed(1)}k out:${((b.output_tokens||0)/1000).toFixed(1)}k)</span></span>
      <span>·</span>
      <span>Est. Cost: <strong>$${Number(b.cost_usd || 0).toFixed(2)} USD</strong></span>
      ${b.updatedAt_12h && b.updatedAt_12h !== '—' ? `<span>· Updated: <strong>${b.updatedAt_12h}</strong></span>` : ''}
    </div>
    ${stepsHtml ? `<div class="steps-list">${stepsHtml}</div>` : ''}
  </div>`;
}

const GANTT_PROFILE_COLORS = {
  qoun: '#3b82f6',
  abod: '#a855f7',
  smallbusiness: '#22c55e',
  quyn: '#f59e0b',
  default: '#94a3b8',
  unassigned: '#64748b',
};

function fmtWallMin(s) {
  if (s === null || s === undefined) return '—';
  const n = Number(s);
  if (n >= 60) return (n / 60).toFixed(0) + 'm';
  return Math.max(1, Math.round(n)) + 's';
}

function ganttLegend(profiles) {
  return profiles.map(p => {
    const c = GANTT_PROFILE_COLORS[p] || GANTT_PROFILE_COLORS.unassigned;
    return `<span class="lg"><i style="background:${c}"></i>${p}</span>`;
  }).join('') + `<span class="lg"><i style="background:#3b82f6;outline:2px dotted #f87171;outline-offset:1px;"></i>fail (dotted)</span>`;
}

function ganttAxisHtml(ticks) {
  return (ticks || []).map(t =>
    `<div class="gantt-tick" style="left:${t.left_pct}%"><span>${t.label}</span></div>`
  ).join('');
}

function shortStepLabel(label) {
  const s = String(label || '');
  const mB = s.match(/Step B[^,]*/i);
  if (mB) return mB[0].replace(/\s+/g, ' ').trim();
  const mA = s.match(/Step A[^,]*/i);
  if (mA) return 'Step A';
  return s.slice(0, 28);
}

function stitchAbuttingSegments(segs) {
  // Pull tiny timeline gaps closed so same-account Step A|B reads as one bar + lines.
  const out = (segs || []).map(s => ({ ...s }));
  for (let i = 1; i < out.length; i++) {
    const prev = out[i - 1];
    const seg = out[i];
    if (prev.profile !== seg.profile || !!prev.ok !== !!seg.ok) continue;
    const prevEnd = Number(prev.left_pct) + Number(prev.width_pct);
    const gap = Number(seg.left_pct) - prevEnd;
    if (gap > 0 && gap < 1.2) {
      seg.left_pct = prevEnd;
      seg.width_pct = Math.max(0.35, Number(seg.width_pct) + gap);
      seg._abut = true;
      seg._step_split = (prev.step_kind || shortStepLabel(prev.label)) !== (seg.step_kind || shortStepLabel(seg.label))
        || shortStepLabel(prev.label) !== shortStepLabel(seg.label);
    } else if (Math.abs(gap) <= 0.15) {
      seg._abut = true;
      seg._step_split = true;
    }
  }
  return out;
}

function renderChip(seg, opts) {
  const c = GANTT_PROFILE_COLORS[seg.profile] || GANTT_PROFILE_COLORS.unassigned;
  const fail = seg.ok === false || seg.outcome === 'fail';
  const showTxt = opts.showTxt;
  const step = shortStepLabel(seg.label);
  const title = `${seg.batch || opts.batch || ''} · ${seg.profile} · ${fail ? 'FAIL' : 'ok'} · ${step || 'turn'} · ${seg.start_12h || ''} → ${seg.end_12h || ''} · ${fmtWallMin(seg.secs)}`;
  const top = opts.top != null ? `top:${opts.top}px;height:${opts.height}px;` : `top:4px;bottom:4px;`;
  // Always keep account color; fail only adds dotted surround.
  const style = `left:${seg.left_pct}%;width:${seg.width_pct}%;${top}background:${c};`;
  const txt = showTxt ? `<span class="txt">${opts.txt || step || seg.ayah || seg.profile || ''}</span>` : '';
  const cls = [
    'gantt-chip',
    fail ? 'fail' : 'ok',
    (seg._step_split || opts.stepSplit) ? 'step-split' : '',
  ].filter(Boolean).join(' ');
  return `<div class="${cls}" style="${style}" title="${title}">${txt}</div>`;
}

function renderGantt(data) {
  const panel = document.getElementById('gantt-panel');
  const sub = document.getElementById('gantt-sub');
  const g = data.gantt || {};
  const lanes = g.lanes || [];
  const batchRows = g.batch_rows || g.rows || [];
  if (!lanes.length && !batchRows.length) {
    sub.textContent = `Surah ${data.selectedSurah} · no turn timeline yet`;
    panel.innerHTML = `<div class="gantt-empty">No batch timeline yet — appears once turns start writing.</div>`;
    return;
  }
  const open = g.open_wave || {};
  const openTxt = Object.keys(open).length
    ? (' · open wave: ' + Object.entries(open).map(([p,n]) => `${p}×${n}`).join(', '))
    : '';
  sub.textContent = `Surah ${data.selectedSurah} (${data.surahNameAr}) · ${g.tMin_12h || '—'} → ${g.tMax_12h || '—'} · batch chunks + account lanes${openTxt}`;
  const profiles = [...new Set([
    ...lanes.map(l => l.profile),
    ...batchRows.flatMap(r => r.tags || []),
  ].filter(Boolean))];
  const legend = ganttLegend(profiles);
  const axis = ganttAxisHtml(g.ticks || []);

  const batchBody = batchRows.map(r => {
    const tags = (r.tags || []).map(p => {
      const c = GANTT_PROFILE_COLORS[p] || GANTT_PROFILE_COLORS.unassigned;
      return `<span class="gantt-batch-tag" style="border-color:${c};color:${c}">${p}</span>`;
    }).join('');
    const segs = stitchAbuttingSegments(r.segments || []).map(seg => renderChip(seg, {
      showTxt: Number(seg.width_pct) >= 6,
      // Prefer step name on chunk hover-bar; profile is in the tag row.
      txt: shortStepLabel(seg.label) || seg.profile,
      batch: r.batch,
    })).join('');
    return `<div class="gantt-batch-row">
      <div class="gantt-batch-lab" title="${r.batch}">
        <span class="ayah">${r.label}</span>
        <div class="gantt-batch-tags">${tags}</div>
      </div>
      <div class="gantt-batch-track">${segs}</div>
      <div class="gantt-meta">${fmtWallMin(r.wall_s)}</div>
    </div>`;
  }).join('');

  const laneBody = lanes.map(ln => {
    const c = GANTT_PROFILE_COLORS[ln.profile] || GANTT_PROFILE_COLORS.unassigned;
    const stacks = Math.max(1, ln.stacks || 1);
    const trackH = stacks >= 2 ? 58 : 44;
    const pad = 4;
    const slotH = (trackH - pad * 2 - (stacks > 1 ? 3 : 0)) / stacks;
    // Stitch per stack so Step A|B lines appear inside each parallel chat.
    const byStack = {};
    for (const seg of (ln.segments || [])) {
      const k = String(seg.stack || 0);
      if (!byStack[k]) byStack[k] = [];
      byStack[k].push(seg);
    }
    const segs = Object.keys(byStack).flatMap(k => {
      const stitched = stitchAbuttingSegments(byStack[k]);
      return stitched.map(seg => {
        const stack = Number(seg.stack || 0);
        const top = pad + stack * (slotH + (stacks > 1 ? 3 : 0));
        return renderChip(seg, {
          showTxt: Number(seg.width_pct) >= 4.5,
          txt: seg.ayah || shortStepLabel(seg.label) || seg.batch,
          top,
          height: slotH,
          batch: seg.batch,
        });
      });
    }).join('');
    return `<div class="gantt-lane">
      <div class="gantt-lane-lab">
        <span class="name" style="color:${c}">${ln.profile}</span>
        <span class="hint">${ln.ok_segments || 0} ok${ln.fail_segments ? ` · ${ln.fail_segments} fail` : ''}</span>
      </div>
      <div class="gantt-track stacks-${stacks}" style="height:${trackH}px">${segs}</div>
      <div class="gantt-meta">${fmtWallMin(ln.active_s)}</div>
    </div>`;
  }).join('');

  panel.innerHTML = `<div class="gantt-legend">${legend}</div>
    <div class="gantt-block-title">BY BATCH — one bar per batch, split into account chunks</div>
    <div class="gantt-axis">${axis}</div>
    ${batchBody || '<div class="gantt-empty">No batch rows</div>'}
    <div class="gantt-block-title" style="margin-top:18px;">BY ACCOUNT — swimlanes (parallel chats stacked)</div>
    <div class="gantt-axis">${axis}</div>
    ${laneBody || '<div class="gantt-empty">No account lanes</div>'}`;
}

function renderBatches(data) {
  const container = document.getElementById('batches-container');
  const batches = data.batches || [];
  if (currentGrouping === 'ayah') {
    container.innerHTML = `<div class="batches-grid">${batches.map(renderBatchCard).join('')}</div>`;
    return;
  }

  // One batch → one card, grouped by final status owner (not duplicated across workers).
  // Handoffs are shown on the chunked batch Gantt + "chunks: a → b" note on the card.
  const byAcc = {};
  const accStats = (data.surahTotals && data.surahTotals.by_account) || {};
  for (const b of batches) {
    const key = b.status_profile || b.profile || 'unassigned';
    if (!byAcc[key]) byAcc[key] = [];
    byAcc[key].push(b);
  }
  const order = ['qoun', 'abod', 'smallbusiness', 'quyn', 'default', 'unassigned'];
  const keys = [...order.filter(k => byAcc[k]), ...Object.keys(byAcc).filter(k => !order.includes(k))];

  container.innerHTML = keys.map(prof => {
    const list = byAcc[prof] || [];
    const st = accStats[prof] || {};
    const doneCnt = list.filter(x => x.pct === 100).length;
    return `<div class="account-group-box">
      <div class="account-group-header">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
          <span class="profile-tag" style="font-size:13px;padding:4px 10px;">Account: ${prof}</span>
          <span style="font-size:13px;font-weight:700;">${doneCnt}/${list.length} Batches Handled</span>
          <span style="font-size:12px;color:var(--muted);">(${list.map(x => x.batch).join(', ')})</span>
        </div>
        <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:#cbd5e1;">
          <span>Stops: <strong>${fmtNum(st.extractions ?? 0)}</strong></span>
          <span>Demos: <strong>${fmtNum(st.demos ?? 0)}</strong></span>
          <span>Turns: <strong>${st.turns_ok ?? 0} ok / ${st.turns_fail ?? 0} fail</strong></span>
          <span style="color:#a5f3fc;">Quota Used: <strong>${fmtNum(st.quota_credits_used ?? 0)} cr</strong></span>
          <span style="color:#a5f3fc;">Tokens: <strong>${fmtNum(st.total_tokens ?? 0)}</strong></span>
          <span style="color:#4ade80;">Est. Cost: <strong>$${Number(st.cost_usd ?? 0).toFixed(2)} USD</strong></span>
          <span>Total Time: <strong>${st.total_min ?? 0}m</strong></span>
        </div>
      </div>
      <div class="batches-grid">${list.map(renderBatchCard).join('')}</div>
    </div>`;
  }).join('');
}

function render(data) {
  lastState = data;
  document.getElementById('main-title').textContent =
    `Waqf & Ibtida — Surah ${data.selectedSurah} (${data.surahNameAr}) Parallel Argon High Dashboard`;
  const alive = data.quotas && data.quotas.runnerAlive;
  document.getElementById('clock').textContent =
    `Scan: ${data.now_12h} · ${alive ? 'Runner ACTIVE' : 'Runner IDLE'}`;

  // Surah selector buttons
  const tabsEl = document.getElementById('surah-tabs');
  tabsEl.innerHTML = `<span style="font-size:12px;color:var(--muted);margin-right:4px;">Select Surah:</span>` +
    (data.availableSurahs || []).map(s => {
      const act = String(s.surah) === String(data.selectedSurah) ? 'active' : '';
      return `<button class="tab-btn ${act}" onclick="setSurah(${s.surah})">
        Surah ${s.surah} (${s.name_ar}) · ${s.batches_done}/${s.batches_total} · ${fmtNum(s.quota_credits_used)}cr · $${Number(s.estimated_cost_usd).toFixed(2)}
      </button>`;
    }).join('');

  const c = data.counts;
  const st = data.surahTotals || {};
  const overallPct = Math.round(
    data.batches.reduce((acc, b) => acc + (b.pct || 0), 0) / Math.max(1, data.totalBatches)
  );

  const accSummaryInline = Object.entries(st.by_account || {}).map(([p, g]) =>
    `<code>${p}</code>: ${g.batches_count}b (${fmtNum(g.quota_credits_used)}cr · $${Number(g.cost_usd).toFixed(2)})`
  ).join(' · ');

  document.getElementById('summary-cards').innerHTML = `
    <div class="card">
      <div class="card-title">Surah ${data.selectedSurah} (${data.surahNameAr}) Progress</div>
      <div class="card-val">${c.done} / ${data.totalBatches} Batches (${overallPct}%)</div>
      <div class="bar"><div style="width:${overallPct}%;background:var(--green);"></div></div>
      <div class="card-sub">Stops: <strong>${fmtNum(st.extractions_total)}</strong> · Demos: <strong>${fmtNum(st.demos_total)}</strong></div>
    </div>
    <div class="card">
      <div class="card-title">Quota Used (Surah ${data.selectedSurah} Run)</div>
      <div class="card-val" style="color:#38bdf8;">${fmtNum(st.quota_credits_used)} credits</div>
      <div class="card-sub">
        = <strong>${st.quota_burst_windows_equiv}x</strong> 2,400 5h-reset windows<br/>
        = <strong>${st.quota_macro_pct_equiv}%</strong> of 48,384 weekly Pro pool
      </div>
    </div>
    <div class="card">
      <div class="card-title">Estimated Tokens (Surah ${data.selectedSurah})</div>
      <div class="card-val" style="color:#c084fc;">${fmtNum(st.total_tokens)} tok</div>
      <div class="card-sub">
        New In: <strong>${((st.new_input_tokens||0)/1000).toFixed(1)}k</strong> ·
        Same-Chat Ctx: <strong>${((st.context_input_tokens||0)/1000).toFixed(1)}k</strong><br/>
        Thinking: <strong>${((st.thinking_tokens||0)/1000).toFixed(1)}k</strong> ·
        Output: <strong>${((st.output_tokens||0)/1000).toFixed(1)}k</strong>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Estimated Equivalent API Cost</div>
      <div class="card-val" style="color:var(--green);">$${Number(st.estimated_cost_usd || 0).toFixed(2)} USD</div>
      <div class="card-sub">${accSummaryInline || '—'}</div>
    </div>
  `;

  const q = data.quotas || {};
  const rpcAt = q.lastRpcPollAt_12h ? ` · last RPC poll ${q.lastRpcPollAt_12h}` : '';
  document.getElementById('quota-updated').textContent =
    q.updatedAt_12h ? `Source: ${q.source} · updated ${q.updatedAt_12h}${rpcAt}${q.error ? ' · Note: ' + q.error : ''}` : 'Loading quotas…';

  const qProfiles = q.profiles || {};
  const pNames = Object.keys(qProfiles);
  document.getElementById('quotas-grid').innerHTML = pNames.map(p => {
    const info = qProfiles[p];
    const argonOk = info.argon_high_ok;
    const status = info.status || 'ready';
    const tierBadge = argonOk === false
      ? `<span class="badge error" title="Chrome mode picker detected Auto/non-Pro tier">NON-PRO (AUTO)</span>`
      : (argonOk === true
          ? `<span class="badge done">PRO · 4 ARGON HIGH</span>`
          : `<span class="badge queued">PRO CHECK</span>`);

    let statusBadge = '';
    const activeSlots = Number(info.active_slots || (Array.isArray(info.active_batches) ? info.active_batches.length : 0));
    const maxSlots = Number(info.max_slots || 2);
    if (status === 'active_busy' || activeSlots > 0) {
      statusBadge = `<span class="badge running">BUSY (${activeSlots}/${maxSlots} slots)${info.current_batch ? ' · ' + info.current_batch : ''}</span>`;
    } else if (status === 'low_quota') {
      statusBadge = `<span class="badge warn">LOW QUOTA</span>`;
    } else if (status === 'non_pro_downgraded') {
      statusBadge = `<span class="badge error">RETIRED (NON-PRO)</span>`;
    } else if (status.startsWith('retired_')) {
      statusBadge = `<span class="badge warn">${status.replace('retired_', '')}</span>`;
    } else if (argonOk === true) {
      statusBadge = `<span class="badge queued" title="Up to ${maxSlots} simultaneous chats supported on this account">0/${maxSlots} SLOTS BUSY</span>`;
    }

    const poolsObj = info.pools || {};
    let poolKeys = Object.keys(poolsObj);
    if (!poolKeys.length) {
      poolKeys = ['_binding'];
      poolsObj._binding = {
        label: (info.plan_limit_info || {}).short_label || 'Plan',
        limit: info.limit,
        remaining: info.remaining,
        used_pct: info.used_pct,
        left_pct: info.left_pct,
        reset_in_s: info.reset_in_s,
        reset_in_human: info.reset_in_human,
        reset_at_12h: info.reset_at_12h,
        binding: true,
        known: info.remaining != null,
      };
    }
    const order = ['burst_5h', 'weekly', 'free', 'other'];
    poolKeys = [...order.filter(k => poolsObj[k]), ...poolKeys.filter(k => !order.includes(k))];

    const poolTone = (k) => {
      if (k === 'burst_5h') return { cls: 'burst', base: 'var(--cyan)' };
      if (k === 'weekly') return { cls: 'weekly', base: '#a855f7' };
      if (k === 'free') return { cls: 'free', base: '#94a3b8' };
      return { cls: 'other', base: 'var(--blue)' };
    };
    const fillColor = (leftPct, known, base) => {
      if (!known) return 'var(--muted)';
      if (argonOk === false) return 'var(--red)';
      if (leftPct > 35) return 'var(--green)';
      if (leftPct > 12) return 'var(--amber)';
      return 'var(--red)';
    };
    const windowSecs = (k, lim) => {
      if (k === 'burst_5h' || lim === 2400) return 5 * 3600;
      if (k === 'weekly' || lim === 48384) return 7 * 24 * 3600;
      if (k === 'free' || lim === 12096) return 24 * 3600;
      return 5 * 3600;
    };
    const shortReset = (s) => {
      if (s == null || s === '') return '—';
      const n = Number(s);
      if (!Number.isFinite(n)) return String(s).replace(/^Resets?\s*in:?\s*/i, '');
      const h = Math.floor(n / 3600);
      const m = Math.floor((n % 3600) / 60);
      if (h > 0) return `${h}h${m ? m + 'm' : ''}`;
      if (m > 0) return `${m}m`;
      return `${Math.max(0, Math.floor(n))}s`;
    };

    const ringHtml = (opts) => {
      const {
        cls, pct, color, main, sub, label, meta, bind, small
      } = opts;
      const p = Math.max(0, Math.min(100, Number(pct) || 0));
      return `<div class="ring-wrap ${cls}${small ? ' time' : ''}">
        <div class="ring${small ? ' sm' : ''}" style="--p:${p};--c:${color};">
          <div class="ring-core">
            <span class="ring-main">${main}</span>
            <span class="ring-sub">${sub || ''}</span>
          </div>
        </div>
        <div class="ring-label">${label}${bind ? ' <span class="badge running" style="font-size:9px;padding:1px 5px;">NOW</span>' : ''}</div>
        <div class="ring-meta">${meta || ''}</div>
      </div>`;
    };

    const poolRings = poolKeys.map(k => {
      const pool = poolsObj[k] || {};
      const rem = pool.remaining;
      const lim = pool.limit;
      const known = !!pool.known && rem != null;
      const usedPct = pool.used_pct ?? 0;
      const leftPct = pool.left_pct ?? (known ? Math.max(0, 100 - usedPct) : 0);
      const tone = poolTone(k);
      const col = fillColor(leftPct, known, tone.base);
      const remTxt = known ? fmtNum(rem) : '—';
      const limTxt = lim ? fmtNum(lim) : '?';
      const pctTxt = known ? `${Math.round(leftPct)}% left` : 'not seen';
      // Live countdown from reset_at so the ring moves every dashboard tick.
      let resetS = pool.reset_in_s != null ? Number(pool.reset_in_s) : null;
      if (pool.reset_at) {
        const tReset = Date.parse(pool.reset_at);
        if (Number.isFinite(tReset)) {
          resetS = Math.max(0, Math.round((tReset - Date.now()) / 1000));
        }
      }
      const elapsed = !!pool.reset_elapsed || (resetS === 0 && !!pool.reset_at);
      const win = windowSecs(k, lim);
      const timePct = (resetS != null && win > 0)
        ? Math.max(0, Math.min(100, 100 * resetS / win))
        : 0;
      const timeKnown = resetS != null && Number.isFinite(resetS);
      const timeCol = !timeKnown ? 'var(--muted)'
        : (elapsed ? 'var(--red)' : (timePct > 35 ? 'var(--amber)' : (timePct > 12 ? '#fb923c' : 'var(--red)')));
      const creditMeta = pool.remaining_stale
        ? `${pctTxt} · stale after reset`
        : pctTxt;
      const creditRing = ringHtml({
        cls: tone.cls,
        pct: known ? leftPct : 0,
        color: col,
        main: remTxt,
        sub: `/ ${limTxt}`,
        label: pool.label || k,
        meta: creditMeta,
        bind: !!pool.binding,
        small: false,
      });
      // Reset timer from qpEbW is always the 5h window — never show it on weekly.
      const showTime = (k === 'burst_5h' || k === 'free' || k === '_binding');
      if (!showTime) return creditRing;
      const timeRing = ringHtml({
        cls: 'time',
        pct: timeKnown && !elapsed ? timePct : 0,
        color: timeCol,
        main: !timeKnown ? '—' : (elapsed ? 'due' : shortReset(resetS)),
        sub: pool.reset_at_12h || 'reset',
        label: 'Time',
        meta: !timeKnown ? 'no timer' : (elapsed ? (pool.binding ? 'reset now' : 'due · rem stale') : 'to reset'),
        bind: false,
        small: true,
      });
      return creditRing + timeRing;
    }).join('');

    const seenAt12h = info.lastSeenAt_12h || '—';

    return `<div class="card" style="${argonOk === false ? 'opacity:0.78;border-color:rgba(239,68,68,0.45);' : ''}">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;flex-wrap:wrap;">
        <span style="font-weight:700;font-size:15px;">${p}</span>
        <div style="display:flex;gap:4px;align-items:center;">${tierBadge}${statusBadge}</div>
      </div>
      <div style="font-size:11px;color:var(--muted);margin-top:2px;">${info.email || ''}</div>
      <div class="quota-rings">${poolRings}</div>
      <div style="display:flex;justify-content:flex-end;color:var(--muted);font-size:11px;margin-top:8px;">
        <span>Seen: ${seenAt12h}</span>
      </div>
    </div>`;
  }).join('');

  document.getElementById('batches-sub').textContent =
    `Surah ${data.selectedSurah} (${data.surahNameAr}) · ${c.done}/${data.totalBatches} validated · ${fmtNum(st.quota_credits_used)} credits · ${fmtNum(st.total_tokens)} tokens · $${Number(st.estimated_cost_usd||0).toFixed(2)} USD`;

  renderGantt(data);
  renderBatches(data);
  document.getElementById('log-box').textContent = (data.logTail || []).join('\n') || '(empty)';
}

async function tick() {
  try {
    const r = await fetch(`/api/state?surah=${encodeURIComponent(currentSurah)}`, { cache: 'no-store' });
    const data = await r.json();
    render(data);
  } catch (e) {
    document.getElementById('clock').textContent = 'Connection lost — retrying…';
  }
}
tick();
setInterval(tick, 2500);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if path == "/api/state":
            surah_raw = (qs.get("surah") or ["6"])[0]
            try:
                surah_num = int(surah_raw)
            except ValueError:
                surah_num = 6
            body = json.dumps(collect_state(surah=surah_num), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    t = threading.Thread(target=_quota_poller, daemon=True)
    t.start()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Dashboard listening on http://{HOST}:{PORT}/ (12-hour AM/PM mode)", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
