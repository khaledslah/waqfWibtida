#!/usr/bin/env python3
"""Probe Thinking/Pro remaining+limit, reset time, and dynamic Argon High capability for profiles.

Safe to run while the parallel runner is active:
- Loads auth state from disk without firing raw httpx GET scrapes to gemini.google.com/app
  (which otherwise trigger Google /sorry/ 429s when run across 5 accounts).
- Serializes any on-demand Chrome daemon launches with DAEMON_START_LOCK and verifies
  the signed-in Chrome email matches the profile email.
- For busy profiles (currently running a batch in surah6_parallel_status.json), uses
  passive read-only cookie + DOM inspection without clicking the mode picker.
- For idle profiles, dynamically tests selecting 4 Argon High in the mode picker to
  detect non-Pro / downgraded accounts automatically.
- Persists results to quotas_live.json for the live dashboard.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

sys.stdout.reconfigure(encoding="utf-8")

from gemini_web_mcp_cli.core.browser_auth import get_browser_auth_status_for_port
from gemini_web_mcp_cli.core.cdp import find_existing_gemcli_chrome, run_js
from gemini_web_mcp_cli.core.chrome_manager import check_daemon_health, same_chrome_profile_path
from gemini_web_mcp_cli.core.client import GeminiClient
from gemini_web_mcp_cli.core.constants import GEMINI_HEADERS, MODELS
from gemini_web_mcp_cli.core.rpc import RPCTransport
from gemini_web_mcp_cli.core.token_factory import SET_MODEL_PICKER_JS
from gemini_web_mcp_cli.services.limits import LimitsService

SCRATCH = Path(__file__).resolve().parent
QUOTAS_LIVE_FILE = SCRATCH / "quotas_live.json"
STATUS_FILE = SCRATCH / "surah6_parallel_status.json"
DEFAULT_PROFILES = ["default", "qoun", "abod", "smallbusiness", "niyyah"]
DAEMON_START_LOCK = asyncio.Lock()

PASSIVE_PICKER_CHECK_JS = """
(() => {
    const email = (window.WIZ_global_data && window.WIZ_global_data.oPEP7c) ? String(window.WIZ_global_data.oPEP7c).toLowerCase() : '';
    const host = document.querySelector('[data-test-id="bard-mode-menu-button"]');
    const btn = host ? (host.tagName === 'BUTTON' ? host : (host.querySelector('button') || host)) : null;
    const label = btn ? (btn.innerText || '').trim().replace(/\\s+/g, ' ') : '';
    const autoOpt = document.querySelector('[data-test-id="bard-mode-option-cf41b0e0dd7d53e5"]');
    return JSON.stringify({
        email: email,
        pickerLabel: label,
        hasAutoOptionInDom: !!autoOpt
    });
})()
"""


def fmt_duration(seconds: int | float | None) -> str:
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


def init_client_from_disk(client: GeminiClient) -> None:
    """Initialize GeminiClient transport from disk auth.json without raw httpx /app scrape."""
    auth_state = client.auth_manager.load()
    client._http_client = httpx.AsyncClient(
        http2=True,
        timeout=client._httpx_timeout(),
        proxy=client.proxy,
        follow_redirects=True,
        headers=GEMINI_HEADERS,
        cookies=auth_state.cookies,
    )
    client._transport = RPCTransport(
        client=client._http_client,
        access_token=auth_state.tokens.snlm0e,
        build_label=auth_state.tokens.cfb2h,
        session_id=auth_state.tokens.fdrfje,
    )
    if auth_state.cookies:
        client._browser_cookies = dict(auth_state.cookies)
    client._initialized = True
    client.last_init_timing = {"refresh_s": 0.0, "recover_s": 0.0, "refresh_failed": False, "total_s": 0.001}


def get_busy_profiles() -> set[str]:
    """Return profiles currently executing step_a or step_b in surah6_parallel_status.json."""
    busy: set[str] = set()
    if not STATUS_FILE.exists():
        return busy
    try:
        data = json.loads(STATUS_FILE.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            for entry in data.values():
                if isinstance(entry, dict) and entry.get("stage") in ("step_a", "step_b"):
                    prof = entry.get("profile")
                    if prof:
                        busy.add(str(prof))
    except Exception:
        pass
    return busy


def find_profile_daemon_port(profile: str, client: GeminiClient) -> int | None:
    """Return the Chrome CDP port for this specific profile if running."""
    resolved = client.auth_manager.resolved_profile_name
    expected_path = client.profile_manager.get_chrome_profile_path(resolved)
    info, st = check_daemon_health(resolved)
    if st == "running" and info and (
        info.profile_name == resolved
        or same_chrome_profile_path(info.chrome_profile_path, expected_path)
    ):
        return info.port
    found_port, _ = find_existing_gemcli_chrome(profile_name=resolved)
    return found_port


async def ensure_profile_chrome_and_cookies(
    profile: str,
    client: GeminiClient,
    allow_launch: bool = True,
) -> int | None:
    """Extract live cookies from the profile's Chrome daemon (starting it under lock if needed)."""
    expected_email = (client.auth_manager.state.email or "").lower()
    port = find_profile_daemon_port(profile, client)

    def _try_extract(p: int) -> bool:
        auth_st = get_browser_auth_status_for_port(p)
        if not auth_st.is_authenticated or not auth_st.cookies:
            return False
        if expected_email and auth_st.ws_url:
            try:
                raw = run_js(auth_st.ws_url, PASSIVE_PICKER_CHECK_JS)
                parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
                chrome_email = str(parsed.get("email") or "").lower()
                if chrome_email and chrome_email != expected_email:
                    return False
            except Exception:
                pass
        client._browser_cookies = auth_st.cookies
        client._raw_browser_cookies = auth_st.raw_cookies
        client._browser_access_token = auth_st.access_token
        return True

    if port and await asyncio.to_thread(_try_extract, port):
        return port

    if not allow_launch or not client.auth_manager.state.chrome_profile_path:
        return None

    from gemini_web_mcp_cli.core.daemon_idle import start_on_demand

    async with DAEMON_START_LOCK:
        await asyncio.to_thread(
            start_on_demand,
            client.auth_manager.resolved_profile_name,
            client.auth_manager.state.chrome_profile_path,
        )
    port = find_profile_daemon_port(profile, client)
    if port and await asyncio.to_thread(_try_extract, port):
        return port
    return port


