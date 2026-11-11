#!/usr/bin/env python3
"""Generalized Live Surah Parallel-Runner & Telemetry Dashboard (auto-refreshing browser UI).

Features:
- Generalized for any Surah (`?surah=6`, `?surah=5`, `?surah=4`, `?surah=3`, etc.)
- 12-hour AM/PM time formatting everywhere (live clock, reset times, step timestamps)
- Displays all 5 accounts (default, qoun, abod, smallbusiness, niyyah) with:
  - Dynamic Pro / 4 Argon High capability badge (detected from Chrome mode picker)
  - Plan Limit bucket explanation (2,400 = 5h Burst Cap vs 48,384 = Multi-Day Macro Pool vs 12,096 = Free/Auto Pool)
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
from datetime import datetime
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
    fmt_12h,
    fmt_iso_to_12h,
)

PROTO = Path(r"D:\AI_Projects\waqfWibtida2\data\llm_prototype")
QUOTAS_LIVE_FILE = SCRATCH / "quotas_live.json"
TURNS_FILE = SCRATCH / "turns.jsonl"
EVENTS_FILE = SCRATCH / "timing_events.jsonl"
LOG_FILE = SCRATCH / "surah6_launch.log"
PREV_LOG_FILE = SCRATCH / "surah6_launch.prev.log"
HOST = "127.0.0.1"
PORT = 8787

ALL_PROFILES = ["default", "qoun", "abod", "smallbusiness", "niyyah"]

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
        ordered[p] = entry
    return ordered


def _get_or_refresh_ledger() -> dict[str, Any]:
    turns_m = TURNS_FILE.stat().st_mtime if TURNS_FILE.exists() else 0.0
    events_m = EVENTS_FILE.stat().st_mtime if EVENTS_FILE.exists() else 0.0
    latest_m = max(turns_m, events_m)
    if not _ledger_cache["data"] or latest_m > _ledger_cache["mtime"] or not LEDGER_FILE.exists():
        try:
            data = build_all_surahs_ledger()
            _ledger_cache["data"] = data
            _ledger_cache["mtime"] = max(latest_m, time.time())
        except Exception:
            _ledger_cache["data"] = _read_json(LEDGER_FILE)
    return _ledger_cache["data"]


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

    s_data = surahs_map.get(str(surah))
    if not s_data and surahs_map:
        first_key = sorted(surahs_map.keys(), key=int, reverse=True)[0]
        surah = int(first_key)
        s_data = surahs_map[first_key]
    s_data = s_data or {}

    batches_dict = s_data.get("batches") or {}
    batches_out: list[dict[str, Any]] = []
    counts = {"done": 0, "running": 0, "queued": 0, "error": 0}

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

        batches_out.append(
            {
                **b,
                "pct": pct,
                "stageLabel": stage_label,
                "lastStep": steps[-1] if steps else None,
            }
        )

    log_tail: list[str] = []
    if LOG_FILE.exists():
        try:
            raw_lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-35:]
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
</style>
</head>
<body>
  <header>
    <div>
      <h1 id="main-title">Waqf &amp; Ibtida — Surah 6 (الأنعام) Parallel Argon High Dashboard</h1>
      <div class="sub">5-Account Dynamic Pool (<code>default</code> · <code>qoun</code> · <code>abod</code> · <code>smallbusiness</code> · <code>niyyah</code>) · 12-Hour AM/PM Clock · Quota, Tokens &amp; Cost Ledger</div>
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
    &nbsp;&nbsp;1. <strong><code>2,400</code> = 5-Hour Rolling Burst Cap</strong> (~20 Argon High turns @ 120 credits/turn; 1 turn = 5% of burst window). Shown once an account has used ≥15–20% of its 5h window.<br/>
    &nbsp;&nbsp;2. <strong><code>48,384</code> = Multi-Day Pro Macro Pool</strong> (~403 Argon High turns @ 120 credits/turn). Shown when the account's 5-hour burst window has freshly reset (0% used) so the macro pool has the higher % used.<br/>
    &nbsp;&nbsp;3. <strong><code>12,096</code> = Free / Auto Tier Pool</strong> (seen on <code>default</code>, which dynamically tested as lacking <code>4 Argon High</code> in the Chrome mode picker).
  </div>

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

  return `<div class="batch-card ${cls}">
    <div class="batch-head">
      <div>
        <span class="batch-id">${b.batch}</span>
        <span style="color:var(--muted);font-size:12px;margin-left:6px;">Ayahs ${b.ayahRange}</span>
      </div>
      <div style="display:flex;gap:6px;align-items:center;">
        ${b.profile ? `<span class="profile-tag">${b.profile}</span>` : ''}
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

function renderBatches(data) {
  const container = document.getElementById('batches-container');
  const batches = data.batches || [];
  if (currentGrouping === 'ayah') {
    container.innerHTML = `<div class="batches-grid">${batches.map(renderBatchCard).join('')}</div>`;
    return;
  }

  // Group batches by account handled
  const byAcc = {};
  const accStats = (data.surahTotals && data.surahTotals.by_account) || {};
  for (const b of batches) {
    const key = b.profile || 'unassigned';
    if (!byAcc[key]) byAcc[key] = [];
    byAcc[key].push(b);
  }
  const order = ['qoun', 'abod', 'smallbusiness', 'niyyah', 'default', 'unassigned'];
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
        = <strong>${st.quota_burst_windows_equiv}x</strong> 2,400-burst windows<br/>
        = <strong>${st.quota_macro_pct_equiv}%</strong> of 48,384 multi-day Pro pool
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
    if (status === 'active_busy') {
      statusBadge = `<span class="badge running">BUSY${info.current_batch ? ' · ' + info.current_batch : ''}</span>`;
    } else if (status === 'low_quota') {
      statusBadge = `<span class="badge warn">LOW QUOTA</span>`;
    } else if (status === 'non_pro_downgraded') {
      statusBadge = `<span class="badge error">RETIRED (NON-PRO)</span>`;
    } else if (status.startsWith('retired_')) {
      statusBadge = `<span class="badge warn">${status.replace('retired_', '')}</span>`;
    }

    const rem = info.remaining;
    const lim = info.limit;
    const usedPct = info.used_pct ?? 0;
    const leftPct = info.left_pct ?? (100 - usedPct);
    const col = argonOk === false ? 'var(--red)' : (leftPct > 35 ? 'var(--green)' : (leftPct > 12 ? 'var(--amber)' : 'var(--red)'));
    const resetHuman = info.reset_in_human || '—';
    const resetAt12h = info.reset_at_12h ? ` (at ${info.reset_at_12h})` : '';
    const plInfo = info.plan_limit_info || {};
    const seenAt12h = info.lastSeenAt_12h || '—';

    return `<div class="card" style="${argonOk === false ? 'opacity:0.78;border-color:rgba(239,68,68,0.45);' : ''}">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;flex-wrap:wrap;">
        <span style="font-weight:700;font-size:15px;">${p}</span>
        <div style="display:flex;gap:4px;align-items:center;">${tierBadge}${statusBadge}</div>
      </div>
      <div style="font-size:11px;color:var(--muted);margin-top:2px;">${info.email || ''}</div>
      <div style="margin-top:7px;display:flex;justify-content:space-between;align-items:baseline;">
        <span style="font-size:20px;font-weight:700;">${rem !== undefined && rem !== null ? fmtNum(rem) : '—'} <span style="font-size:12px;color:var(--muted);font-weight:400;">/ ${lim ? fmtNum(lim) : '?'}</span></span>
        <span style="font-size:12px;font-weight:700;color:${col};">${rem !== undefined && rem !== null ? `${usedPct}% used (${leftPct}% left)` : ''}</span>
      </div>
      <div class="bar"><div style="width:${Math.max(0, Math.min(100, leftPct))}%;background:${col};"></div></div>
      <div style="font-size:11px;color:#93c5fd;margin-top:6px;font-weight:600;">
        Bucket: ${plInfo.bucket_type || 'Plan Pool'} — <span style="font-weight:400;color:var(--muted);">${plInfo.short_label || ''}</span>
      </div>
      <div style="display:flex;justify-content:space-between;color:var(--muted);font-size:11.5px;margin-top:5px;">
        <span>Resets in: <strong style="color:var(--text);">${resetHuman}${resetAt12h}</strong></span>
        <span>Seen: ${seenAt12h}</span>
      </div>
    </div>`;
  }).join('');

  document.getElementById('batches-sub').textContent =
    `Surah ${data.selectedSurah} (${data.surahNameAr}) · ${c.done}/${data.totalBatches} validated · ${fmtNum(st.quota_credits_used)} credits · ${fmtNum(st.total_tokens)} tokens · $${Number(st.estimated_cost_usd||0).toFixed(2)} USD`;

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