def check_picker_capability_sync(
    profile: str,
    client: GeminiClient,
    port: int | None,
    allow_active_click: bool = True,
) -> dict[str, Any]:
    """Dynamically determine whether this profile has 4 Argon High (Pro) access."""
    if not port:
        return {
            "argon_high_ok": None,
            "tier": "unknown_no_chrome",
            "picker_result": "no_port",
            "picker_label": None,
        }

    expected_email = (client.auth_manager.state.email or "").lower()
    auth_st = get_browser_auth_status_for_port(port)
    if not auth_st.is_authenticated or not auth_st.ws_url:
        return {
            "argon_high_ok": False,
            "tier": "unauthenticated",
            "picker_result": "unauthenticated",
            "picker_label": None,
        }

    try:
        passive_raw = run_js(auth_st.ws_url, PASSIVE_PICKER_CHECK_JS)
        passive = json.loads(passive_raw) if isinstance(passive_raw, str) else (passive_raw or {})
        chrome_email = str(passive.get("email") or "").lower()
        if expected_email and chrome_email and chrome_email != expected_email:
            return {
                "argon_high_ok": None,
                "tier": "email_mismatch",
                "picker_result": f"mismatch:{chrome_email}",
                "picker_label": None,
            }
        lbl = str(passive.get("pickerLabel") or "")
        if "Auto" in lbl or passive.get("hasAutoOptionInDom"):
            return {
                "argon_high_ok": False,
                "tier": "non_pro_downgraded",
                "picker_result": "auto_tier_detected",
                "picker_label": lbl,
            }
        if not allow_active_click:
            return {
                "argon_high_ok": True,
                "tier": "pro_argon_high",
                "picker_result": "passive_ok",
                "picker_label": lbl or "Argon High",
            }

        model = MODELS["argon"].with_thinking_level("high")
        js = SET_MODEL_PICKER_JS.replace("{hash}", model.hash).replace("{level}", model.thinking_label)
        res = run_js(auth_st.ws_url, js)
        passive_raw2 = run_js(auth_st.ws_url, PASSIVE_PICKER_CHECK_JS)
        passive2 = json.loads(passive_raw2) if isinstance(passive_raw2, str) else (passive_raw2 or {})
        lbl2 = str(passive2.get("pickerLabel") or lbl)
        ok = res == "set" and "Auto" not in lbl2
        return {
            "argon_high_ok": ok,
            "tier": "pro_argon_high" if ok else "non_pro_downgraded",
            "picker_result": str(res),
            "picker_label": lbl2,
        }
    except Exception as exc:
        return {
            "argon_high_ok": None,
            "tier": "error",
            "picker_result": f"{type(exc).__name__}: {exc}",
            "picker_label": None,
        }


async def probe_one(
    profile: str,
    busy_profiles: set[str],
    check_picker: bool = True,
    allow_launch: bool = True,
    timeout_s: float = 45.0,
) -> dict[str, Any]:
    t0 = time.monotonic()
    client = GeminiClient(profile_name=profile, timeout=timeout_s)
    is_busy = profile in busy_profiles
    try:
        init_client_from_disk(client)
        port = await ensure_profile_chrome_and_cookies(
            profile, client, allow_launch=(allow_launch and not is_busy)
        )
        cap_info: dict[str, Any] = {
            "argon_high_ok": None,
            "tier": "unknown",
            "picker_result": None,
            "picker_label": None,
        }
        if check_picker and port:
            cap_info = await asyncio.to_thread(
                check_picker_capability_sync,
                profile,
                client,
                port,
                allow_active_click=(not is_busy),
            )
        try:
            lims = await asyncio.wait_for(LimitsService(client).get_limits(), timeout=20.0)
            rpc_err: str | None = None
        except Exception as lim_exc:
            lims = []
            rpc_err = f"{type(lim_exc).__name__}: {lim_exc}"

        preferred = []
        features_summary = []
        for q in lims:
            name = str(q.name or "")
            local_dt = q.reset_at.astimezone()
            local_reset = local_dt.isoformat(timespec="seconds")
            local_reset_12h = local_dt.strftime("%I:%M %p")
            reset_in = int(round(q.reset_in_seconds))
            if "Think" in name or name.startswith("Pro") or "Prompt" in name or q.feature_id in (3, 9, 15, 16):
                features_summary.append(
                    {
                        "feature_id": q.feature_id,
                        "name": name,
                        "remaining": int(q.remaining),
                        "limit": int(q.limit),
                        "used_pct": int(q.used),
                        "reset_in_s": reset_in,
                        "reset_in_human": fmt_duration(reset_in),
                        "reset_at": local_reset,
                        "reset_at_12h": local_reset_12h,
                    }
                )
            if name == "Thinking Prompts" or "Thinking" in name:
                preferred.append((0, q))
            elif name == "Pro Prompts" or name.startswith("Pro"):
                preferred.append((1, q))
        preferred.sort(key=lambda x: (x[1].remaining, x[0]))
        primary = preferred[0][1] if preferred else None

        rem = int(primary.remaining) if primary else None
        lim = int(primary.limit) if primary else None
        used_pct = (
            round(100.0 * (lim - rem) / lim, 1)
            if (primary and lim and lim > 0 and rem is not None)
            else (int(primary.used) if primary else None)
        )
        left_pct = round(100.0 - used_pct, 1) if used_pct is not None else None
        reset_in_s = int(round(primary.reset_in_seconds)) if primary else None
        reset_at_dt = primary.reset_at.astimezone() if primary else None
        reset_at_local = reset_at_dt.isoformat(timespec="seconds") if reset_at_dt else None
        reset_at_12h = reset_at_dt.strftime("%I:%M %p") if reset_at_dt else None

        argon_ok = cap_info.get("argon_high_ok")
        is_429 = bool(rpc_err and ("429" in rpc_err or "/sorry/" in rpc_err))
        if argon_ok is False:
            status_label = "non_pro_downgraded"
        elif is_429 and primary is None:
            status_label = "cooldown_429"
        elif rem is not None and rem < 240:
            status_label = "low_quota"
        elif is_busy:
            status_label = "active_busy"
        elif argon_ok is True:
            status_label = "ready_pro"
        else:
            status_label = "ready"

        from surah_telemetry_ledger import explain_plan_limit

        now_dt = datetime.now().astimezone()
        res_dict: dict[str, Any] = {
            "profile": profile,
            "email": client.auth_manager.state.email,
            "ok": primary is not None or argon_ok is not None,
            "status": status_label,
            "argon_high_ok": argon_ok,
            "tier": cap_info.get("tier"),
            "picker_result": cap_info.get("picker_result"),
            "picker_label": cap_info.get("picker_label"),
            "name": str(primary.name) if primary else "Thinking Prompts",
            "features": features_summary,
            "rpc_error": rpc_err,
            "elapsed_s": round(time.monotonic() - t0, 2),
            "lastSeenAt": now_dt.isoformat(timespec="seconds"),
            "lastSeenAt_12h": now_dt.strftime("%I:%M:%S %p"),
        }
        if primary is not None:
            res_dict.update(
                {
                    "remaining": rem,
                    "limit": lim,
                    "plan_limit_info": explain_plan_limit(lim, argon_ok),
                    "used_pct": used_pct,
                    "left_pct": left_pct,
                    "reset_in_s": reset_in_s,
                    "reset_in_human": fmt_duration(reset_in_s),
                    "reset_at": reset_at_local,
                    "reset_at_12h": reset_at_12h,
                }
            )
        return res_dict
    except Exception as exc:
        now_dt = datetime.now().astimezone()
        return {
            "profile": profile,
            "ok": False,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_s": round(time.monotonic() - t0, 2),
            "lastSeenAt": now_dt.isoformat(timespec="seconds"),
            "lastSeenAt_12h": now_dt.strftime("%I:%M:%S %p"),
        }
    finally:
        try:
            await client.close()
        except Exception:
            pass


def save_quotas_live(results: list[dict[str, Any]]) -> None:
    from surah_telemetry_ledger import explain_plan_limit, fmt_iso_to_12h

    existing: dict[str, Any] = {}
    if QUOTAS_LIVE_FILE.exists():
        try:
            existing = json.loads(QUOTAS_LIVE_FILE.read_text(encoding="utf-8-sig"))
        except Exception:
            existing = {}
    prof_map = existing.get("profiles") if isinstance(existing.get("profiles"), dict) else {}
    for r in results:
        p = r["profile"]
        prev = prof_map.get(p, {}) if isinstance(prof_map.get(p), dict) else {}
        if not r.get("ok") and prev.get("ok"):
            merged = {**prev, "lastSeenAt": r.get("lastSeenAt"), "lastSeenAt_12h": r.get("lastSeenAt_12h")}
        else:
            merged = {**prev, **{k: v for k, v in r.items() if v is not None}}
        if r.get("argon_high_ok") is None and prev.get("argon_high_ok") is not None:
            merged["argon_high_ok"] = prev.get("argon_high_ok")
            merged["tier"] = prev.get("tier")
            merged["picker_result"] = prev.get("picker_result")
            merged["picker_label"] = prev.get("picker_label")
            if merged.get("argon_high_ok") is False:
                merged["status"] = "non_pro_downgraded"
            elif merged.get("status") == "ready" and merged.get("argon_high_ok") is True:
                merged["status"] = "ready_pro"
        if r.get("ok") and r.get("remaining") is not None:
            start_rem = prev.get("start_remaining")
            if start_rem is None or int(start_rem) < int(r["remaining"]):
                start_rem = r["remaining"]
            merged["start_remaining"] = start_rem
            merged["from"] = "live-rpc"
        if merged.get("reset_at") and not merged.get("reset_at_12h"):
            merged["reset_at_12h"] = fmt_iso_to_12h(merged.get("reset_at"), include_seconds=False)
        if merged.get("limit") is not None:
            merged["plan_limit_info"] = explain_plan_limit(merged.get("limit"), merged.get("argon_high_ok"))
        prof_map[p] = merged
    now_dt = datetime.now().astimezone()
    payload = {
        "updatedAt": now_dt.isoformat(timespec="seconds"),
        "updatedAt_12h": now_dt.strftime("%I:%M:%S %p"),
        "source": "LimitsService (qpEbW) + dynamic picker check",
        "profiles": prof_map,
    }
    QUOTAS_LIVE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def main() -> None:
    ap = argparse.ArgumentParser(description="Probe Gemini profile quotas and dynamic 4 Argon High status")
    ap.add_argument("profiles", nargs="*", help="Profiles to probe (default: all 5)")
    ap.add_argument("--no-picker", action="store_true", help="Skip dynamic mode picker check")
    ap.add_argument("--no-launch", action="store_true", help="Do not launch Chrome daemons if not already running")
    ap.add_argument("--json", action="store_true", help="Print JSON output")
    args = ap.parse_args()

    profiles = [p for p in args.profiles if p] or list(DEFAULT_PROFILES)
    busy = get_busy_profiles()
    results = await asyncio.gather(
        *(
            probe_one(
                p,
                busy_profiles=busy,
                check_picker=(not args.no_picker),
                allow_launch=(not args.no_launch),
            )
            for p in profiles
        )
    )
    save_quotas_live(list(results))

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    from surah_telemetry_ledger import QUOTAS_LIVE_FILE as _QF
    saved = json.loads(QUOTAS_LIVE_FILE.read_text(encoding="utf-8"))["profiles"]
    for p in profiles:
        r = saved.get(p, {})
        if not r.get("ok"):
            print(f"\n=== {p} ERR ({r.get('elapsed_s')}s): {r.get('error')} ===")
            continue
        tier_badge = (
            "PRO (4 Argon High OK)"
            if r.get("argon_high_ok") is True
            else (
                "NON-PRO / DOWNGRADED (picker=" + str(r.get("picker_result")) + ")"
                if r.get("argon_high_ok") is False
                else "TIER UNKNOWN"
            )
        )
        pl_info = r.get("plan_limit_info") or {}
        print(
            f"\n=== {p} ({r.get('email')}) [{r.get('status')}] · {tier_badge} · {r.get('lastSeenAt_12h')} ==="
        )
        if pl_info.get("bucket_type"):
            print(f"  Plan Bucket: {pl_info['bucket_type']} — {pl_info.get('short_label')}")
        if r.get("rpc_error") and not r.get("features"):
            print(f"  qpEbW quota RPC note: {str(r.get('rpc_error'))[:140]}")
        for f in r.get("features", []):
            reset_12h = f.get("reset_at_12h") or f.get("reset_at")
            print(
                f"  {f['name']:18s}: remaining={f['remaining']:,}/{f['limit']:,} "
                f"used%={f['used_pct']}% reset_in={fmt_duration(f['reset_in_s'])} "
                f"(at {reset_12h})"
            )


if __name__ == "__main__":
    asyncio.run(main())
