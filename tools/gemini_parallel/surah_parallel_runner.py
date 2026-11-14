from __future__ import annotations

import argparse
import random
import re
import asyncio
import json
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

SCRATCH = Path(
    r"C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch"
)
if str(SCRATCH) not in sys.path:
    sys.path.insert(0, str(SCRATCH))

import waqf_batch_utils as u  # noqa: E402
from surah_telemetry_ledger import (  # noqa: E402
    CREDITS_PER_ARGON_HIGH_TURN,
    SURAH_NAMES_AR,
    build_all_surahs_ledger,
    compute_surah_turn_ledger,
    discover_surah_batches,
    explain_plan_limit,
    fmt_12h,
    fmt_iso_to_12h,
)
from loguru import logger  # noqa: E402
from gemini_web_mcp_cli.core.client import GeminiClient  # noqa: E402

logger.configure(extra={"profile": "main"})
logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="{time:hh:mm:ss.SSS A} | {level: <7} | [{extra[profile]}] {name}:{function}:{line} - {message}",
)
from gemini_web_mcp_cli.core.constants import RPC  # noqa: E402
from gemini_web_mcp_cli.core.exceptions import (  # noqa: E402
    APIError,
    AuthError,
    GeminiReplyError,
    TimeoutError as GeminiTimeoutError,
    TokenFactoryError,
    UsageLimitExceeded,
)
from types import SimpleNamespace  # noqa: E402
from gemini_web_mcp_cli.services.chat import ChatService  # noqa: E402
from gemini_web_mcp_cli.services.limits import LimitsService  # noqa: E402
import coarena_backend as cb  # noqa: E402

SURAH_NUM: int = 6
SURAH_NAME_AR: str = SURAH_NAMES_AR.get(6, "الأنعام")

REMAINING_BATCHES_8_18: list[tuple[str, int, int]] = discover_surah_batches(6) or [
    ("s006_a001_018", 1, 18),
    ("s006_a019_033", 19, 33),
    ("s006_a034_048", 34, 48),
    ("s006_a049_061", 49, 61),
    ("s006_a062_075", 62, 75),
    ("s006_a076_091", 76, 91),
    ("s006_a092_102", 92, 102),
    ("s006_a103_119", 103, 119),
    ("s006_a120_133", 120, 133),
    ("s006_a134_144", 134, 144),
    ("s006_a145_154", 145, 154),
    ("s006_a155_165", 155, 165),
]

BATCH_RANGE_MAP: dict[str, tuple[int, int]] = {bid: (a, b) for bid, a, b in REMAINING_BATCHES_8_18}

# All candidate profiles — dynamic preflight check at worker startup automatically
# detects whether each account has active Pro / 4 Argon High access and quota.
DEFAULT_PROFILES_4: list[str] = ["default", "niyyah", "abod", "smallbusiness", "quyn", "coarena"]
API_PROFILES: frozenset[str] = frozenset({"coarena"})
COARENA_MIN_USD_LEFT: float = 0.25
COARENA_STEP_B_ONLY: bool = True


def _is_api_profile(profile: str) -> bool:
    return profile in API_PROFILES


class _BatchHandoff(Exception):
    """Non-error queue handoff (Step A done -> Step B pool, or Step B-only worker skipped Step A)."""

    def __init__(self, kind: str, reason: str = "") -> None:
        super().__init__(reason or kind)
        self.kind = kind
        self.reason = reason or kind


def _batch_final_exists(batch_id: str) -> bool:
    return (u.PROTO / f"{batch_id}_llm_output.json").exists()


def _batch_step_a_cached(batch_id: str) -> bool:
    return (SCRATCH / f"{batch_id}_extract_only.json").exists()


def _batch_ready_for_step_b(batch_id: str) -> bool:
    return _batch_step_a_cached(batch_id) or _batch_final_exists(batch_id)


def _active_api_profiles() -> list[str]:
    return [p for p in ALIVE_WORKERS if _is_api_profile(p) and p not in RETIRED_PROFILES]


def _eligible_api_worker_exists(batch_id: str) -> bool:
    if not COARENA_STEP_B_ONLY:
        return False
    failed = FAILED_ON.get(batch_id, ())
    return any(p not in failed for p in _active_api_profiles())


def _api_free_slots() -> int:
    active_api = _active_api_profiles()
    if not active_api:
        return 0
    cap = sum(_profile_slot_count(p) for p in active_api)
    busy = sum(len(ACTIVE_BATCHES_BY_PROFILE.get(p, [])) for p in active_api)
    return max(0, cap - busy)


def _browser_step_a_worker_alive() -> bool:
    return any(
        (not _is_api_profile(p)) and (p not in RETIRED_PROFILES or is_recoverable_retire(p))
        for p in ALIVE_WORKERS
    )


def _pick_next_batch_for_worker(
    profile: str,
    q_items: list[str],
    faults: int,
) -> tuple[str | None, list[str], bool, str | None]:
    """Select next batch from queue snapshot respecting Coarena Step-B-only specialization.

    Returns (picked_bid, remaining_items, deferred_wait, exit_reason).
    """
    if not q_items:
        return None, [], False, None

    is_api = _is_api_profile(profile)
    items = list(q_items)

    def _eligible_workers_for(cand_bid: str) -> set[str]:
        failed = FAILED_ON.get(cand_bid, ())
        cand_ready_b = _batch_ready_for_step_b(cand_bid)
        return {
            p
            for p in ALIVE_WORKERS
            if p != profile
            and p not in failed
            and (p not in RETIRED_PROFILES or is_recoverable_retire(p))
            and not (COARENA_STEP_B_ONLY and _is_api_profile(p) and not cand_ready_b)
        }

    def _fallback_failed_only(candidates: list[str]) -> tuple[str | None, list[str], bool, str | None]:
        other_eligible = any(bool(_eligible_workers_for(c)) for c in candidates)
        api_can_take_any = any(_batch_ready_for_step_b(c) for c in candidates) or not COARENA_STEP_B_ONLY
        other_alive_cnt = len(
            {
                p
                for p in ALIVE_WORKERS
                if p != profile and (api_can_take_any or not _is_api_profile(p))
            }
        )
        other_idle_available = other_alive_cnt > IN_FLIGHT_BATCHES
        if other_eligible and (other_idle_available or faults > 0):
            return None, items, True, None
        first_cand = candidates[0]
        items.remove(first_cand)
        return first_cand, items, False, None

    if COARENA_STEP_B_ONLY and is_api:
        ready_items = [c for c in items if _batch_ready_for_step_b(c)]
        if not ready_items:
            if _browser_step_a_worker_alive() or IN_FLIGHT_BATCHES > 0:
                return None, items, True, None
            return None, items, False, "step_b_only_no_browser_workers"
        pick = next((c for c in ready_items if profile not in FAILED_ON.get(c, ())), None)
        if pick is not None:
            items.remove(pick)
            return pick, items, False, None
        return _fallback_failed_only(ready_items)

    # Browser / general worker
    api_active = COARENA_STEP_B_ONLY and bool(_active_api_profiles())
    non_failed = [c for c in items if profile not in FAILED_ON.get(c, ())]
    if non_failed:
        if api_active:
            # Prefer batches that still need Step A so browser workers feed Step B to Coarena.
            need_a = next((c for c in non_failed if not _batch_ready_for_step_b(c)), None)
            if need_a is not None:
                items.remove(need_a)
                return need_a, items, False, None
            # Only Step-B-ready (or cached-final) batches remain: leave up to api_free for Coarena.
            reserved = _api_free_slots()
            skipped_for_api = 0
            for c in non_failed:
                if _batch_final_exists(c) or not _eligible_api_worker_exists(c):
                    items.remove(c)
                    return c, items, False, None
                if skipped_for_api < reserved:
                    skipped_for_api += 1
                    continue
                items.remove(c)
                return c, items, False, None
            return None, items, True, None
        pick = non_failed[0]
        items.remove(pick)
        return pick, items, False, None

    return _fallback_failed_only(items)


def _idle_status(profile: str) -> str:
    return "ready_api" if _is_api_profile(profile) else "ready_pro"


def _profile_slot_count(profile: str) -> int:
    if _is_api_profile(profile):
        try:
            return max(1, cb.total_slots())
        except Exception:
            return cb.SLOTS_PER_KEY
    return CHATS_PER_ACCOUNT


def _make_chat(profile: str, client: Any) -> Any:
    return cb.CoarenaChatService(client) if _is_api_profile(profile) else ChatService(client)


def _coarena_email_label(keys: list[str] | None = None) -> str:
    n_keys = len(keys) if keys is not None else max(1, cb.total_slots() // max(1, cb.SLOTS_PER_KEY))
    slots = n_keys * cb.SLOTS_PER_KEY
    return f"{n_keys} key{'s' if n_keys != 1 else ''} · {slots} slots · {cb.MODEL}"


def _coarena_quota_snapshot() -> dict[str, Any]:
    return {
        "remaining": None,
        "limit": None,
        "used_pct": None,
        "left_pct": None,
        "reset_in_s": None,
        "reset_in_human": "API",
        "reset_at": None,
        "name": f"Coarena ({cb.MODEL})",
        "elapsed_s": 0.0,
        "rpc_error": None,
        "usage_page": {"ok": False, "error": None},
        "reset_source": "api",
        "api_usage": cb.usage_snapshot(),
        "api_credits": None,
    }


def _coarena_is_low_quota(q: dict[str, Any]) -> bool:
    cr = q.get("api_credits") if isinstance(q.get("api_credits"), dict) else {}
    return bool(cr.get("ok") and float(cr.get("left_usd") or 0.0) < COARENA_MIN_USD_LEFT)


def _coarena_has_usable_quota(q: dict[str, Any], *, slots_needed: int = 1) -> bool:
    cr = q.get("api_credits") if isinstance(q.get("api_credits"), dict) else {}
    return bool(cr.get("ok") and float(cr.get("left_usd") or 0.0) >= (COARENA_MIN_USD_LEFT * max(1, slots_needed)))


async def _coarena_quota_snapshot_async(force: bool = False) -> dict[str, Any]:
    t0 = time.monotonic()
    snap = _coarena_quota_snapshot()
    credits = await cb.fetch_api_credits(force=force)
    snap["elapsed_s"] = round(time.monotonic() - t0, 3)
    snap["api_credits"] = credits
    if credits.get("ok"):
        snap.update(
            {
                "used_pct": credits.get("used_pct"),
                "left_pct": credits.get("left_pct"),
                "reset_in_s": credits.get("reset_in_s"),
                "reset_in_human": credits.get("reset_in_human") or "—",
                "reset_at": credits.get("reset_at"),
                "reset_source": "coarena_limits",
            }
        )
    else:
        snap["rpc_error"] = credits.get("error")
    return snap


def _make_coarena_client_shim(profile: str, keys: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        profile=profile,
        _is_coarena_api=True,
        auth_manager=SimpleNamespace(
            state=SimpleNamespace(email=_coarena_email_label(keys), chrome_profile_path=None),
            resolved_profile_name=profile,
        ),
        last_turn_timing={},
    )

STATUS_LOCK = asyncio.Lock()
VALIDATE_LOCK = asyncio.Lock()
EVENTS_LOCK = asyncio.Lock()
QUOTAS_LOCK = asyncio.Lock()
FORENSICS_LOCK = asyncio.Lock()
STATUS_FILE = SCRATCH / "surah6_parallel_status.json"
EVENTS_FILE = SCRATCH / "timing_events.jsonl"
FAILED_TURNS_FORENSICS_LOG = SCRATCH / "failed_turns_forensics.jsonl"
FORENSICS_PARTIALS_DIR = SCRATCH / "forensics_partials"
QUOTAS_LIVE_FILE = SCRATCH / "quotas_live.json"
DRAIN_STOP_FILE = SCRATCH / "drain_stop.flag"


def is_drain_requested() -> bool:
    """True when dashboard/operator requested graceful drain (finish in-flight, queue nothing new)."""
    return DRAIN_STOP_FILE.exists()
STATUS_STATE: dict[str, dict[str, Any]] = {}
PROGRESS: dict[str, int] = {}
FAILED_ON: dict[str, set[str]] = {}
LAST_END: dict[str, float] = {}
STEP_A_SECONDS: dict[str, float] = {}
ALIVE_WORKERS: set[str] = set()
ALIVE_SLOTS: set[str] = set()
ACTIVE_BATCHES_BY_PROFILE: dict[str, list[str]] = {}
OVERLAPPED_BATCHES: set[str] = set()
RETIRED_PROFILES: set[str] = set()
# Recoverable low-quota retires only: wait until reset_at, then unretire.
RETIRED_UNTIL: dict[str, datetime] = {}
RETIRED_REASON: dict[str, str] = {}
RECOVERABLE_RETIRE_REASONS = frozenset({
    "low_quota",
    "initial_quota",
    "usage_limit",
    "high_downgrade_low_quota",
    "high_downgrade_cooldown",
    "token_factory_cooldown",
    "session_cooldown",
})
ACCOUNT_INIT_LOCKS: dict[str, asyncio.Lock] = {}
UNRETIRE_LOCKS: dict[str, asyncio.Lock] = {}
ACCOUNT_INIT_CACHE: dict[str, dict[str, Any]] = {}
CHATS_PER_ACCOUNT: int = 2

BATCH_ID_RE = re.compile(r"^s(\d{3})_a(\d+)_(\d+)$", re.I)
STATUS_STATE_BY_SURAH: dict[int, dict[str, dict[str, Any]]] = {}
FINALIZE_ENABLED: bool = True
SURAH_BATCHES: dict[int, list[tuple[str, int, int]]] = {}
_ENQ_SEQ: int = 0


def surah_from_batch(batch_id: str) -> int:
    m = BATCH_ID_RE.match(batch_id)
    return int(m.group(1)) if m else SURAH_NUM


def surah_name(surah: int) -> str:
    return SURAH_NAMES_AR.get(int(surah), f"سورة {int(surah)}")


class BatchPriorityQueue:
    """Lower Surah first; within a Surah larger input files first; stable FIFO tie-break."""

    def __init__(self) -> None:
        self._q: asyncio.PriorityQueue[tuple[int, int, int, str]] = asyncio.PriorityQueue()
        self._seq = 0

    def _key(self, bid: str) -> tuple[int, int, int, str]:
        self._seq += 1
        return (surah_from_batch(bid), -_batch_input_size(bid), self._seq, bid)

    def put_nowait(self, bid: str) -> None:
        self._q.put_nowait(self._key(bid))

    async def get(self) -> str:
        *_rest, bid = await self._q.get()
        return bid

    def get_nowait(self) -> str:
        *_rest, bid = self._q.get_nowait()
        return bid

    def empty(self) -> bool:
        return self._q.empty()

    def qsize(self) -> int:
        return self._q.qsize()


# ---- Ban-safety: scoped circuit breaker + per-profile self-healing ----
TURN_OUTCOMES: "deque[tuple[float, bool, str]]" = deque(maxlen=12)
PROFILE_CONSEC_FAILS: dict[str, int] = defaultdict(int)
PROFILE_LAST_FAIL_TS: dict[str, float] = {}
PROFILE_INFLIGHT_TURNS: dict[str, int] = defaultdict(int)
BREAKER_UNTIL: float = 0.0
BREAKER_TRIPS: int = 0
BREAKER_MIN_SAMPLES: int = 8
BREAKER_ERR_THRESHOLD: float = 0.6
BREAKER_PAUSE_S: tuple[int, ...] = (300, 600, 900)
TINY_REPLY_CHARS: int = 120
RETRY_BASE_SLEEP_SERVER_S: float = 30.0  # APIError / GeminiReplyError: back off, don't hammer
EST_CREDITS_PER_INFLIGHT_BATCH: int = 360


def configure_surah(surah: int) -> None:
    """Configure global runner state for any Surah (1..114)."""
    global SURAH_NUM, SURAH_NAME_AR, REMAINING_BATCHES_8_18, BATCH_RANGE_MAP, STATUS_FILE, STATUS_STATE
    SURAH_NUM = int(surah)
    SURAH_NAME_AR = SURAH_NAMES_AR.get(SURAH_NUM, f"سورة {SURAH_NUM}")
    STATUS_FILE = SCRATCH / f"surah{SURAH_NUM}_parallel_status.json"
    STATUS_STATE.clear()
    discovered = discover_surah_batches(SURAH_NUM)
    if discovered:
        REMAINING_BATCHES_8_18 = discovered
        BATCH_RANGE_MAP = {bid: (a, b) for bid, a, b in REMAINING_BATCHES_8_18}


async def record_event(event: str, **fields: Any) -> None:
    now_dt = datetime.now().astimezone()
    row = {
        "ts": now_dt.isoformat(timespec="seconds"),
        "ts_12h": fmt_12h(now_dt),
        "event": event,
        **fields,
    }
    async with EVENTS_LOCK:
        with EVENTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _fmt_turn_timing(t: dict[str, Any]) -> str:
    cap = t.get("capture") or {}
    rep = t.get("replay") or {}
    parts: list[str] = []
    if cap:
        ct = float(cap.get("total_s") or 0.0)
        lw = float(cap.get("lock_wait_s") or 0.0)
        cr = int(cap.get("retries") or 0)
        cw = float(cap.get("wasted_retry_s") or 0.0)
        sub: list[str] = []
        if lw >= 0.1:
            sub.append(f"lock={lw:.1f}")
        sub.extend([f"nav={cap.get('nav_wait_s', 0):.1f}", f"pick={cap.get('picker_s', 0):.1f}"])
        if cr or cw:
            sub.append(f"r{cr}:waste={cw:.1f}")
        parts.append(f"cap={ct:.1f}s({','.join(sub)})")
    if rep:
        rt = float(rep.get("total_s") or 0.0)
        sub_r: list[str] = []
        if "ttft_s" in rep:
            sub_r.append(f"ttft={rep['ttft_s']:.1f}")
        if "first_answer_s" in rep:
            sub_r.append(f"1st={rep['first_answer_s']:.1f}")
        if "first_content_s" in rep:
            sub_r.append(f"cnt={rep['first_content_s']:.1f}")
        if "answer_s" in rep:
            sub_r.append(f"ans={rep['answer_s']:.1f}")
        if rep.get("reopens"):
            sub_r.append(f"reop={rep['reopens']}")
        if rep.get("error_stage"):
            sub_r.append(f"err@{rep['error_stage']}")
        parts.append(f"rep={rt:.1f}s({','.join(sub_r)})" if sub_r else f"rep={rt:.1f}s")
    if "verify_s" in t:
        parts.append(f"ver={float(t['verify_s']):.1f}s")
    return " ".join(parts)


class HighDowngradeError(RuntimeError):
    """Raised when server downgraded from 4 Argon High or returned transient error text."""


class VerifyReadbackError(RuntimeError):
    """Raised when hNvQHb verification raised and response lacked sufficient thoughts."""


def _heal_profile_session_sync(profile: str, cf: int, force_bounce: bool = False) -> None:
    """Refresh/reload or bounce Chrome daemon for a struggling profile under profile_lock."""
    if not profile or _is_api_profile(profile):
        return
    try:
        from gemini_web_mcp_cli.core.cdp import find_existing_gemcli_chrome, run_js
        from gemini_web_mcp_cli.core.chrome_manager import stop_chrome_daemon
        from gemini_web_mcp_cli.core.locks import profile_lock

        try:
            _, ws_url = find_existing_gemcli_chrome(profile_name=profile)
            if ws_url:
                run_js(ws_url, "window.__gemcliForceReload = true;")
        except Exception:
            pass

        should_bounce = force_bounce or (
            cf in (4, 6)
            and PROFILE_INFLIGHT_TURNS.get(profile, 0) == 0
            and len(ACTIVE_BATCHES_BY_PROFILE.get(profile, [])) == 0
        )
        if should_bounce:
            with profile_lock(profile, timeout=15.0):
                stopped = stop_chrome_daemon(profile, force=True)
            ACCOUNT_INIT_CACHE.pop(profile, None)
            log(
                f"[{profile}] Self-healed browser session "
                f"(bounced Chrome daemon, stopped={stopped}, consec_fails={cf})"
            )
    except Exception as exc:
        log(
            f"[{profile}] Browser session self-heal note (consec_fails={cf}): "
            f"{type(exc).__name__}: {exc}"
        )


def breaker_record(ok: bool, profile: str = "") -> None:
    """Record one turn outcome; heal degraded profiles individually and scope global pause."""
    global BREAKER_UNTIL, BREAKER_TRIPS
    now = time.monotonic()
    TURN_OUTCOMES.append((now, bool(ok), profile))
    if ok:
        if profile:
            prev_cf = PROFILE_CONSEC_FAILS.get(profile, 0)
            if prev_cf > 0:
                log(
                    f"[{profile}] Recovered to high throughput (2/2 slots) "
                    f"after {prev_cf} consecutive fail(s)."
                )
            PROFILE_CONSEC_FAILS[profile] = 0
        if len(TURN_OUTCOMES) >= 4 and all(x[1] for x in list(TURN_OUTCOMES)[-4:]):
            BREAKER_TRIPS = 0
        return

    if profile and not _is_api_profile(profile):
        PROFILE_CONSEC_FAILS[profile] += 1
        cf = PROFILE_CONSEC_FAILS[profile]
        PROFILE_LAST_FAIL_TS[profile] = now
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(asyncio.to_thread(_heal_profile_session_sync, profile, cf))
        except RuntimeError:
            pass
        if cf >= 4 and cf % 4 == 0:
            wake_dt = datetime.now().astimezone() + timedelta(seconds=240)
            mark_recoverable_quota_retire(
                profile,
                wake_dt.isoformat(timespec="seconds"),
                reason="session_cooldown",
            )
            log(
                f"[{profile}] {cf} consecutive turn failures; parking profile for 4m session cooldown "
                f"until {fmt_12h(wake_dt)} (other profiles unaffected)."
            )

    if now < BREAKER_UNTIL or len(TURN_OUTCOMES) < BREAKER_MIN_SAMPLES:
        return
    total = len(TURN_OUTCOMES)
    errs = sum(1 for _, ok_flag, _ in TURN_OUTCOMES if not ok_flag)
    failed_profiles = {p for _, ok_flag, p in TURN_OUTCOMES if not ok_flag and p}
    rate = errs / total
    if rate >= BREAKER_ERR_THRESHOLD and len(failed_profiles) >= 2:
        pause = BREAKER_PAUSE_S[min(BREAKER_TRIPS, len(BREAKER_PAUSE_S) - 1)]
        BREAKER_TRIPS += 1
        BREAKER_UNTIL = now + pause
        TURN_OUTCOMES.clear()
        log(
            f"[breaker] {errs}/{total} recent turns failed across {len(failed_profiles)} profiles "
            f"({sorted(failed_profiles)}) ({rate:.0%} >= {BREAKER_ERR_THRESHOLD:.0%}); "
            f"pausing ALL new requests for {pause/60:.0f}m (trip #{BREAKER_TRIPS}) to avoid hammering a throttled endpoint."
        )


async def breaker_gate(tag: str) -> None:
    announced = False
    while time.monotonic() < BREAKER_UNTIL:
        if not announced:
            left = BREAKER_UNTIL - time.monotonic()
            log(f"[{tag}] circuit breaker open; holding new request for up to {left/60:.0f}m")
            announced = True
        await asyncio.sleep(15.0)


_PACE_LOCK: asyncio.Lock | None = None
_LAST_GLOBAL_ACTION_TS: float = 0.0
_LAST_ACCOUNT_ACTION_TS: dict[str, float] = {}
GLOBAL_ACTION_GAP_RANGE: tuple[float, float] = (1.0, 2.2)
ACCOUNT_ACTION_GAP_RANGE: tuple[float, float] = (2.5, 4.5)


def _get_pace_lock() -> asyncio.Lock:
    global _PACE_LOCK
    if _PACE_LOCK is None:
        _PACE_LOCK = asyncio.Lock()
    return _PACE_LOCK


async def pace_google_action(profile: str, kind: str = "action") -> float:
    """Reserve a non-overlapping, jittered timestamp before any send, receive/verify, or quota RPC."""
    global _LAST_GLOBAL_ACTION_TS
    if _is_api_profile(profile):
        return 0.0
    async with _get_pace_lock():
        now = time.monotonic()
        g_gap = random.uniform(*GLOBAL_ACTION_GAP_RANGE)
        a_gap = random.uniform(*ACCOUNT_ACTION_GAP_RANGE)
        min_global = _LAST_GLOBAL_ACTION_TS + g_gap if _LAST_GLOBAL_ACTION_TS > 0 else now
        prev_acct = _LAST_ACCOUNT_ACTION_TS.get(profile, 0.0)
        min_acct = prev_acct + a_gap if prev_acct > 0 else now
        slot_ts = max(now, min_global, min_acct)
        _LAST_GLOBAL_ACTION_TS = slot_ts
        _LAST_ACCOUNT_ACTION_TS[profile] = slot_ts
        wait_s = max(0.0, slot_ts - now)
    if wait_s > 0:
        await asyncio.sleep(wait_s)
    return wait_s


async def pace_note_complete(profile: str) -> None:
    """Record completion of a send/receive so the next action respects jitter from this moment too."""
    global _LAST_GLOBAL_ACTION_TS
    if _is_api_profile(profile):
        return
    async with _get_pace_lock():
        now = time.monotonic()
        if now > _LAST_GLOBAL_ACTION_TS:
            _LAST_GLOBAL_ACTION_TS = now
        if now > _LAST_ACCOUNT_ACTION_TS.get(profile, 0.0):
            _LAST_ACCOUNT_ACTION_TS[profile] = now


def log(msg: str) -> None:
    ts = fmt_12h()
    print(f"[{ts}] {msg}", flush=True)


async def update_status(batch_id: str, **fields: Any) -> None:
    s_num = surah_from_batch(batch_id)
    s_name = surah_name(s_num)
    status_file = SCRATCH / f"surah{s_num}_parallel_status.json"
    async with STATUS_LOCK:
        state = STATUS_STATE_BY_SURAH.setdefault(s_num, {})
        if not state and status_file.exists():
            try:
                loaded = json.loads(status_file.read_text(encoding="utf-8-sig"))
                if isinstance(loaded, dict):
                    if "batches" in loaded and isinstance(loaded["batches"], dict):
                        state.update(loaded["batches"])
                    else:
                        state.update({k: v for k, v in loaded.items() if isinstance(v, dict)})
            except Exception:
                pass
        now_dt = datetime.now().astimezone()
        entry = state.setdefault(batch_id, {})
        entry.update(fields)
        entry["updatedAt"] = now_dt.isoformat(timespec="seconds")
        entry["updatedAt_12h"] = fmt_12h(now_dt)
        doc = {
            "surah": s_num,
            "surah_name_ar": s_name,
            "updatedAt": now_dt.isoformat(timespec="seconds"),
            "updatedAt_12h": fmt_iso_to_12h(now_dt.isoformat(timespec="seconds"), include_date=True),
            "batches": state,
        }
        status_file.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


async def update_quota_live(profile: str, **fields: Any) -> None:
    async with QUOTAS_LOCK:
        existing: dict[str, Any] = {}
        if QUOTAS_LIVE_FILE.exists():
            try:
                existing = json.loads(QUOTAS_LIVE_FILE.read_text(encoding="utf-8-sig"))
            except Exception:
                existing = {}
        prof_map = existing.get("profiles") if isinstance(existing.get("profiles"), dict) else {}
        prev = prof_map.get(profile, {}) if isinstance(prof_map.get(profile), dict) else {}
        rem = fields.get("remaining")
        start_rem = prev.get("start_remaining")
        if rem is not None and (start_rem is None or int(start_rem) < int(rem)):
            start_rem = int(rem)
        now_dt = datetime.now().astimezone()
        active_b = list(ACTIVE_BATCHES_BY_PROFILE.get(profile, []))
        merged = {
            **prev,
            "profile": profile,
            **{k: v for k, v in fields.items() if v is not None or k not in prev},
            "active_batches": active_b,
            "active_slots": len(active_b),
            "max_slots": int(fields.get("max_slots") or _profile_slot_count(profile)),
            "lastSeenAt": now_dt.isoformat(timespec="seconds"),
            "lastSeenAt_12h": fmt_12h(now_dt),
        }
        if _is_api_profile(profile):
            merged["api_usage"] = cb.usage_snapshot()
        if active_b:
            merged["current_batch"] = ", ".join(active_b)
            if merged.get("status") in ("ready_pro", "ready_api"):
                merged["status"] = "active_busy"
        elif "current_batch" in fields and fields["current_batch"] is None:
            merged["current_batch"] = None
        if (
            merged.get("status") in ("ready_pro", "ready_api", "active_busy")
            and "last_error" not in fields
            and PROFILE_CONSEC_FAILS.get(profile, 0) == 0
        ):
            merged["last_error"] = ""
        if start_rem is not None:
            merged["start_remaining"] = start_rem
        if merged.get("reset_at") and not merged.get("reset_at_12h"):
            merged["reset_at_12h"] = fmt_iso_to_12h(merged.get("reset_at"), include_seconds=False)
        if merged.get("limit") is not None:
            merged["plan_limit_info"] = explain_plan_limit(merged.get("limit"), merged.get("argon_high_ok"))
        prof_map[profile] = merged
        payload = {
            "updatedAt": now_dt.isoformat(timespec="seconds"),
            "updatedAt_12h": fmt_12h(now_dt),
            "source": "runner-live",
            "profiles": prof_map,
        }
        QUOTAS_LIVE_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def build_step_a_prompt(batch_id: str, start_ayah: int, end_ayah: int, input_text: str, surah: int | None = None, surah_name_ar: str | None = None) -> str:
    s_num = int(surah) if surah is not None else surah_from_batch(batch_id)
    s_name = surah_name_ar if surah_name_ar is not None else surah_name(s_num)
    return (
        "أنت خبير متمرس في علم الوقف والابتداء، والنحو القرآني، والقراءات القرآنية، وتحقيق كتب أئمة الوقف الخمسة:\n"
        "1. السجاوندي (علل الوقوف)\n"
        "2. الداني (المكتفى في الوقف والابتداء)\n"
        "3. ابن الأنباري (إيضاح الوقف والابتداء)\n"
        "4. الأشموني (منار الهدى في بيان الوقف والابتداء)\n"
        "5. النحاس (القطع والائتناف)\n\n"
        f"المهمة (المرحلة الأولى - الاستخراج الموحد للدفعة `{batch_id}`: سورة {s_name} `surah: {s_num}`، الآيات `{start_ayah}` إلى `{end_ayah}`):\n"
        "اقرأ ملف الإدخال JSON أدناه الذي يضم:\n"
        "- `ayahWordsCompact`: جدول الكلمات القرآنية المرقمة بدقة (`wordIndex:كلمة_عثمانية` مع وسوم `[مصحف]` و`[رأس آية]`).\n"
        "- `jamharahSections`: نصوص الأئمة الأربعة (`السجاوندي`, `الداني`, `ابن الأنباري`, `الأشموني`).\n"
        "- `nahhasEntries`: نصوص الإمام `النحاس`.\n"
        "- `boundaryContext`: كلمات ومقاطع الحدود المجاورة (`prevWordsCompact`, `nextWordsCompact`, `prevSections`, `nextSections`, `prevNahhasEntries`, `nextNahhasEntries`).\n\n"
        "استخرج **100%** من جميع مواضع الوقف التي حكم عليها كل إمام في الآيات المطلوبة وفق المخطط التالي بالضبط:\n"
        "```json\n"
        "{\n"
        f'  "surah": {s_num},\n'
        f'  "ayahRange": [{start_ayah}, {end_ayah}],\n'
        '  "boundaryFlags": {\n'
        '    "expandedLookbehindAyah": null,\n'
        '    "expandedLookaheadAyah": null,\n'
        '    "inheritedFromPrev": null,\n'
        '    "extendedIntoNext": null,\n'
        '    "outOfRangeStopsEmitted": []\n'
        "  },\n"
        '  "extractions": [\n'
        "    {\n"
        f'      "ayah": {start_ayah},\n'
        '      "wordIndex": 1,\n'
        '      "targetWord": "كلمة_عثمانية_مطابقة",\n'
        '      "scholar": "الداني",\n'
        '      "book": "المكتفى",\n'
        '      "page": null,\n'
        '      "verdicts": ["كاف"],\n'
        '      "isQila": [false],\n'
        '      "sajawandiSymbol": null,\n'
        '      "typoDetected": null,\n'
        '      "comment": "النص العلمي الكامل للإمام دون وضع الحكم بين قوسين في البداية."\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "```\n\n"
        "### الضوابط العلمية الصارمة:\n"
        "1. **تحديد الإحداثيات (`ayah`, `wordIndex`) بدقة 1-based**:\n"
        "   - موضع الوقف هو **آخر كلمة** في العبارة القرآنية المذكورة، ويجب أن يطابق رقمه تمامًا في `ayahWordsCompact`.\n"
        "   - انتبه لتكرار الكلمة داخل الآية الواحدة وحدد الفهرس المقصود من السياق وترتيب الآيات.\n"
        "   - لا تفرد موضعًا مستقلًا لمجرد ذكر قراءة أخرى في فعل وسط الكلام إذا كان الوقف واحدًا على آخر الجملة، ولا تستخرج شواهد السور الأخرى.\n"
        "   - لا تغفل المواضع الضمنية غير الموضوعة بين أقواس أو المعطوفة بـ`ومثله` / `وكذا` / `والتقدير` أو المذكورة في تذييلات رؤوس الآيات (`والوقف على رؤوس الآي...`).\n"
        "2. **توحيد الموضع والترتيب (`verdicts`, `isQila`)**:\n"
        "   - القيم المسموحة فقط في `verdicts`: `[\"لازم\", \"تام\", \"كاف\", \"حسن\", \"صالح\", \"جائز\", \"قيل فيه وقف\", \"لا يوقف\"]`.\n"
        "   - لا تكرر نفس الرباعي `(surah, ayah, wordIndex, scholar)`؛ بل اجمع كل الأوجه المذكورة لذلك الإمام في هذا الموضع داخل `verdicts` و`isQila` بنفس الطول (`true` للوجه الثانوي/التمريض أو `قيل` و`false` للمختار).\n"
        "   - **قاعدة السجاوندي الصارمة**: ضع الرمز الأصلي في `sajawandiSymbol` (`\"م\"`, `\"ط\"`, `\"ج\"`, `\"ز\"`, `\"ص\"`, `\"لا\"`, `\"ق\"`) لمداخل السجاوندي فقط (و`null` لغيره)، والتزم حرفيًا بالتحويل:\n"
        '     `"م"` ← `"لازم"`, `"ط"` ← `"تام"`, `"ج"` ← `"جائز"`, `"ز"` ← `"جائز"`, `"ص"` ← `"حسن"` (مرخص ضرورة؛ لا تستخدم `"صالح"` لرمز `"ص"` أبدًا!), `"لا"` ← `"لا يوقف"`, `"ق"` ← `"قيل فيه وقف"`.\n'
        "3. **التعليق العلمي (`comment`) والتصحيفات (`typoDetected`)**:\n"
        "   - لا تبدأ `comment` أبدًا بالحكم بين قوسين مثل `(لا يوقف) ...` أو `(تام) ...`.\n"
        "   - أورد التعليل العلمي الكامل من كلام الإمام دون بتر (وإذا جمع العالم كلمتين في تعليل واحد فأورد التعليل كاملًا لكل منهما).\n"
        "   - إذا وقع تصحيف مطبعي في كلمة قرآنية أو رقم آية أو لفظ حكم، استخرج الإحداثي والحكم الصحيحين علميًا وسجّل التصحيف في `\"typoDetected\": {\"raw\": \"...\", \"corrected\": \"...\", \"reason\": \"...\"}` مع تصويبه في `comment`.\n"
        "4. **مزامنة الحدود ونطاق الآيات (`boundaryContext`, `boundaryFlags`)**:\n"
        f"   - راجع `prevSections` و`prevNahhasEntries` و`nextSections` لاكتشاف أي جملة مقسومة أو إحالة (`ومثله`, `وكذا`) تكمّل حكمًا يخص الآيات `{start_ayah}..{end_ayah}` وأدرجه في `extractions`.\n"
        f"   - **اقصر مصفوفة `extractions` حصريًا على الآيات `{start_ayah}` إلى `{end_ayah}` فقط**؛ وإذا امتد كلام إمام نحو آية خارج النطاق فسجّل ملاحظته في `boundaryFlags.extendedIntoNext` أو `boundaryFlags.inheritedFromPrev` دون إدراج آية خارج `{start_ayah}..{end_ayah}` داخل `extractions`.\n"
        "5. **الإخراج**: أخرج كائن JSON واحدًا فقط صحيحًا بالكامل داخل كتلة كود ```json واحدة بدون أي نص إضافي قبلها أو بعدها.\n\n"
        "ملف الإدخال:\n"
        f"```json\n{input_text.strip()}\n```\n"
    )


def build_step_a_fix_prompt(
    batch_id: str,
    start_ayah: int,
    end_ayah: int,
    fatal_errors: list[str],
    warnings: list[str],
    input_data: dict[str, Any],
) -> str:
    words_ref = json.dumps(input_data.get("ayahWordsCompact", {}), ensure_ascii=False, indent=2)
    issues_txt = "\n".join(f"- {e}" for e in fatal_errors[:25])
    warns_txt = "\n".join(f"- {w}" for w in warnings[:15])
    return (
        f"في استخراجك للدفعة `{batch_id}` ({start_ayah}–{end_ayah}) وُجدت الملاحظات التالية الواجب تصحيحها فورًا:\n"
        f"{issues_txt}\n"
        + (f"\nتحذيرات للتثبت والتحقق (استخرج أي موضع أغفلته إن وُجد في النص):\n{warns_txt}\n" if warns_txt else "")
        + "\nراجع جدول الكلمات الدقيق `ayahWordsCompact`:\n"
        f"```json\n{words_ref}\n```\n\n"
        "أعد إخراج **كائن JSON الكامل المصحح** داخل كتلة كود ```json واحدة فقط بعد إصلاح جميع الأخطاء أعلاه "
        f"(تأكّد من: اقتصار `extractions` على الآيات {start_ayah}–{end_ayah} فقط، صحة `wordIndex` حسب الجدول، عدم تكرار `(ayah, wordIndex, scholar)`، عدم بدء `comment` بحكم بين قوسين، وتحويل رمز السجاوندي `\"ص\"` إلى `\"حسن\"` لا `\"صالح\"`)."
    )


def collect_permissive_items(
    ext_data: dict[str, Any], include_comments: bool = False, default_surah: int | None = None
) -> list[dict[str, Any]]:
    ds = int(default_surah) if default_surah is not None else SURAH_NUM
    permissive = []
    for x in ext_data.get("extractions", []):
        non_la = [v for v in (x.get("verdicts") or []) if u.norm_verdict(v) != "لا يوقف"]
        if not non_la:
            continue
        item: dict[str, Any] = {
            "ayah": x["ayah"],
            "wordIndex": x["wordIndex"],
            "targetWord": x["targetWord"],
            "scholar": x["scholar"],
            "verdicts": x["verdicts"],
            "isQila": x["isQila"],
        }
        if x.get("surah") and int(x["surah"]) != ds:
            item["surah"] = int(x["surah"])
        if include_comments:
            item["comment"] = x.get("comment", "")
        permissive.append(item)
    return permissive


def build_step_b_chunk_prompt(
    batch_id: str,
    chunk: list[dict[str, Any]],
    input_data: dict[str, Any],
    chunk_label: str = "",
) -> str:
    ays = {str(it["ayah"]) for it in chunk}
    words_ctx: dict[str, str] = {}
    for ay in sorted(ays, key=int):
        if ay in input_data.get("ayahWordsCompact", {}):
            words_ctx[ay] = input_data["ayahWordsCompact"][ay]
        nxt = str(int(ay) + 1)
        if nxt in input_data.get("ayahWordsCompact", {}):
            words_ctx[nxt] = input_data["ayahWordsCompact"][nxt]
        elif nxt in input_data.get("boundaryContext", {}).get("nextWordsCompact", {}):
            words_ctx[f"{nxt}_next"] = input_data["boundaryContext"]["nextWordsCompact"][nxt]

    list_json = json.dumps(chunk, ensure_ascii=False, separators=(",", ":"))
    words_json = json.dumps(words_ctx, ensure_ascii=False, indent=2)
    lbl_txt = f" ({chunk_label})" if chunk_label else ""
    return (
        f"ممتاز. الآن للدفعة `{batch_id}`{lbl_txt}، أضف حقول التوضيح والمعاني الإضافية (`demosAndMeanings`) لهذه القائمة.\n\n"
        "مواصفات حقل `demosAndMeanings` (مثل نموذج البقرة آية 28):\n"
        "- أي موضع حكمه `[\"لا يوقف\"]` فقط مستبعد بالفعل (قيمته `null`).\n"
        f"- لكل موضع في القائمة أدناه (عددها {len(chunk)})، أنشئ مصفوفة `demosAndMeanings` تحوي عنصرًا واحدًا بالضبط لكل حكم **غير `\"لا يوقف\"`** في `verdicts` بالترتيب نفسه، بهذه الحقول فقط (`additionalProperties: false`):\n"
        "  - `verdict` (string): الحكم الموضَّح مطابقًا لـ`verdicts`.\n"
        "  - `isQila` (boolean): `true` أو `false` مطابقًا للموضع.\n"
        "  - `attributedTo` (string اختياري عند وجود قائل منقول عنه مثل السجستاني أو الأخفش).\n"
        "  - `waqfSegmentWords`: `[startWordIndex, endWordIndex]` (1-based في نفس الآية؛ يجب أن يكون `1 <= startWordIndex <= endWordIndex` و`endWordIndex == wordIndex` بالضبط!).\n"
        "  - `ibtidaSegmentWords`: `[startWordIndex, endWordIndex]` في نفس الآية للابتداء بعد الوقف (بحيث يكون `startWordIndex == wordIndex + 1` و`endWordIndex <= عدد كلمات الآية`)، أو `null` إذا كان `wordIndex` هو `[رأس آية]` والابتداء من الآية التالية.\n"
        "  - `waqfDemo`: نص التلاوة حتى كلمة الوقف بصيغة `تلاوة: ﴿ ... ﴾ [قف على: ...]`.\n"
        "  - `ibtidaDemo`: نص الابتداء بعد الوقف بصيغة `﴿ ... ﴾ [قف على: ...]` (أو مطلع الآية التالية `[الآية التالية]` عند رأس الآية).\n"
        "  - `meaningAtWaqf`: بيان المعنى عند الوقف.\n"
        "  - `meaningAtIbtida`: بيان المعنى عند الابتداء بما بعده.\n"
        "  - `meaningIfConnected`: بيان المعنى أو رجحان الوصل/الوقف عند الوصل.\n\n"
        "مثال مختصر:\n"
        "```json\n"
        "[\n"
        "  {\n"
        '    "ayah": 28,\n'
        '    "wordIndex": 3,\n'
        '    "scholar": "ابن الأنباري",\n'
        '    "demosAndMeanings": [\n'
        "      {\n"
        '        "verdict": "حسن",\n'
        '        "isQila": false,\n'
        '        "waqfSegmentWords": [1, 3],\n'
        '        "ibtidaSegmentWords": [4, 13],\n'
        '        "waqfDemo": "تلاوة: ﴿ كَيْفَ تَكْفُرُونَ بِٱللَّهِ ﴾ [قف على: بِٱللَّهْ]",\n'
        '        "ibtidaDemo": "﴿ وَكُنتُمْ أَمْوَٰتًۭا فَأَحْيَـٰكُمْ ثُمَّ يُمِيتُكُمْ ثُمَّ يُحْيِيكُمْ ثُمَّ إِلَيْهِ تُرْجَعُونَ ﴾ [قف على: تُرْجَعُونْ]",\n'
        '        "meaningAtWaqf": "استفهام إنكاري وتوبيخي مستقلٌّ في لفظه...",\n'
        '        "meaningAtIbtida": "والحال أنكم كنتم أمواتاً...",\n'
        '        "meaningIfConnected": "الوصل أتمّ؛ لأن جملة ﴿وَكُنتُمْ أَمْوَٰتًۭا﴾ في موضع الحال..."\n'
        "      }\n"
        "    ]\n"
        "  }\n"
        "]\n"
        "```\n\n"
        "مرجع أرقام الكلمات الدقيقة (`ayahWordsCompact` 1-based):\n"
        f"```json\n{words_json}\n```\n\n"
        f"أخرج مصفوفة JSON واحدة فقط داخل كتلة كود ```json واحدة تضم **كافة المداخل الـ {len(chunk)} التالية كاملة دون اختصار أو حذف** "
        "(كل عنصر يحوي فقط: `ayah`, `wordIndex`, `scholar`, و`demosAndMeanings` — مع `\"surah\"` فقط لو تغيرت السورة):\n"
        f"```json\n{list_json}\n```\n"
    )


def build_step_b_repair_prompt(
    fix_items: list[dict[str, Any]], input_data: dict[str, Any], is_missing_only: bool
) -> str:
    ays = {str(it["ayah"]) for it in fix_items}
    words_ctx: dict[str, str] = {}
    for ay in sorted(ays, key=int):
        if ay in input_data.get("ayahWordsCompact", {}):
            words_ctx[ay] = input_data["ayahWordsCompact"][ay]
        nxt = str(int(ay) + 1)
        if nxt in input_data.get("ayahWordsCompact", {}):
            words_ctx[nxt] = input_data["ayahWordsCompact"][nxt]
        elif nxt in input_data.get("boundaryContext", {}).get("nextWordsCompact", {}):
            words_ctx[f"{nxt}_next"] = input_data["boundaryContext"]["nextWordsCompact"][nxt]

    compact_items = [{k: v for k, v in it.items() if k != "previous"} for it in fix_items]
    header = (
        f"بقيت هذه المداخل الـ {len(compact_items)} ناقصة من ردك السابق لم تولّد بعد. أكملها الآن كاملة:\n"
        if is_missing_only
        else f"المواضع الـ {len(compact_items)} التالية إما ناقصة أو فيها أخطاء (مذكورة في `reasons` كعدم تطابق `verdict` أو خطأ `waqfSegmentWords` / `ibtidaSegmentWords` أو نقص حقل). أكملها وأصلحها بدقة:\n"
    )
    return (
        f"{header}\n"
        "قواعد صارمة:\n"
        "- `waqfSegmentWords`: `[start, wordIndex]` (ينتهي عند `wordIndex`).\n"
        "- `ibtidaSegmentWords`: `[wordIndex + 1, end]` ضمن كلمات الآية في الجدول، أو `null` **فقط** عندما يكون الوقف على `[رأس آية]` (آخر كلمة في الآية).\n"
        "- **مهم جدًا عند `[رأس آية]`**: اجعل `ibtidaSegmentWords` فقط `null`، أما `ibtidaDemo` و`meaningAtIbtida` **فممنوع وضع `null` أو نص فارغ فيهما مطلقًا**! في `ibtidaDemo` اكتب مطلع الآية التالية من جدول الكلمات بصيغة `﴿ مطلع الآية التالية ... ﴾ [قف على: ...]` (أو `[الآية التالية]`)، وفي `meaningAtIbtida` اشرح معنى الابتداء بأول الآية التالية.\n"
        "- عنصر واحد لكل حكم غير `\"لا يوقف\"` في `verdicts` بالترتيب نفسه.\n"
        "- الحقول المسموحة فقط داخل `demosAndMeanings`: `verdict`, `isQila`, `attributedTo` (اختياري), `waqfSegmentWords`, `ibtidaSegmentWords`, `waqfDemo` (بصيغة `تلاوة: ﴿ ... ﴾ [قف على: ...]`), `ibtidaDemo` (نص غير فارغ دائمًا), `meaningAtWaqf` (نص غير فارغ), `meaningAtIbtida` (نص غير فارغ دائمًا), `meaningIfConnected` (نص غير فارغ).\n\n"
        f"جدول الكلمات الدقيقة:\n```json\n{json.dumps(words_ctx, ensure_ascii=False, indent=2)}\n```\n\n"
        f"أخرج مصفوفة JSON واحدة فقط داخل كتلة كود ```json لهذه الـ {len(compact_items)} فقط (كل عنصر يحوي `ayah`, `wordIndex`, `scholar`, `demosAndMeanings`):\n"
        f"```json\n{json.dumps(compact_items, ensure_ascii=False, indent=2)}\n```\n"
    )


def _is_transient_error_reply(text: str) -> bool:
    t = (text or "").strip().lower()
    if len(t) > 350:
        return False
    markers = (
        "encountered an error",
        "hard time fulfilling",
        "something went wrong",
        "couldn't process",
        "try again",
        "لا يمكنني مساعدتك",
        "مجرّد نموذج لغوي",
        "مجرد نموذج لغوي",
        "لا أستطيع فهم ذلك",
    )
    return any(m in t for m in markers)


async def verify_argon_high_turn(client: GeminiClient, resp: Any) -> tuple[bool, str, dict[str, Any]]:
    """Verify server actually executed 4 Argon High without downgrade."""
    t_v0 = time.monotonic()
    vinfo: dict[str, Any] = {"rpc_calls": 0, "sleep_s": 0.0}
    txt = (resp.text or "").strip()
    if _is_transient_error_reply(txt):
        vinfo["total_s"] = round(time.monotonic() - t_v0, 3)
        return False, f"server failure reply: {txt[:120]!r}", vinfo

    thoughts_len = len(resp.thoughts or "")
    cid = resp.metadata.cid if resp.metadata else None
    rcid = resp.metadata.rcid if resp.metadata else None
    if not cid:
        vinfo["total_s"] = round(time.monotonic() - t_v0, 3)
        if thoughts_len == 0:
            return False, "missing cid and thoughts_len=0", vinfo
        return True, f"no-cid thoughts={thoughts_len}", vinfo

    raw_txt = ""
    turn_txt = ""
    prof_name = str(getattr(client, "profile", "") or getattr(client.auth_manager, "resolved_profile_name", "") or "default")
    for _retry in range(3):
        vinfo["rpc_calls"] += 1
        try:
            await pace_google_action(prof_name, "verify")
            res = await client.execute_rpc_with_browser_cookies(
                RPC.READ_CHAT, json.dumps([cid, 25, None, 1, [0], [4], None, 1])
            )
            await pace_note_complete(prof_name)
            if res and res[0].raw:
                raw_txt = res[0].raw
                d = res[0].data
                turns = d[0] if isinstance(d, list) and d and isinstance(d[0], list) else []
                matched_turn = None
                if rcid:
                    for t in turns:
                        ts = json.dumps(t, ensure_ascii=False)
                        if rcid in ts:
                            matched_turn = ts
                            break
                if matched_turn is None and turns:
                    matched_turn = json.dumps(turns[0], ensure_ascii=False)
                if matched_turn:
                    turn_txt = matched_turn
                    break
        except Exception:
            pass
        slp = 1.5 * (_retry + 1)
        vinfo["sleep_s"] = round(vinfo["sleep_s"] + slp, 3)
        await asyncio.sleep(slp)

    vinfo["total_s"] = round(time.monotonic() - t_v0, 3)
    if turn_txt:
        low_t = turn_txt.lower()
        if "high demand" in low_t or "different model was used" in low_t:
            return False, "server downgraded due to high demand", vinfo
        matched_marker = next(
            (
                m for m in (
                    '"4 argon high"',
                    r'\"4 argon high\"',
                    '"gemini-4-argon"',
                    r'\"gemini-4-argon\"',
                )
                if m in low_t
            ),
            None,
        )
        if not matched_marker:
            # Server sometimes omits the literal marker in hNvQHb readback on genuine
            # 4 Argon High turns that produced long CoT thoughts (matches readback fallback).
            if thoughts_len >= 1000:
                return True, f"argon_high=True thoughts={thoughts_len} (no-literal-marker)", vinfo
            return False, f"missing 4 Argon High marker in hNvQHb turn (thoughts={thoughts_len})", vinfo
        return True, f"argon_high=True marker={matched_marker} thoughts={thoughts_len}", vinfo

    if thoughts_len == 0:
        return False, "empty hNvQHb and thoughts_len=0", vinfo
    return True, f"hNvQHb-empty thoughts={thoughts_len}", vinfo


async def send_with_retry(
    profile: str,
    batch_id: str,
    client: GeminiClient,
    chat: ChatService,
    prompt: str,
    label: str,
    max_attempts: int = 3,
    bstats: dict[str, Any] | None = None,
    send_timeout_s: float | None = None,
):
    is_api = _is_api_profile(profile)
    if send_timeout_s is None:
        send_timeout_s = 2400.0 if is_api else (800.0 if label.startswith("Step A") else 480.0)
    turns_log = SCRATCH / "turns.jsonl"

    first_exc: Exception | None = None
    last_exc: Exception | None = None
    attempt_excs: list[Exception] = []
    for attempt in range(1, max_attempts + 1):
        if not is_api:
            await breaker_gate(f"{profile}][{batch_id}")
            if PROFILE_CONSEC_FAILS.get(profile, 0) >= 2 and PROFILE_INFLIGHT_TURNS.get(profile, 0) >= 1:
                log(
                    f"[{profile}][{batch_id}] Degraded profile ({PROFILE_CONSEC_FAILS[profile]} consec fails); "
                    "scaling temporarily to 1/2 slot until 1 turn succeeds."
                )
                waited_s = 0.0
                while (
                    PROFILE_CONSEC_FAILS.get(profile, 0) >= 2
                    and PROFILE_INFLIGHT_TURNS.get(profile, 0) >= 1
                    and waited_s < 240.0
                ):
                    await asyncio.sleep(2.0)
                    waited_s += 2.0
        prev_meta = getattr(chat, "_metadata", None)
        mode = "same_chat" if prev_meta is not None else "fresh"
        t0 = time.monotonic()
        prev_end = LAST_END.get(profile)
        idle_before_s = round(t0 - prev_end, 3) if prev_end is not None else None
        if bstats is not None and bstats.get("step_a_known"):
            step_a_s: float | None = round(float(bstats["step_a_s"]), 2)
        elif batch_id in STEP_A_SECONDS:
            step_a_s = round(float(STEP_A_SECONDS[batch_id]), 2)
        else:
            step_a_s = None

        def _rec(**kw: Any) -> None:
            row = {
                "profile": profile,
                "batch": batch_id,
                "label": label,
                "attempt": attempt,
                "mode": mode,
                "idle_before_s": idle_before_s,
                "step_a_s": step_a_s,
                **kw,
                "ts": datetime.now().isoformat(timespec="seconds"),
            }
            with turns_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        resp: Any = None
        vinfo: dict[str, Any] = {}
        bstats_turn_recorded = False
        sleep_s = 0.0
        PROFILE_INFLIGHT_TURNS[profile] += 1
        try:
            if not is_api:
                await pace_google_action(profile, "send")
            try:
                resp = await asyncio.wait_for(
                    chat.send(prompt, model="gemini-4-argon", thinking_level="high"),
                    timeout=send_timeout_s,
                )
            except TimeoutError as timeout_exc:
                raise TimeoutError(f"chat.send timed out after {send_timeout_s:.0f}s") from timeout_exc
            if not is_api:
                await pace_note_complete(profile)
            t_send_done = time.monotonic()

            ver_failed = False
            ver_err_detail = ""
            t_v0 = time.monotonic()
            try:
                ok_high, why, vinfo = await (
                    cb.api_verify(client, resp) if is_api else verify_argon_high_turn(client, resp)
                )
            except Exception as ver_exc:
                ver_failed = True
                ver_err_detail = f"{type(ver_exc).__name__}: {ver_exc}"
                vinfo = {"error": ver_err_detail, "total_s": round(time.monotonic() - t_v0, 3)}
                thoughts_len = len(getattr(resp, "thoughts", None) or "")
                if thoughts_len > 1000:
                    ok_high = True
                    why = "readback_failed"
                else:
                    ok_high = False
                    why = "readback_failed"
                    raise VerifyReadbackError(
                        f"verify=readback_failed (thoughts={thoughts_len}): {ver_err_detail}"
                    ) from ver_exc

            dt = time.monotonic() - t0
            turn_t = dict(getattr(client, "last_turn_timing", {}) or {})
            turn_t["send_call_s"] = round(t_send_done - t0, 3)
            turn_t["verify_s"] = float(vinfo.get("total_s") or 0.0)
            turn_t["verify_detail"] = vinfo
            cap_t = float((turn_t.get("capture") or {}).get("total_s") or 0.0)
            cap_w = float((turn_t.get("capture") or {}).get("wasted_retry_s") or 0.0)
            rep_t = float((turn_t.get("replay") or {}).get("total_s") or 0.0)
            ver_t = float(turn_t.get("verify_s") or 0.0)

            if bstats is not None:
                bstats["capture_s"] += cap_t
                bstats["capture_wasted_s"] += cap_w
                bstats["replay_s"] += rep_t
                bstats["verify_s"] += ver_t
            bstats_turn_recorded = True

            if not ok_high:
                if "server failure reply" in why:
                    raise GeminiReplyError(why)
                raise HighDowngradeError(why)

            reply_len = len((resp.text or "").strip())
            if reply_len < TINY_REPLY_CHARS:
                raise GeminiReplyError(f"server failure reply: tiny answer ({reply_len} chars): {(resp.text or '').strip()[:80]!r}")
            if not is_api:
                breaker_record(True, profile)
            PROGRESS[batch_id] = PROGRESS.get(batch_id, 0) + 1
            if bstats is not None:
                bstats["turns_ok"] += 1
            ok_kw: dict[str, Any] = {}
            if getattr(resp, "usage", None):
                ok_kw["api_usage"] = getattr(resp, "usage")
            _rec(
                outcome="ok",
                prompt_chars=len(prompt),
                secs=round(dt, 1),
                thoughts=len(resp.thoughts or ""),
                chars=len(resp.text or ""),
                model_hash=resp.server_model_hash,
                model_label=getattr(resp, "server_model_label", None),
                verify=why,
                cid=resp.metadata.cid if resp.metadata else None,
                is_wasted=False,
                timing=turn_t,
                **ok_kw,
            )
            t_str = _fmt_turn_timing(turn_t)
            why_log = f"verify=readback_failed ({ver_err_detail})" if ver_failed else why
            log(
                f"[{profile}][{batch_id}] {label} done in {dt:.1f}s "
                f"[{t_str}] (chars={len(resp.text or '')}, {why_log}, cid={resp.metadata.cid if resp.metadata else None})"
            )
            return resp
        except Exception as exc:
            dt = time.monotonic() - t0
            if first_exc is None:
                first_exc = exc
            last_exc = exc
            attempt_excs.append(exc)
            if hasattr(chat, "_metadata"):
                chat._metadata = prev_meta
            turn_t = dict(getattr(client, "last_turn_timing", {}) or {})
            if vinfo:
                turn_t["verify_s"] = float(vinfo.get("total_s") or 0.0)
                turn_t["verify_detail"] = vinfo
            # TokenFactoryError already does an internal capture retry + daemon restart.
            # Outer retries just replay the Chrome-restart spiral (~100s each) seen in
            # production ("input field not found" / /sorry/). Fail fast and let the
            # worker terminal path requeue the batch onto another profile.
            is_stale_target = type(exc).__name__ == "StaleTargetError"
            no_retry = (not is_stale_target) and (
                isinstance(exc, (HighDowngradeError, VerifyReadbackError, TokenFactoryError))
                or type(exc).__name__ in ("AuthError", "UsageLimitExceeded", "TokenFactoryError")
            )
            will_retry = (not no_retry) and attempt < max_attempts
            if not is_api and not is_stale_target:
                breaker_record(False, profile)
            if is_stale_target:
                sleep_s = 3.0 if will_retry else 0.0
            else:
                base_sleep = RETRY_BASE_SLEEP_SERVER_S if isinstance(exc, (GeminiReplyError, APIError)) else 5.0
                sleep_s = float(base_sleep * (2 ** (attempt - 1))) if will_retry else 0.0
            if bstats is not None:
                bstats["turns_fail"] += 1
                bstats["wasted_fail_s"] += dt
                bstats["wasted_sleep_s"] += sleep_s
                if not bstats_turn_recorded:
                    cap_t = float((turn_t.get("capture") or {}).get("total_s") or 0.0)
                    cap_w = float((turn_t.get("capture") or {}).get("wasted_retry_s") or 0.0)
                    rep_t = float((turn_t.get("replay") or {}).get("total_s") or 0.0)
                    ver_t = float(vinfo.get("total_s") or 0.0) if vinfo else 0.0
                    bstats["capture_s"] += cap_t
                    bstats["capture_wasted_s"] += cap_w
                    bstats["replay_s"] += rep_t
                    bstats["verify_s"] += ver_t

            partial_thoughts_str = (
                (getattr(resp, "thoughts", None) or "")
                if resp is not None
                else (getattr(exc, "partial_thoughts", None) or "")
            )
            partial_text_str = (
                (getattr(resp, "text", None) or "")
                if resp is not None
                else (getattr(exc, "partial_text", None) or "")
            )
            fail_thoughts = len(partial_thoughts_str) if partial_thoughts_str else getattr(exc, "thoughts", None)
            fail_chars = len(partial_text_str) if partial_text_str else getattr(exc, "chars", None)
            fail_cid = (
                (resp.metadata.cid if getattr(resp, "metadata", None) else None)
                if resp is not None
                else (getattr(exc, "partial_cid", None) or getattr(exc, "cid", None) or getattr(prev_meta, "cid", None))
            )
            fail_rcid = (
                (resp.metadata.rcid if getattr(resp, "metadata", None) else None)
                if resp is not None
                else (getattr(exc, "partial_rcid", None) or getattr(prev_meta, "rcid", None))
            )
            fail_usage = getattr(resp, "usage", None) if resp is not None else getattr(exc, "usage", None)
            rep_t_info = turn_t.get("replay") or {}
            body_frames = getattr(exc, "body_frames", rep_t_info.get("body_frames"))
            reopens = getattr(exc, "reopens", rep_t_info.get("reopens"))
            transcript_tail = getattr(exc, "transcript_tail", "") or ""
            rec_kw: dict[str, Any] = {
                "outcome": type(exc).__name__,
                "prompt_chars": len(prompt),
                "secs": round(dt, 1),
                "thoughts": fail_thoughts,
                "chars": fail_chars,
                "cid": fail_cid,
                "rcid": fail_rcid,
                "retry_sleep_s": sleep_s,
                "is_wasted": True,
                "err": str(exc)[:180],
                "timing": turn_t,
            }
            if fail_usage:
                rec_kw["api_usage"] = fail_usage
            if isinstance(exc, VerifyReadbackError):
                rec_kw["verify"] = "readback_failed"
            _rec(**rec_kw)
            try:
                partial_file: str | None = None
                if partial_text_str or partial_thoughts_str:
                    FORENSICS_PARTIALS_DIR.mkdir(parents=True, exist_ok=True)
                    safe_lbl = re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_")[:32]
                    pf_path = FORENSICS_PARTIALS_DIR / f"{batch_id}_{profile}_{safe_lbl}_att{attempt}_{int(time.time())}.json"
                    pf_path.write_text(
                        json.dumps(
                            {
                                "ts": datetime.now().isoformat(timespec="seconds"),
                                "profile": profile,
                                "batch": batch_id,
                                "label": label,
                                "attempt": attempt,
                                "mode": mode,
                                "outcome": type(exc).__name__,
                                "err": str(exc),
                                "cid": fail_cid,
                                "rcid": fail_rcid,
                                "partial_thoughts": partial_thoughts_str,
                                "partial_text": partial_text_str,
                                "transcript_tail": transcript_tail,
                                "timing": turn_t,
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    partial_file = pf_path.name
                forensic_row = {
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "profile": profile,
                    "batch": batch_id,
                    "label": label,
                    "attempt": attempt,
                    "mode": mode,
                    "outcome": type(exc).__name__,
                    "secs": round(dt, 1),
                    "err": str(exc),
                    "cid": fail_cid,
                    "rcid": fail_rcid,
                    "thoughts_len": len(partial_thoughts_str),
                    "chars_len": len(partial_text_str),
                    "body_frames": body_frames,
                    "reopens": reopens,
                    "thoughts_tail": partial_thoughts_str[-600:] if partial_thoughts_str else "",
                    "text_tail": partial_text_str[-600:] if partial_text_str else "",
                    "transcript_tail": transcript_tail[-600:] if transcript_tail else "",
                    "partial_file": partial_file,
                    "timing": turn_t,
                }
                with FAILED_TURNS_FORENSICS_LOG.open("a", encoding="utf-8") as ff:
                    ff.write(json.dumps(forensic_row, ensure_ascii=False) + "\n")
            except Exception:
                pass
            t_str = _fmt_turn_timing(turn_t)
            extra_t = f" [{t_str}]" if t_str else ""
            sleep_str = f" sleep={sleep_s:.0f}s" if sleep_s else ""
            log(
                f"[{profile}][{batch_id}] {label} attempt {attempt}/{max_attempts} ERR in {dt:.1f}s{extra_t}{sleep_str}: "
                f"{type(exc).__name__}: {exc}"
            )
            if no_retry:
                raise
        finally:
            PROFILE_INFLIGHT_TURNS[profile] = max(0, PROFILE_INFLIGHT_TURNS[profile] - 1)
            LAST_END[profile] = time.monotonic()

        if sleep_s > 0:
            await asyncio.sleep(sleep_s)
    if isinstance(first_exc, HighDowngradeError):
        raise first_exc
    if isinstance(last_exc, HighDowngradeError):
        raise last_exc
    if last_exc is None:
        err_detail = "unknown error"
    elif first_exc is not None and (type(first_exc) is not type(last_exc) or str(first_exc) != str(last_exc)):
        err_detail = f"first={type(first_exc).__name__}: {first_exc} | last={type(last_exc).__name__}: {last_exc}"
    else:
        err_detail = f"{type(last_exc).__name__}: {last_exc}"
    err = RuntimeError(
        f"[{profile}][{batch_id}] {label} failed after {max_attempts} attempts: {err_detail}"
    )
    err.first_exc = first_exc  # type: ignore[attr-defined]
    err.attempt_excs = tuple(attempt_excs)  # type: ignore[attr-defined]
    raise err from last_exc


def _iter_exception_causes(exc: BaseException):
    """Yield exc, attached first/attempt exceptions, and their causal chains."""
    queue: list[BaseException] = [exc]
    seen: set[int] = set()
    while queue:
        cur = queue.pop(0)
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        yield cur
        first_exc = getattr(cur, "first_exc", None)
        if isinstance(first_exc, BaseException) and id(first_exc) not in seen:
            queue.append(first_exc)
        for att_exc in getattr(cur, "attempt_excs", ()) or ():
            if isinstance(att_exc, BaseException) and id(att_exc) not in seen:
                queue.append(att_exc)
        for nxt in (cur.__cause__, cur.__context__):
            if nxt is not None and id(nxt) not in seen:
                queue.append(nxt)


def _is_chunk1_no_fallback_error(exc: BaseException) -> bool:
    """True for failures where Chunk 1 same-chat should NOT fall back to fresh ChatService."""
    for cur in _iter_exception_causes(exc):
        if isinstance(cur, (HighDowngradeError, AuthError, UsageLimitExceeded, TokenFactoryError)):
            return True
        if type(cur).__name__ in (
            "HighDowngradeError",
            "AuthError",
            "UsageLimitExceeded",
            "TokenFactoryError",
        ):
            return True
    return False


def _is_usage_limit_error(exc: BaseException) -> bool:
    for cur in _iter_exception_causes(exc):
        if isinstance(cur, UsageLimitExceeded) or type(cur).__name__ == "UsageLimitExceeded":
            return True
    return False


def _is_high_downgrade_error(exc: BaseException) -> bool:
    for cur in _iter_exception_causes(exc):
        if isinstance(cur, HighDowngradeError) or type(cur).__name__ == "HighDowngradeError":
            return True
    return False


def _is_token_factory_error(exc: BaseException) -> bool:
    """True for recoverable TokenFactoryError (Chrome DOM/nav/sorry) and False for AuthError/session-expired."""
    for cur in _iter_exception_causes(exc):
        if isinstance(cur, AuthError) or type(cur).__name__ == "AuthError":
            return False
        if isinstance(cur, TokenFactoryError) or type(cur).__name__ == "TokenFactoryError":
            msg = str(cur).lower()
            if "session expired" in msg or "run 'gemcli login'" in msg or "not signed in" in msg:
                return False
            return True
    return False


def _is_terminal_worker_error(exc: BaseException) -> bool:
    """True when the profile/worker cannot continue running."""
    for cur in _iter_exception_causes(exc):
        if isinstance(cur, (HighDowngradeError, AuthError, UsageLimitExceeded, TokenFactoryError)):
            return True
        if type(cur).__name__ in (
            "HighDowngradeError",
            "AuthError",
            "UsageLimitExceeded",
            "TokenFactoryError",
        ):
            return True
    return False


def _parse_reset_at(reset_at: Any) -> datetime | None:
    if reset_at is None or reset_at == "":
        return None
    if isinstance(reset_at, datetime):
        return reset_at if reset_at.tzinfo else reset_at.astimezone()
    try:
        dt = datetime.fromisoformat(str(reset_at))
        return dt if dt.tzinfo else dt.astimezone()
    except Exception:
        return None


def mark_recoverable_quota_retire(
    profile: str,
    reset_at: Any,
    *,
    reason: str = "low_quota",
) -> datetime | None:
    """Mark profile retired for quota; store when the 5h reset clock says to retry."""
    RETIRED_PROFILES.add(profile)
    RETIRED_REASON[profile] = reason
    dt = _parse_reset_at(reset_at)
    now = datetime.now().astimezone()
    if dt is None:
        return RETIRED_UNTIL.get(profile)
    if dt <= now:
        dt = now + timedelta(seconds=60)
    prev = RETIRED_UNTIL.get(profile)
    # Keep the soonest future wake if we already scheduled one.
    if prev is not None and now < prev < dt:
        return prev
    RETIRED_UNTIL[profile] = dt
    return dt


def clear_profile_retire(profile: str) -> None:
    RETIRED_PROFILES.discard(profile)
    RETIRED_UNTIL.pop(profile, None)
    RETIRED_REASON.pop(profile, None)


def is_recoverable_retire(profile: str) -> bool:
    return profile in RETIRED_PROFILES and RETIRED_REASON.get(profile) in RECOVERABLE_RETIRE_REASONS


def _all_work_finished(
    shared_queue: asyncio.Queue[str] | None,
    dedicated_queue: asyncio.Queue[str] | None,
) -> bool:
    """True when no queued or in-flight batches remain for a parked slot."""
    if shared_queue is None and dedicated_queue is None:
        return False
    shared_empty = shared_queue is None or shared_queue.empty()
    dedicated_empty = dedicated_queue is None or dedicated_queue.empty()
    return shared_empty and dedicated_empty and IN_FLIGHT_BATCHES == 0


async def await_quota_unretire(
    *,
    profile: str,
    slot_tag: str,
    slot_idx: int,
    client: GeminiClient,
    required_for_slot: int,
    shared_queue: asyncio.Queue[str] | None = None,
    dedicated_queue: asyncio.Queue[str] | None = None,
) -> bool:
    """Sleep until reset_at, re-check qpEbW, and unretire if credits recovered.

    Returns True if this slot should resume picking batches.
    """
    import probe_profile_quotas as pq

    while is_recoverable_retire(profile):
        if _all_work_finished(shared_queue, dedicated_queue):
            log(f"[{slot_tag}] All queued/in-flight batches finished while quota-retired — exiting cleanly.")
            return False

        until = RETIRED_UNTIL.get(profile)
        now = datetime.now().astimezone()
        if until is None:
            log(
                f"[{slot_tag}] Quota-retired without reset_at; cannot auto-unretire — staying retired."
            )
            return False

        wake_at = until + timedelta(seconds=5.0 * max(0, slot_idx - 1))
        wait_s = (wake_at - now).total_seconds()
        if wait_s > 0:
            log(
                f"[{slot_tag}] Quota-retired until {until.strftime('%I:%M %p')} "
                f"(waiting {pq.fmt_duration(int(wait_s))} then recheck); batches stay in shared pool."
            )
            while (
                wait_s > 0
                and is_recoverable_retire(profile)
                and not is_drain_requested()
                and not _all_work_finished(shared_queue, dedicated_queue)
            ):
                chunk = min(wait_s, 5.0)
                await asyncio.sleep(chunk)
                wait_s -= chunk

        if is_drain_requested():
            log(f"[{slot_tag}] Drain stop requested while quota-retired — exiting cleanly.")
            return False
        if _all_work_finished(shared_queue, dedicated_queue):
            log(f"[{slot_tag}] All queued/in-flight batches finished while quota-retired — exiting cleanly.")
            return False

        if not is_recoverable_retire(profile):
            # Another path cleared or permanently retired this profile.
            return profile not in RETIRED_PROFILES

        unretire_lock = UNRETIRE_LOCKS.setdefault(profile, asyncio.Lock())
        should_sleep_headroom = False
        async with unretire_lock:
            now_locked = datetime.now().astimezone()
            until_locked = RETIRED_UNTIL.get(profile)
            if not is_recoverable_retire(profile):
                if profile in RETIRED_PROFILES:
                    return False
                q = await get_pro_quota_rich(client, force=True)
                rem = q.get("remaining")
                lim_s = q.get("limit") if q.get("limit") is not None else "?"
                if (
                    (_is_api_profile(profile) and _coarena_has_usable_quota(q, slots_needed=slot_idx))
                    or (rem is not None and int(rem) >= required_for_slot)
                    or (rem is None and not _is_api_profile(profile))
                ):
                    log(
                        f"[{slot_tag}] Account unretired by sibling slot; "
                        f"remaining={rem}/{lim_s} meets slot need {required_for_slot} — resuming."
                    )
                    return True
                if slot_idx > 1 or _is_api_profile(profile):
                    log(
                        f"[{slot_tag}] Account unretired but remaining={rem}/{lim_s} "
                        f"< {required_for_slot} for this slot; waiting for more headroom."
                    )
                    should_sleep_headroom = True
                else:
                    return True
            elif until_locked is not None and now_locked < until_locked:
                continue
            else:
                q = await get_pro_quota_rich(client, force=True)
                rem = q.get("remaining")
                if rem is None and not _is_api_profile(profile):
                    log(f"[{slot_tag}] Quota check missing browser cookies; refreshing Chrome/cookies and retrying...")
                    try:
                        pq.init_client_from_disk(client)
                        await pq.ensure_profile_chrome_and_cookies(profile, client, allow_launch=True)
                        q = await get_pro_quota_rich(client)
                        rem = q.get("remaining")
                    except Exception as exc:
                        log(f"[{slot_tag}] Cookie refresh before quota recheck failed: {type(exc).__name__}: {exc}")
                lim = q.get("limit")
                reset_h = q.get("reset_in_human") or "—"
                lim_s = lim if lim is not None else "?"
                await update_quota_live(
                    profile,
                    status="low_quota_recheck",
                    remaining=rem,
                    limit=lim,
                    used_pct=q.get("used_pct"),
                    left_pct=q.get("left_pct"),
                    reset_in_s=q.get("reset_in_s"),
                    reset_in_human=reset_h,
                    reset_at=q.get("reset_at"),
                    api_credits=q.get("api_credits"),
                    name=q.get("name") or "Thinking/Pro",
                )
                reason_now = RETIRED_REASON.get(profile) or ""
                cooldown_only = reason_now in (
                    "token_factory_cooldown",
                    "session_cooldown",
                    "high_downgrade_cooldown",
                )
                base_min_needed = min(required_for_slot, 240)
                if (
                    (_is_api_profile(profile) and _coarena_has_usable_quota(q, slots_needed=1))
                    or (rem is not None and int(rem) >= base_min_needed)
                    or (cooldown_only and rem is None)
                ):
                    clear_profile_retire(profile)
                    if cooldown_only:
                        PROFILE_CONSEC_FAILS[profile] = 2
                    else:
                        PROFILE_CONSEC_FAILS[profile] = 0
                    ACCOUNT_INIT_CACHE.pop(profile, None)
                    log(
                        f"[{slot_tag}] Quota refreshed (remaining={rem}/{lim_s} reset_in={reset_h}); "
                        "unretired — rejoining shared pool."
                    )
                    await update_quota_live(
                        profile,
                        status=_idle_status(profile),
                        remaining=rem,
                        limit=lim,
                        used_pct=q.get("used_pct"),
                        left_pct=q.get("left_pct"),
                        reset_in_s=q.get("reset_in_s"),
                        reset_in_human=reset_h,
                        reset_at=q.get("reset_at"),
                        api_credits=q.get("api_credits"),
                        name=q.get("name") or "Thinking/Pro",
                    )
                    if (
                        (_is_api_profile(profile) and not _coarena_has_usable_quota(q, slots_needed=slot_idx))
                        or (rem is not None and int(rem) < required_for_slot)
                    ):
                        log(
                            f"[{slot_tag}] Account unretired for slot #1 (remaining={rem}/{lim_s} "
                            f"< {required_for_slot} for slot #{slot_idx}); waiting 30s for headroom."
                        )
                        should_sleep_headroom = True
                    else:
                        return True
                else:
                    new_until = mark_recoverable_quota_retire(
                        profile, q.get("reset_at"), reason=RETIRED_REASON.get(profile) or "low_quota"
                    )
                    if new_until is None or new_until <= datetime.now().astimezone():
                        # Still low and no future reset — poll again in 60s.
                        RETIRED_UNTIL[profile] = datetime.now().astimezone() + timedelta(seconds=60)
                        new_until = RETIRED_UNTIL[profile]
                    log(
                        f"[{slot_tag}] Still low after reset check (remaining={rem}/{lim_s} "
                        f"< {base_min_needed}); next wake {new_until.strftime('%I:%M %p')}."
                    )
                    continue

        while should_sleep_headroom and not is_drain_requested():
            headroom_wait_s = 30.0
            while (
                headroom_wait_s > 0
                and not is_drain_requested()
                and not _all_work_finished(shared_queue, dedicated_queue)
            ):
                chunk = min(headroom_wait_s, 5.0)
                await asyncio.sleep(chunk)
                headroom_wait_s -= chunk
            if _all_work_finished(shared_queue, dedicated_queue):
                log(
                    f"[{slot_tag}] All queued/in-flight batches finished while waiting for headroom — exiting cleanly."
                )
                return False
            if is_drain_requested():
                break
            if profile in RETIRED_PROFILES:
                break
            q_hr = await get_pro_quota_rich(client, force=True)
            rem_hr = q_hr.get("remaining")
            if (_is_api_profile(profile) and _coarena_has_usable_quota(q_hr, slots_needed=slot_idx)) or (
                rem_hr is not None and int(rem_hr) >= required_for_slot
            ):
                log(
                    f"[{slot_tag}] Headroom recovered (remaining={rem_hr}/{q_hr.get('limit') or '?'}) "
                    f"— resuming slot #{slot_idx}."
                )
                return True
            log(
                f"[{slot_tag}] Account unretired but remaining={rem_hr}/{q_hr.get('limit') or '?'} "
                f"< {required_for_slot} for this slot; waiting for more headroom."
            )

        if is_drain_requested() or _all_work_finished(shared_queue, dedicated_queue):
            return False

    return profile not in RETIRED_PROFILES


def _is_no_standalone_retry_error(exc: BaseException) -> bool:
    """True when retrying the same account in a fresh standalone chat is futile."""
    for cur in _iter_exception_causes(exc):
        if isinstance(cur, (HighDowngradeError, AuthError, UsageLimitExceeded, TokenFactoryError)):
            return True
        if type(cur).__name__ in (
            "HighDowngradeError",
            "AuthError",
            "UsageLimitExceeded",
            "ConnectTimeout",
            "TokenFactoryError",
        ):
            return True
        msg = str(cur).lower()
        if any(
            m in msg
            for m in (
                "without an answer after",
                "no first answer/thought after",
                "no answer from gemini",
                "connecttimeout",
                "tokenfactoryerror",
                "google.com/sorry",
            )
        ):
            return True
    return False


def _attach_comments(
    items: list[dict[str, Any]],
    comment_map: dict[tuple[int, int, int, str], str],
    default_surah: int | None = None,
) -> list[dict[str, Any]]:
    ds = default_surah if default_surah is not None else SURAH_NUM
    out: list[dict[str, Any]] = []
    for it in items:
        it2 = dict(it)
        if not it2.get("comment"):
            k = (
                int(it2.get("surah") or ds),
                int(it2["ayah"]),
                int(it2["wordIndex"]),
                str(it2["scholar"]),
            )
            it2["comment"] = comment_map.get(k, "")
        out.append(it2)
    return out


async def process_batch(
    profile: str,
    client: GeminiClient,
    batch_id: str,
    start_ayah: int,
    end_ayah: int,
    wl_cache: dict[int, dict[tuple[int, int], dict[str, Any]]],
    mw_cache: dict[int, dict[int, int]],
) -> tuple[bool, str]:
    t_batch0 = time.monotonic()
    s_num = surah_from_batch(batch_id)
    s_name = surah_name(s_num)
    bstats: dict[str, Any] = {
        "turns_ok": 0,
        "turns_fail": 0,
        "capture_s": 0.0,
        "capture_wasted_s": 0.0,
        "replay_s": 0.0,
        "verify_s": 0.0,
        "wasted_fail_s": 0.0,
        "wasted_sleep_s": 0.0,
        "validate_s": 0.0,
        "step_a_s": 0.0,
        "step_a_known": False,
        "step_b_s": 0.0,
    }
    final_out = u.PROTO / f"{batch_id}_llm_output.json"
    if final_out.exists():
        t_v0 = time.monotonic()
        async with VALIDATE_LOCK:
            ok, msg = u.validate_candidate_file(batch_id, start_ayah, end_ayah, final_out, apply_to_feed=False, surah=s_num)
        bstats["validate_s"] += time.monotonic() - t_v0
        if ok:
            dt_b = round(time.monotonic() - t_batch0, 3)
            log(f"[{profile}][{batch_id}] SKIP already complete & valid in {dt_b:.2f}s: {final_out.name}")
            await update_status(batch_id, profile=profile, stage="done_cached", valid=True, total_s=dt_b)
            await record_event("batch_done", surah=s_num, batch=batch_id, profile=profile, ok=True, cached=True, total_s=dt_b)
            return True, "cached"

    inp_path = u.PROTO / f"{batch_id}_input.json"
    input_text = inp_path.read_text(encoding="utf-8")
    input_data = json.loads(input_text)

    chat = _make_chat(profile, client)
    ext_path = SCRATCH / f"{batch_id}_extract_only.json"
    ext_data: dict[str, Any] | None = None
    step_a_from_chat = False

    if ext_path.exists():
        try:
            cand = json.loads(ext_path.read_text(encoding="utf-8"))
            t_v0 = time.monotonic()
            errs, warns = u.validate_step_a(
                cand, s_num, start_ayah, end_ayah, input_data, wl_cache, mw_cache, strict_in_range=True
            )
            bstats["validate_s"] += time.monotonic() - t_v0
            if not errs:
                ext_data = cand
                log(
                    f"[{profile}][{batch_id}] Loaded cached valid Step A "
                    f"({len(cand['extractions'])} stops, warns={len(warns)})"
                )
        except Exception:
            pass

    if ext_data is None:
        if COARENA_STEP_B_ONLY and _is_api_profile(profile):
            raise _BatchHandoff(
                "needs_step_a",
                f"[{profile}][{batch_id}] Coarena is dedicated to Step B (demos) only; awaiting browser Step A",
            )
        t_sa0 = time.monotonic()
        await update_status(batch_id, profile=profile, stage="step_a")
        prompt_a = build_step_a_prompt(batch_id, start_ayah, end_ayah, input_text, surah=s_num, surah_name_ar=s_name)
        (SCRATCH / f"{batch_id}_stepA_prompt.txt").write_text(prompt_a, encoding="utf-8")

        resp_a = await send_with_retry(profile, batch_id, client, chat, prompt_a, "Step A", bstats=bstats)
        (SCRATCH / f"{batch_id}_stepA_raw.txt").write_text(resp_a.text or "", encoding="utf-8")
        step_a_from_chat = True

        for fix_round in range(1, 4):
            try:
                cand = u.extract_json_value(resp_a.text or "")
                t_v0 = time.monotonic()
                errs, warns = u.validate_step_a(
                    cand, s_num, start_ayah, end_ayah, input_data, wl_cache, mw_cache, strict_in_range=True
                )
                bstats["validate_s"] += time.monotonic() - t_v0
            except Exception as exc:
                cand = None
                errs = [f"JSON parse error: {exc}"]
                warns = []

            if not errs:
                nahhas_missing_warns = [
                    w for w in warns if "Nahhas source text" in w or "In-range ayahs with 0 extractions" in w
                ]
                if nahhas_missing_warns and fix_round == 1:
                    log(f"[{profile}][{batch_id}] Step A warnings triggering recall check: {nahhas_missing_warns}")
                    recall_prompt = (
                        build_step_a_fix_prompt(batch_id, start_ayah, end_ayah, [], nahhas_missing_warns, input_data)
                        + "\nإذا ثبت بعد مراجعة نص الإدخال أن تلك الآيات لا تحوي أي مواضع وقف زائدة عما استخرجتَه بالفعل، فأعد نفس كائن JSON كاملًا دون تغيير."
                    )
                    try:
                        resp_a2 = await send_with_retry(
                            profile, batch_id, client, chat, recall_prompt, "Step A recall check", bstats=bstats
                        )
                        (SCRATCH / f"{batch_id}_stepA_recall_raw.txt").write_text(
                            resp_a2.text or "", encoding="utf-8"
                        )
                        cand2 = u.extract_json_value(resp_a2.text or "")
                        t_v0 = time.monotonic()
                        errs2, warns2 = u.validate_step_a(
                            cand2, s_num, start_ayah, end_ayah, input_data, wl_cache, mw_cache, strict_in_range=True
                        )
                        bstats["validate_s"] += time.monotonic() - t_v0
                        if not errs2 and len(cand2.get("extractions", [])) >= len(cand.get("extractions", [])):
                            cand = cand2
                            warns = warns2
                    except Exception as recall_exc:
                        log(f"[{profile}][{batch_id}] Recall check failed ({recall_exc}); keeping valid initial cand")
                ext_data = cand
                bstats["step_a_s"] = round(time.monotonic() - t_sa0, 2)
                bstats["step_a_known"] = True
                STEP_A_SECONDS[batch_id] = bstats["step_a_s"]
                log(
                    f"[{profile}][{batch_id}] Step A validated OK in {bstats['step_a_s']:.1f}s: "
                    f"{len(ext_data['extractions'])} extractions, warns={len(warns)}"
                )
                for w in warns:
                    log(f"[{profile}][{batch_id}]   WARN: {w}")
                break

            log(f"[{profile}][{batch_id}] Step A errors (round {fix_round}): {errs[:5]}")
            if fix_round == 3:
                raise RuntimeError(f"[{profile}][{batch_id}] Step A failed validation after 3 rounds: {errs}")
            fix_prompt = build_step_a_fix_prompt(batch_id, start_ayah, end_ayah, errs, warns, input_data)
            resp_a = await send_with_retry(
                profile, batch_id, client, chat, fix_prompt, f"Step A fix #{fix_round}", bstats=bstats
            )
            (SCRATCH / f"{batch_id}_stepA_fix{fix_round}_raw.txt").write_text(
                resp_a.text or "", encoding="utf-8"
            )

        assert ext_data is not None
        ext_path.write_text(json.dumps(ext_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        if (not _is_api_profile(profile)) and step_a_from_chat and _eligible_api_worker_exists(batch_id):
            await update_status(
                batch_id,
                profile=profile,
                stage="step_a_done",
                extractionsCount=len(ext_data.get("extractions", [])),
                step_a_s=bstats["step_a_s"],
            )
            log(
                f"[{profile}][{batch_id}] Step A ready ({len(ext_data.get('extractions', []))} stops in {bstats['step_a_s']:.1f}s); "
                "handing off Step B (demos) to Coarena/pool."
            )
            raise _BatchHandoff("step_b_handoff", "step_a_done")

    # Step B: chunked in chunks of <= 38 items in SAME ChatService session if Step A ran there
    t_sb0 = time.monotonic()
    await update_status(
        batch_id,
        profile=profile,
        stage="step_b",
        extractionsCount=len(ext_data.get("extractions", [])),
    )

    demos_cache_path = SCRATCH / f"{batch_id}_demos_collected.json"
    collected_items: list[dict[str, Any]] = []
    if demos_cache_path.exists():
        try:
            collected_items = json.loads(demos_cache_path.read_text(encoding="utf-8"))
        except Exception:
            collected_items = []

    t_v0 = time.monotonic()
    miss, brok, valid_map = u.validate_step_b(ext_data, collected_items, wl_cache, mw_cache, default_surah=s_num)
    bstats["validate_s"] += time.monotonic() - t_v0

    perm_comment_map = {
        (
            int(it.get("surah") or s_num),
            int(it["ayah"]),
            int(it["wordIndex"]),
            str(it["scholar"]),
        ): it.get("comment", "")
        for it in collect_permissive_items(ext_data, include_comments=True, default_surah=s_num)
    }

    if miss:
        miss_keys = {
            (
                int(m.get("surah") or s_num),
                int(m["ayah"]),
                int(m["wordIndex"]),
                str(m["scholar"]),
            )
            for m in miss
        }
        permissive_all = collect_permissive_items(ext_data, include_comments=False, default_surah=s_num)
        permissive = [
            it
            for it in permissive_all
            if (
                int(it.get("surah") or s_num),
                int(it["ayah"]),
                int(it["wordIndex"]),
                str(it["scholar"]),
            )
            in miss_keys
        ]
        if collected_items:
            log(
                f"[{profile}][{batch_id}] Resuming Step B: {len(valid_map)} valid cached, "
                f"{len(brok)} broken, {len(permissive)}/{len(permissive_all)} remaining in chunks"
            )
        chunk_size = 38
        chunks = [permissive[i : i + chunk_size] for i in range(0, len(permissive), chunk_size)]
        for ci, ch in enumerate(chunks, 1):
            ch_lbl = f"جزء {ci}/{len(chunks)}" if len(chunks) > 1 else ""
            ch_for_chat = ch if step_a_from_chat else _attach_comments(ch, perm_comment_map)
            prompt_b = build_step_b_chunk_prompt(batch_id, ch_for_chat, input_data, ch_lbl)
            (SCRATCH / f"{batch_id}_stepB_c{ci}_prompt.txt").write_text(prompt_b, encoding="utf-8")
            was_existing_chat = getattr(chat, "_metadata", None) is not None
            first_max_attempts = 1 if was_existing_chat else 3
            try:
                resp_b = await send_with_retry(
                    profile,
                    batch_id,
                    client,
                    chat,
                    prompt_b,
                    f"Step B c{ci}/{len(chunks)}",
                    max_attempts=first_max_attempts,
                    bstats=bstats,
                )
            except Exception as exc:
                if (not was_existing_chat) or _is_chunk1_no_fallback_error(exc):
                    raise
                log(
                    f"[{profile}][{batch_id}] Step B c{ci} same-chat failed ({exc}); "
                    "falling back to fresh standalone Step B chat"
                )
                chat = _make_chat(profile, client)
                step_a_from_chat = False
                prompt_b = build_step_b_chunk_prompt(
                    batch_id, _attach_comments(ch, perm_comment_map), input_data, ch_lbl
                )
                resp_b = await send_with_retry(
                    profile,
                    batch_id,
                    client,
                    chat,
                    prompt_b,
                    f"Step B c{ci}/{len(chunks)} standalone",
                    max_attempts=3,
                    bstats=bstats,
                )

            (SCRATCH / f"{batch_id}_stepB_c{ci}_raw.txt").write_text(resp_b.text or "", encoding="utf-8")
            try:
                parsed_b = u.extract_json_value(resp_b.text or "")
                if isinstance(parsed_b, dict) and "extractions" in parsed_b:
                    parsed_b = parsed_b["extractions"]
                if isinstance(parsed_b, list):
                    collected_items.extend(parsed_b)
            except Exception as exc:
                log(f"[{profile}][{batch_id}] Step B c{ci} JSON parse error: {exc}")

            demos_cache_path.write_text(
                json.dumps(collected_items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

        t_v0 = time.monotonic()
        miss, brok, valid_map = u.validate_step_b(ext_data, collected_items, wl_cache, mw_cache, default_surah=s_num)
        bstats["validate_s"] += time.monotonic() - t_v0
        log(f"[{profile}][{batch_id}] Step B initial: valid={len(valid_map)} missing={len(miss)} broken={len(brok)}")

    # Continuation / Repair loop (up to 7 turns, chunked <= 35 items)
    for rep_round in range(1, 8):
        if not miss and not brok:
            break
        fix_list = miss + brok
        chunk = _attach_comments(fix_list[:35], perm_comment_map)
        is_miss_only = len(miss) == len(fix_list)
        rep_prompt = build_step_b_repair_prompt(chunk, input_data, is_miss_only)
        was_existing_chat = chat._metadata is not None
        try:
            resp_r = await send_with_retry(
                profile,
                batch_id,
                client,
                chat,
                rep_prompt,
                f"Step B cont/repair #{rep_round} ({len(chunk)} items)",
                max_attempts=1 if was_existing_chat else 3,
                bstats=bstats,
            )
        except Exception as exc:
            if (not was_existing_chat) or _is_chunk1_no_fallback_error(exc):
                raise
            log(f"[{profile}][{batch_id}] Step B repair #{rep_round} error ({exc}); resetting to fresh standalone chat")
            chat = _make_chat(profile, client)
            step_a_from_chat = False
            resp_r = await send_with_retry(
                profile,
                batch_id,
                client,
                chat,
                rep_prompt,
                f"Step B cont/repair #{rep_round} standalone ({len(chunk)} items)",
                bstats=bstats,
            )
        (SCRATCH / f"{batch_id}_stepB_repair{rep_round}_raw.txt").write_text(
            resp_r.text or "", encoding="utf-8"
        )
        try:
            parsed_r = u.extract_json_value(resp_r.text or "")
            if isinstance(parsed_r, dict) and "extractions" in parsed_r:
                parsed_r = parsed_r["extractions"]
            if isinstance(parsed_r, list):
                collected_items.extend(parsed_r)
        except Exception as exc:
            log(f"[{profile}][{batch_id}] Step B repair #{rep_round} JSON parse error: {exc}")

        demos_cache_path.write_text(
            json.dumps(collected_items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        t_v0 = time.monotonic()
        miss, brok, valid_map = u.validate_step_b(ext_data, collected_items, wl_cache, mw_cache, default_surah=s_num)
        bstats["validate_s"] += time.monotonic() - t_v0
        log(
            f"[{profile}][{batch_id}] Step B post-repair #{rep_round}: "
            f"valid={len(valid_map)} missing={len(miss)} broken={len(brok)}"
        )

    bstats["step_b_s"] = round(time.monotonic() - t_sb0, 2)
    if miss or brok:
        dt_b = round(time.monotonic() - t_batch0, 2)
        tot_wasted = round(bstats["wasted_fail_s"] + bstats["wasted_sleep_s"] + bstats["capture_wasted_s"], 2)
        await record_event(
            "batch_done", surah=s_num, batch=batch_id, profile=profile, ok=False, total_s=dt_b,
            step_a_s=bstats["step_a_s"], step_b_s=bstats["step_b_s"], validate_s=round(bstats["validate_s"], 2),
            capture_s=round(bstats["capture_s"], 2), capture_wasted_s=round(bstats["capture_wasted_s"], 2),
            replay_s=round(bstats["replay_s"], 2), verify_s=round(bstats["verify_s"], 2),
            wasted_fail_s=round(bstats["wasted_fail_s"], 2), wasted_sleep_s=round(bstats["wasted_sleep_s"], 2),
            wasted_s=tot_wasted, turns_ok=bstats["turns_ok"], turns_fail=bstats["turns_fail"],
        )
        await update_status(
            batch_id,
            profile=profile,
            stage="failed_step_b",
            valid=len(valid_map),
            missing=len(miss),
            broken=len(brok),
            total_s=dt_b,
            wasted_s=tot_wasted,
        )
        return False, f"incomplete Step B: missing={len(miss)} broken={len(brok)}"

    candidate = u.assemble_candidate_output(ext_data, valid_map, default_surah=s_num)
    final_out.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    t_v0 = time.monotonic()
    async with VALIDATE_LOCK:
        ok, msg = u.validate_candidate_file(batch_id, start_ayah, end_ayah, final_out, apply_to_feed=False, surah=s_num)
    bstats["validate_s"] += time.monotonic() - t_v0

    dt_b = round(time.monotonic() - t_batch0, 2)
    tot_wasted = round(bstats["wasted_fail_s"] + bstats["wasted_sleep_s"] + bstats["capture_wasted_s"], 2)
    # Compute token & cost estimates from turns.jsonl for this batch.
    # Telemetry must never fail a finished extraction — fall back to turn counts.
    try:
        telem_map = compute_surah_turn_ledger(s_num)
        bt = telem_map.get(batch_id) or {}
    except Exception as telem_exc:
        log(f"[{profile}][{batch_id}] telemetry refresh soft-failed: {type(telem_exc).__name__}: {telem_exc}")
        bt = {}
    est_quota_cr = int(bt.get("quota_credits_used") or ((bstats["turns_ok"] + bstats["turns_fail"]) * CREDITS_PER_ARGON_HIGH_TURN))
    est_tokens = int(bt.get("total_tokens") or 0)
    est_cost = float(bt.get("cost_usd") or 0.0)
    step_a_cached_s = ((STATUS_STATE_BY_SURAH.get(s_num) or {}).get(batch_id) or {}).get("step_a_s")
    step_a_total_s = round(
        float(bstats["step_a_s"] or STEP_A_SECONDS.get(batch_id, 0.0) or step_a_cached_s or 0.0),
        2,
    )
    await update_status(
        batch_id,
        profile=profile,
        stage="validated_ready" if ok else "failed_validate",
        valid=ok,
        extractionsCount=len(candidate.get("extractions", [])),
        permissiveDemosCount=len(valid_map),
        total_s=dt_b,
        step_a_s=step_a_total_s,
        step_b_s=bstats["step_b_s"],
        capture_s=round(bstats["capture_s"], 2),
        replay_s=round(bstats["replay_s"], 2),
        verify_s=round(bstats["verify_s"], 2),
        wasted_s=tot_wasted,
        quota_credits_used=est_quota_cr,
        total_tokens=est_tokens,
        new_input_tokens=int(bt.get("new_input_tokens") or 0),
        context_input_tokens=int(bt.get("context_input_tokens") or 0),
        thinking_tokens=int(bt.get("thinking_tokens") or 0),
        output_tokens=int(bt.get("output_tokens") or 0),
        cost_usd=est_cost,
    )
    await record_event(
        "batch_done", surah=s_num, batch=batch_id, profile=profile, ok=ok, cached=False, total_s=dt_b,
        step_a_s=step_a_total_s, step_b_s=bstats["step_b_s"], validate_s=round(bstats["validate_s"], 2),
        capture_s=round(bstats["capture_s"], 2), capture_wasted_s=round(bstats["capture_wasted_s"], 2),
        replay_s=round(bstats["replay_s"], 2), verify_s=round(bstats["verify_s"], 2),
        wasted_fail_s=round(bstats["wasted_fail_s"], 2), wasted_sleep_s=round(bstats["wasted_sleep_s"], 2),
        wasted_s=tot_wasted, turns_ok=bstats["turns_ok"], turns_fail=bstats["turns_fail"],
        quota_credits_used=est_quota_cr, total_tokens=est_tokens, cost_usd=est_cost,
    )
    if not ok:
        log(f"[{profile}][{batch_id}] FAILED llm_waqf_extractor --validate in {dt_b/60:.1f}m:\n{msg}")
        return False, msg
    log(
        f"[{profile}][{batch_id}] COMPLETE & VALIDATED in {dt_b/60:.1f}m "
        f"(A={step_a_total_s:.0f}s B={bstats['step_b_s']:.0f}s val={bstats['validate_s']:.2f}s | "
        f"cap={bstats['capture_s']:.0f}s rep={bstats['replay_s']:.0f}s ver={bstats['verify_s']:.1f}s waste={tot_wasted:.0f}s | "
        f"quota={est_quota_cr}cr tokens={est_tokens:,} cost=${est_cost:.2f}) "
        f"({len(candidate['extractions'])} stops, {len(valid_map)} demos) -> {final_out.name}"
    )
    return True, "ok"


IN_FLIGHT_BATCHES = 0
DAEMON_START_LOCK = asyncio.Lock()


async def init_client_with_retry(profile: str, stagger_s: float) -> tuple[GeminiClient, dict[str, Any]]:
    import probe_profile_quotas as pq
    from gemini_web_mcp_cli.core.daemon_idle import start_on_demand

    t_w0 = time.monotonic()
    if stagger_s > 0:
        await asyncio.sleep(stagger_s)
    client = GeminiClient(profile_name=profile, timeout=750.0)
    client.profile = profile  # type: ignore[attr-defined]
    last_exc: Exception | None = None
    for attempt in range(1, 5):
        try:
            t_c0 = time.monotonic()
            # Load auth from disk directly to avoid firing simultaneous raw httpx GET /app
            # scrapes across 5 workers (which otherwise trigger Google /sorry/ 429s).
            pq.init_client_from_disk(client)
            client_init_s = round(time.monotonic() - t_c0, 3)
            t_d0 = time.monotonic()
            daemon_wait_s = 0.0
            daemon_start_s = 0.0
            async with DAEMON_START_LOCK:
                daemon_wait_s = round(time.monotonic() - t_d0, 3)
                t_d1 = time.monotonic()
                port = pq.find_profile_daemon_port(profile, client)
                if not port and client.auth_manager.state.chrome_profile_path:
                    await asyncio.to_thread(
                        start_on_demand,
                        client.auth_manager.resolved_profile_name,
                        client.auth_manager.state.chrome_profile_path,
                    )
                    port = pq.find_profile_daemon_port(profile, client)
                daemon_start_s = round(time.monotonic() - t_d1, 3)

            if not port and client.auth_manager.state.chrome_profile_path:
                port = await pq.ensure_profile_chrome_and_cookies(profile, client, allow_launch=True)

            cap_info: dict[str, Any] = {
                "argon_high_ok": None,
                "tier": "unknown",
                "picker_result": None,
                "picker_label": None,
            }
            if port:
                await pq.ensure_profile_chrome_and_cookies(profile, client, allow_launch=False)
                cap_info = await asyncio.to_thread(
                    pq.check_picker_capability_sync, profile, client, port, True
                )
            launch_info: dict[str, Any] = {
                "stagger_s": round(stagger_s, 3),
                "client_init_s": client_init_s,
                "client_init_detail": dict(getattr(client, "last_init_timing", {}) or {}),
                "daemon_lock_wait_s": daemon_wait_s,
                "daemon_start_s": daemon_start_s,
                "attempts": attempt,
                "total_pre_quota_s": round(time.monotonic() - t_w0, 3),
                "port": port,
                "cap_info": cap_info,
            }
            return client, launch_info
        except Exception as exc:
            last_exc = exc
            log(f"[{profile}] init attempt {attempt}/4 ERR: {type(exc).__name__}: {exc}")
            await asyncio.sleep(2.5 * attempt)
    raise RuntimeError(f"[{profile}] GeminiClient.init() failed after 4 tries: {last_exc}")


async def get_pro_quota_rich(client: Any, *, force: bool = False) -> dict[str, Any]:
    """Return rich quota dict for Thinking/Pro pool.

    Credits come from qpEbW. Dual-window reset times (5h + weekly) come from
    the /usage page when available; exhausted-window blocking reset is preferred
    for retire/unretire parking.
    """
    if getattr(client, "_is_coarena_api", False) or getattr(client, "profile", None) in API_PROFILES:
        return await _coarena_quota_snapshot_async(force=force)
    import probe_profile_quotas as pq

    prof_name = str(
        getattr(client, "profile", "")
        or getattr(getattr(client, "auth_manager", None), "resolved_profile_name", "")
        or "default"
    )
    await pace_google_action(prof_name, "quota")

    # Best-effort live model catalog (sJBwce) so Hydrogen/Carbon hashes stay fresh.
    try:
        import gemini_live_catalog as glc

        await asyncio.wait_for(glc.ensure_live_catalog(client, force=False), timeout=12.0)
    except Exception:
        pass

    t0 = time.monotonic()
    out: dict[str, Any] = {
        "remaining": None,
        "limit": None,
        "used_pct": None,
        "left_pct": None,
        "reset_in_s": None,
        "reset_in_human": "—",
        "reset_at": None,
        "name": None,
        "elapsed_s": 0.0,
        "rpc_error": None,
        "usage_page": None,
        "reset_source": None,
    }
    try:
        lim = await asyncio.wait_for(LimitsService(client).get_limits(), timeout=20.0)
        preferred = []
        for q in lim:
            name = str(q.name or "")
            if name == "Thinking Prompts" or "Thinking" in name:
                preferred.append((0, q))
            elif name == "Pro Prompts" or name.startswith("Pro"):
                preferred.append((1, q))
        preferred.sort(key=lambda x: (x[1].remaining, x[0]))
        if preferred:
            q = preferred[0][1]
            rem = int(q.remaining)
            limit = int(q.limit)
            used_pct = round(100.0 * (limit - rem) / limit, 1) if limit > 0 else int(q.used)
            left_pct = round(100.0 - used_pct, 1)
            reset_in_s = int(round(q.reset_in_seconds))
            reset_at = q.reset_at.astimezone().isoformat(timespec="seconds")
            out.update(
                {
                    "remaining": rem,
                    "limit": limit,
                    "used_pct": used_pct,
                    "left_pct": left_pct,
                    "reset_in_s": reset_in_s,
                    "reset_in_human": pq.fmt_duration(reset_in_s),
                    "reset_at": reset_at,
                    "name": str(q.name),
                    "reset_source": "qpEbW",
                }
            )
    except Exception as exc:
        out["rpc_error"] = f"{type(exc).__name__}: {exc}"

    try:
        from usage_page_quotas import fetch_usage_page_pools

        usage = await asyncio.wait_for(fetch_usage_page_pools(client), timeout=35.0)
        out["usage_page"] = usage
        if usage.get("ok"):
            if usage.get("blocking_reset_at"):
                out["reset_at"] = usage.get("blocking_reset_at")
                out["reset_in_s"] = usage.get("blocking_reset_in_s")
                out["reset_in_human"] = pq.fmt_duration(usage.get("blocking_reset_in_s"))
                out["reset_source"] = f"usage_page:{usage.get('blocking_pool') or 'blocking'}"
                out["blocking_pool"] = usage.get("blocking_pool")
            elif not out.get("reset_at"):
                burst = (usage.get("pools") or {}).get("burst_5h") or {}
                if burst.get("reset_at"):
                    out["reset_at"] = burst.get("reset_at")
                    out["reset_in_s"] = burst.get("reset_in_s")
                    out["reset_in_human"] = burst.get("reset_in_human") or pq.fmt_duration(burst.get("reset_in_s"))
                    out["reset_source"] = "usage_page:burst_5h"
    except Exception as usage_exc:
        out["usage_page"] = {"ok": False, "error": f"{type(usage_exc).__name__}: {usage_exc}"}

    out["elapsed_s"] = round(time.monotonic() - t0, 3)
    return out


async def get_pro_quota(client: GeminiClient) -> tuple[int | None, int | None, str | None, float]:
    """Return (remaining, plan_limit, feature_name, elapsed_s) for Thinking/Pro pool."""
    q = await get_pro_quota_rich(client)
    return q["remaining"], q["limit"], q["name"], q["elapsed_s"]


async def get_pro_remaining(client: GeminiClient) -> tuple[int | None, float]:
    rem, _limit, _name, dt = await get_pro_quota(client)
    return rem, dt


async def init_account_slot(
    profile: str,
    account_idx: int,
    slot_idx: int,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    """Initialize an account once and return an isolated client/shim for each concurrent chat slot."""
    if _is_api_profile(profile):
        lock = ACCOUNT_INIT_LOCKS.setdefault(profile, asyncio.Lock())
        async with lock:
            keys = cb.load_keys()
            email = _coarena_email_label(keys)
            effort_lbl = "high"
            launch_info = {
                "mode": "coarena_api",
                "port": None,
                "stagger_s": 0.0,
                "client_init_s": 0.0,
                "client_init_detail": {"mode": "coarena_api"},
                "daemon_lock_wait_s": 0.0,
                "daemon_start_s": 0.0,
                "argon_high_ok": True,
                "tier": "coarena_api",
                "picker_result": "api_explicit",
                "picker_label": f"{cb.MODEL} ({effort_lbl})",
                "email": email,
                "cap_info": {
                    "argon_high_ok": True,
                    "tier": "coarena_api",
                    "picker_result": "api_explicit",
                    "picker_label": f"{cb.MODEL} ({effort_lbl})",
                    "role": "step_b_only" if COARENA_STEP_B_ONLY else "all",
                },
            }
            return _make_coarena_client_shim(profile, keys), launch_info, await _coarena_quota_snapshot_async()

    import probe_profile_quotas as pq

    lock = ACCOUNT_INIT_LOCKS.setdefault(profile, asyncio.Lock())
    async with lock:
        cached = ACCOUNT_INIT_CACHE.get(profile)
        if cached is None:
            base_client, launch_info = await init_client_with_retry(profile, stagger_s=account_idx * 0.8)
            q0 = await get_pro_quota_rich(base_client)
            cached = {
                "base_client": base_client,
                "launch_info": launch_info,
                "q0": q0,
                "slot1_claimed": slot_idx == 1,
            }
            ACCOUNT_INIT_CACHE[profile] = cached
            if slot_idx == 1:
                return base_client, launch_info, q0

        base_client = cached["base_client"]
        launch_info = dict(cached["launch_info"])
        q0 = dict(cached["q0"])
        if slot_idx == 1 and not cached.get("slot1_claimed"):
            cached["slot1_claimed"] = True
            return base_client, launch_info, q0

        slot_client = GeminiClient(profile_name=profile, timeout=750.0)
        pq.init_client_from_disk(slot_client)
        slot_client._browser_cookies = getattr(base_client, "_browser_cookies", None)
        slot_client._raw_browser_cookies = getattr(base_client, "_raw_browser_cookies", None)
        slot_client._browser_access_token = getattr(base_client, "_browser_access_token", None)
        return slot_client, launch_info, q0


async def safe_close_slot_client(client: Any) -> None:
    """Close HTTP transports on a slot client without shutting down the shared persistent Chrome daemon."""
    if client is None or getattr(client, "_is_coarena_api", False):
        return
    try:
        if getattr(client, "_token_factory", None) is not None:
            client._token_factory._we_launched = False
            client._token_factory._process = None
        await client.close()
    except Exception:
        pass


async def queue_worker(
    worker_idx: int,
    profile: str,
    dedicated_queue: asyncio.Queue[str] | None,
    shared_queue: asyncio.Queue[str],
    requeue_counts: dict[str, int],
    results: dict[str, tuple[bool, str]],
    wl_cache: dict[int, dict[tuple[int, int], dict[str, Any]]],
    mw_cache: dict[int, dict[int, int]],
    min_quota_remaining: int = 220,
    max_batches: int | None = None,
    slot_idx: int = 1,
    chats_per_account: int = 2,
) -> None:
    global IN_FLIGHT_BATCHES
    client: GeminiClient | None = None
    done_count = 0
    faults = 0
    t_worker0 = time.monotonic()
    quota_total_s = 0.0
    idle_wait_s = 0.0
    slot_tag = f"{profile}#{slot_idx}" if chats_per_account > 1 else profile
    with logger.contextualize(profile=slot_tag):
        try:
            ALIVE_WORKERS.add(profile)
            ALIVE_SLOTS.add(slot_tag)
            try:
                client, launch_info, q0 = await init_account_slot(profile, worker_idx, slot_idx)
                cap_info = launch_info.get("cap_info") or {}
                argon_ok = cap_info.get("argon_high_ok")
                rem0, lim0, qname0, q0_s = q0["remaining"], q0["limit"], q0["name"], q0["elapsed_s"]
                reset0_human = q0.get("reset_in_human") or "—"
                reset0_at = q0.get("reset_at")
                if slot_idx == 1:
                    quota_total_s += q0_s
                launch_total_s = round(time.monotonic() - t_worker0, 3)
                qlabel = qname0 or "Thinking/Pro"
                lim_s = lim0 if lim0 is not None else "?"
                reset_str = f" reset_in={reset0_human}" if reset0_human != "—" else ""
                tier_str = (
                    ("API(Step B / demos only)" if COARENA_STEP_B_ONLY else "API(4 Argon High)")
                    if _is_api_profile(profile)
                    else (
                        "PRO(4 Argon High)"
                        if argon_ok is True
                        else (f"NON-PRO({cap_info.get('picker_result')})" if argon_ok is False else "tier=unknown")
                    )
                )
                log(
                    f"[{slot_tag}] Worker slot {slot_idx}/{chats_per_account} ready in {launch_total_s:.2f}s "
                    f"(port={launch_info.get('port')} tier={tier_str}) {qlabel} remaining={rem0}/{lim_s}{reset_str}"
                )
                if slot_idx == 1:
                    await record_event(
                        "worker_launch",
                        surah=SURAH_NUM,
                        profile=profile,
                        chats_per_account=chats_per_account,
                        stagger_s=launch_info.get("stagger_s", 0.0),
                        client_init_s=launch_info.get("client_init_s", 0.0),
                        client_init_detail=launch_info.get("client_init_detail", {}),
                        daemon_lock_wait_s=launch_info.get("daemon_lock_wait_s", 0.0),
                        daemon_start_s=launch_info.get("daemon_start_s", 0.0),
                        quota_s=q0_s,
                        total_s=launch_total_s,
                        remaining=rem0,
                        limit=lim0,
                        reset_in_s=q0.get("reset_in_s"),
                        reset_at=reset0_at,
                        quota_name=qname0,
                        argon_high_ok=argon_ok,
                        picker_result=cap_info.get("picker_result"),
                    )

                if argon_ok is False and cap_info.get("picker_result") != "no_picker":
                    RETIRED_PROFILES.add(profile)
                    if slot_idx == 1:
                        await update_quota_live(
                            profile,
                            email=client.auth_manager.state.email,
                            status="non_pro_downgraded",
                            argon_high_ok=False,
                            tier=cap_info.get("tier"),
                            picker_result=cap_info.get("picker_result"),
                            picker_label=cap_info.get("picker_label"),
                            remaining=rem0,
                            limit=lim0,
                            used_pct=q0.get("used_pct"),
                            left_pct=q0.get("left_pct"),
                            reset_in_s=q0.get("reset_in_s"),
                            reset_in_human=reset0_human,
                            reset_at=reset0_at,
                            name=qlabel,
                        )
                        log(
                            f"[{slot_tag}] Dynamic tier check: account does NOT have 4 Argon High / Pro access "
                            f"(picker={cap_info.get('picker_result')}, label={cap_info.get('picker_label')!r}); "
                            "retiring cleanly before picking any batch."
                        )
                    return

                required_for_slot = min_quota_remaining + ((slot_idx - 1) * EST_CREDITS_PER_INFLIGHT_BATCH)
                while (rem0 is not None and rem0 < required_for_slot) or (
                    _is_api_profile(profile) and _coarena_is_low_quota(q0)
                ):
                    if slot_idx == 1:
                        mark_recoverable_quota_retire(
                            profile, reset0_at, reason="initial_quota"
                        )
                        await update_quota_live(
                            profile,
                            email=client.auth_manager.state.email,
                            status="low_quota",
                            argon_high_ok=argon_ok,
                            tier=cap_info.get("tier"),
                            picker_result=cap_info.get("picker_result"),
                            picker_label=cap_info.get("picker_label"),
                            remaining=rem0,
                            limit=lim0,
                            used_pct=q0.get("used_pct"),
                            left_pct=q0.get("left_pct"),
                            reset_in_s=q0.get("reset_in_s"),
                            reset_in_human=reset0_human,
                            reset_at=reset0_at,
                            api_credits=q0.get("api_credits"),
                            name=qlabel,
                        )
                    elif not is_recoverable_retire(profile):
                        # Slot #1 may not have marked yet; park this slot on the same reset clock.
                        mark_recoverable_quota_retire(
                            profile, reset0_at, reason="initial_quota"
                        )
                    if _is_api_profile(profile) and _coarena_is_low_quota(q0):
                        cr0 = q0.get("api_credits") or {}
                        log(
                            f"[{slot_tag}] Daily API credit low (left=${float(cr0.get('left_usd') or 0):.2f}/${float(cr0.get('usd_per_day') or 0):.0f}{reset_str}); "
                            "parking until daily reset, then auto-unretire."
                        )
                    else:
                        log(
                            f"[{slot_tag}] Initial quota (remaining={rem0}/{lim_s}{reset_str} < {required_for_slot} needed for slot #{slot_idx}); "
                            "parking until 5h reset, then auto-unretire."
                        )
                    resumed = await await_quota_unretire(
                        profile=profile,
                        slot_tag=slot_tag,
                        slot_idx=slot_idx,
                        client=client,
                        required_for_slot=required_for_slot,
                        shared_queue=shared_queue,
                        dedicated_queue=dedicated_queue,
                    )
                    if not resumed:
                        return
                    q0 = await get_pro_quota_rich(client)
                    rem0, lim0, qname0, q0_s = q0["remaining"], q0["limit"], q0["name"], q0["elapsed_s"]
                    reset0_human = q0.get("reset_in_human") or "—"
                    reset0_at = q0.get("reset_at")
                    quota_total_s += q0_s
                    qlabel = qname0 or "Thinking/Pro"
                    lim_s = lim0 if lim0 is not None else "?"
                    reset_str = f" reset_in={reset0_human}" if reset0_human != "—" else ""

                if slot_idx == 1:
                    await update_quota_live(
                        profile,
                        email=client.auth_manager.state.email,
                        status=_idle_status(profile),
                        argon_high_ok=True if argon_ok is None else argon_ok,
                        tier=cap_info.get("tier") or ("coarena_api" if _is_api_profile(profile) else "pro_argon_high"),
                        picker_result=cap_info.get("picker_result"),
                        picker_label=cap_info.get("picker_label"),
                        remaining=rem0,
                        limit=lim0,
                        used_pct=q0.get("used_pct"),
                        left_pct=q0.get("left_pct"),
                        reset_in_s=q0.get("reset_in_s"),
                        reset_in_human=reset0_human,
                        reset_at=reset0_at,
                        api_credits=q0.get("api_credits"),
                        name=qlabel,
                    )
                else:
                    # Stagger slot #2+ slightly so slot #1 acquires profile_lock(profile) first
                    await asyncio.sleep(2.5 * (slot_idx - 1))

                while True:
                    if profile in RETIRED_PROFILES:
                        if is_recoverable_retire(profile):
                            resumed = await await_quota_unretire(
                                profile=profile,
                                slot_tag=slot_tag,
                                slot_idx=slot_idx,
                                client=client,
                                required_for_slot=required_for_slot,
                                shared_queue=shared_queue,
                                dedicated_queue=dedicated_queue,
                            )
                            if resumed:
                                continue
                            if _all_work_finished(shared_queue, dedicated_queue):
                                break
                        log(f"[{slot_tag}] Account {profile} is marked retired; exiting slot #{slot_idx} cleanly.")
                        break
                    if is_drain_requested():
                        log(f"[{slot_tag}] Drain stop requested — not queuing new batches; exiting slot #{slot_idx} cleanly.")
                        break
                    if max_batches is not None and done_count >= max_batches:
                        log(f"[{slot_tag}] Reached max_batches={max_batches}; retiring cleanly.")
                        break

                    bid: str | None = None
                    deferred_failed_only = False
                    if dedicated_queue is not None and not dedicated_queue.empty():
                        bid = dedicated_queue.get_nowait()
                    elif not shared_queue.empty():
                        q_items: list[str] = []
                        while not shared_queue.empty():
                            q_items.append(shared_queue.get_nowait())
                        bid, rem_items, deferred_failed_only, exit_reason = _pick_next_batch_for_worker(
                            profile, q_items, faults
                        )
                        for rem_bid in rem_items:
                            shared_queue.put_nowait(rem_bid)
                        if exit_reason == "step_b_only_no_browser_workers":
                            log(
                                f"[{slot_tag}] Coarena is Step-B-only and no browser workers remain for Step A; "
                                f"exiting slot #{slot_idx} cleanly."
                            )
                            break

                    if bid is None:
                        if is_drain_requested():
                            log(f"[{slot_tag}] Drain stop requested — idle slot #{slot_idx} exiting cleanly.")
                            break
                        if deferred_failed_only or IN_FLIGHT_BATCHES > 0:
                            idle_wait_s += 5.0
                            await asyncio.sleep(5.0)
                            continue
                        break

                    IN_FLIGHT_BATCHES += 1
                    registered_active = False
                    try:
                        q_now = await get_pro_quota_rich(client)
                        rem, lim, qname, q_s = q_now["remaining"], q_now["limit"], q_now["name"], q_now["elapsed_s"]
                        reset_h = q_now.get("reset_in_human") or "—"
                        quota_total_s += q_s
                        sibling_batches = list(ACTIVE_BATCHES_BY_PROFILE.get(profile, []))
                        reserved_for_siblings = len(sibling_batches) * EST_CREDITS_PER_INFLIGHT_BATCH
                        effective_rem = (int(rem) - reserved_for_siblings) if rem is not None else None

                        if (rem is not None and int(rem) < min_quota_remaining) or (
                            _is_api_profile(profile) and _coarena_is_low_quota(q_now)
                        ):
                            reset_target = q_now.get("reset_at")
                            if _is_api_profile(profile) and not reset_target:
                                reset_target = (datetime.now().astimezone() + timedelta(minutes=15)).isoformat(timespec="seconds")
                            mark_recoverable_quota_retire(
                                profile, reset_target, reason="low_quota"
                            )
                            lim_s = lim if lim is not None else "?"
                            qlabel = qname or "Thinking/Pro"
                            await update_quota_live(
                                profile,
                                status="low_quota",
                                remaining=rem,
                                limit=lim,
                                used_pct=q_now.get("used_pct"),
                                left_pct=q_now.get("left_pct"),
                                reset_in_s=q_now.get("reset_in_s"),
                                reset_in_human=reset_h,
                                reset_at=q_now.get("reset_at"),
                                api_credits=q_now.get("api_credits"),
                                name=qlabel,
                            )
                            cr_now = q_now.get("api_credits") if isinstance(q_now.get("api_credits"), dict) else {}
                            if _is_api_profile(profile) and cr_now.get("ok"):
                                log(
                                    f"[{slot_tag}] API credit low (left=${float(cr_now.get('left_usd') or 0):.2f}/${float(cr_now.get('usd_per_day') or 0):.0f} "
                                    f"< ${COARENA_MIN_USD_LEFT:.2f}, reset_in={reset_h}); returning {bid} to shared pool & stopping until reset."
                                )
                            else:
                                log(
                                    f"[{slot_tag}] Quota low ({qlabel} remaining={rem}/{lim_s} reset_in={reset_h}); "
                                    f"returning {bid} to shared pool & parking until reset (auto-unretire)."
                                )
                            shared_queue.put_nowait(bid)
                            # `continue` runs try/finally (decr IN_FLIGHT), then top-of-loop await_quota_unretire.
                            continue

                        if _is_api_profile(profile):
                            cr_now = q_now.get("api_credits") if isinstance(q_now.get("api_credits"), dict) else {}
                            if not cr_now.get("ok"):
                                log(f"[{slot_tag}] API quota probe unavailable ({cr_now.get('error') or 'unknown'}); returning {bid} to pool & waiting 15s.")
                                shared_queue.put_nowait(bid)
                                await asyncio.sleep(15.0)
                                continue
                            if sibling_batches and not _coarena_has_usable_quota(q_now, slots_needed=1 + len(sibling_batches)):
                                log(
                                    f"[{slot_tag}] API credit left=${float(cr_now.get('left_usd') or 0):.2f} reserved for sibling batch(es) "
                                    f"{sibling_batches}; returning {bid} to shared pool & waiting 30s on slot #{slot_idx}."
                                )
                                shared_queue.put_nowait(bid)
                                await asyncio.sleep(30.0)
                                continue

                        if effective_rem is not None and effective_rem < min_quota_remaining:
                            lim_s = lim if lim is not None else "?"
                            log(
                                f"[{slot_tag}] Quota remaining={rem}/{lim_s} has {reserved_for_siblings}cr reserved for sibling batch(es) "
                                f"{sibling_batches} (effective_rem={effective_rem} < {min_quota_remaining}); returning {bid} to shared pool & waiting 30s on slot #{slot_idx}."
                            )
                            shared_queue.put_nowait(bid)
                            await asyncio.sleep(30.0)
                            continue

                        active_list = ACTIVE_BATCHES_BY_PROFILE.setdefault(profile, [])
                        if bid not in active_list:
                            active_list.append(bid)
                        registered_active = True
                        if len(active_list) > 1:
                            for ab in active_list:
                                OVERLAPPED_BATCHES.add(ab)

                        await update_quota_live(
                            profile,
                            status="active_busy",
                            current_batch=", ".join(active_list),
                            remaining=rem,
                            limit=lim,
                            used_pct=q_now.get("used_pct"),
                            left_pct=q_now.get("left_pct"),
                            reset_in_s=q_now.get("reset_in_s"),
                            reset_in_human=reset_h,
                            reset_at=q_now.get("reset_at"),
                            api_credits=q_now.get("api_credits"),
                            name=qname or "Thinking/Pro",
                        )
                        start_ay, end_ay = BATCH_RANGE_MAP[bid]
                        sib_str = f" [concurrent with {sibling_batches}]" if sibling_batches else ""
                        rem_log = f" (remaining={rem}/{lim} reset_in={reset_h}){sib_str}" if rem is not None else sib_str
                        log(f"[{slot_tag}] Picked up {bid} ({start_ay}..{end_ay}){rem_log}")
                        prog_before = PROGRESS.get(bid, 0)
                        ok, info = await process_batch(profile, client, bid, start_ay, end_ay, wl_cache, mw_cache)
                        if len(ACTIVE_BATCHES_BY_PROFILE.get(profile, [])) > 1:
                            for ab in ACTIVE_BATCHES_BY_PROFILE.get(profile, []):
                                OVERLAPPED_BATCHES.add(ab)
                        if registered_active and bid in ACTIVE_BATCHES_BY_PROFILE.get(profile, []):
                            ACTIVE_BATCHES_BY_PROFILE[profile].remove(bid)
                            registered_active = False
                        q_after = await get_pro_quota_rich(client, force=_is_api_profile(profile))
                        quota_total_s += q_after["elapsed_s"]
                        window_delta: int | None = None
                        if (
                            rem is not None
                            and q_after.get("remaining") is not None
                            and lim == q_after.get("limit")
                            and int(rem) >= int(q_after["remaining"])
                        ):
                            window_delta = int(rem) - int(q_after["remaining"])
                        was_overlapped = bid in OVERLAPPED_BATCHES
                        measured_delta = None if was_overlapped else window_delta
                        await update_status(
                            bid,
                            worker_slot=slot_tag,
                            concurrent_same_account=was_overlapped,
                            quota_before=rem,
                            quota_after=q_after.get("remaining"),
                            quota_limit=q_after.get("limit") or lim,
                            quota_measured_delta=measured_delta,
                            quota_shared_window_delta=window_delta if was_overlapped else None,
                        )
                        still_active = list(ACTIVE_BATCHES_BY_PROFILE.get(profile, []))
                        await update_quota_live(
                            profile,
                            status="active_busy" if still_active else _idle_status(profile),
                            current_batch=", ".join(still_active) if still_active else None,
                            remaining=q_after["remaining"],
                            limit=q_after["limit"],
                            used_pct=q_after.get("used_pct"),
                            left_pct=q_after.get("left_pct"),
                            reset_in_s=q_after.get("reset_in_s"),
                            reset_in_human=q_after.get("reset_in_human"),
                            reset_at=q_after.get("reset_at"),
                            api_credits=q_after.get("api_credits"),
                        )
                        if ok:
                            results[bid] = (True, info)
                            done_count += 1
                            faults = 0
                        else:
                            # Soft failure (incomplete Step B / validate) used to park the
                            # batch forever. Requeue like the exception path so another
                            # profile can finish it.
                            log(f"[{slot_tag}][{bid}] SOFT FAIL: {info}")
                            FAILED_ON.setdefault(bid, set()).add(profile)
                            prog_after = PROGRESS.get(bid, 0)
                            if prog_after > prog_before:
                                log(
                                    f"[{slot_tag}][{bid}] Progress made (turns {prog_before}->{prog_after}); "
                                    f"requeueing {bid} without incrementing requeue/faults "
                                    f"(requeue={requeue_counts.get(bid, 0)}/4, faults={faults})"
                                )
                                shared_queue.put_nowait(bid)
                            else:
                                requeue_counts[bid] = requeue_counts.get(bid, 0) + 1
                                if requeue_counts[bid] <= 4:
                                    log(
                                        f"[{slot_tag}][{bid}] Requeueing {bid} "
                                        f"(attempt {requeue_counts[bid]}/4) to shared pool after soft fail"
                                    )
                                    shared_queue.put_nowait(bid)
                                else:
                                    results[bid] = (False, f"parked after 4 requeues: {info}")
                                faults += 1
                                if faults >= 2:
                                    log(
                                        f"[{slot_tag}] {faults} consecutive batch faults; "
                                        "cooling down slot for 45s and resetting fault counter."
                                    )
                                    faults = 0
                                    await asyncio.sleep(45.0)
                    except _BatchHandoff as ho:
                        if registered_active and bid in ACTIVE_BATCHES_BY_PROFILE.get(profile, []):
                            ACTIVE_BATCHES_BY_PROFILE[profile].remove(bid)
                            registered_active = False
                        still_active = list(ACTIVE_BATCHES_BY_PROFILE.get(profile, []))
                        await update_quota_live(
                            profile,
                            status="active_busy" if still_active else _idle_status(profile),
                            current_batch=", ".join(still_active) if still_active else None,
                        )
                        if ho.kind == "step_b_handoff":
                            faults = 0
                        shared_queue.put_nowait(bid)
                        if ho.kind == "needs_step_a":
                            log(ho.reason)
                            await asyncio.sleep(5.0)
                        continue
                    except Exception as exc:
                        if registered_active and bid in ACTIVE_BATCHES_BY_PROFILE.get(profile, []):
                            ACTIVE_BATCHES_BY_PROFILE[profile].remove(bid)
                            registered_active = False
                        if _is_terminal_worker_error(exc):
                            # Account/worker-level failure must NEVER increment requeue_counts[bid].
                            FAILED_ON.setdefault(bid, set()).add(profile)
                            shared_queue.put_nowait(bid)
                            if _is_usage_limit_error(exc):
                                # Hard quota limit — recoverable after the reset clock.
                                q_lim = await get_pro_quota_rich(client, force=True)
                                reset_target = q_lim.get("reset_at")
                                if _is_api_profile(profile) and not reset_target:
                                    reset_target = (datetime.now().astimezone() + timedelta(minutes=15)).isoformat(timespec="seconds")
                                mark_recoverable_quota_retire(
                                    profile, reset_target, reason="usage_limit"
                                )
                                await update_quota_live(
                                    profile,
                                    status="retired_UsageLimitExceeded",
                                    current_batch=None,
                                    remaining=q_lim.get("remaining"),
                                    limit=q_lim.get("limit"),
                                    used_pct=q_lim.get("used_pct"),
                                    left_pct=q_lim.get("left_pct"),
                                    reset_in_s=q_lim.get("reset_in_s"),
                                    reset_in_human=q_lim.get("reset_in_human"),
                                    reset_at=reset_target,
                                    api_credits=q_lim.get("api_credits"),
                                    last_error=f"{type(exc).__name__}: {str(exc)[:140]}",
                                )
                                log(
                                    f"[{slot_tag}][{bid}] WORKER PARK ({type(exc).__name__}: {exc}); "
                                    f"returning {bid} to shared pool; stopping retries until reset."
                                )
                                continue
                            if _is_high_downgrade_error(exc):
                                # 5h quota hit 0 mid-batch OR transient verification/downgrade blip:
                                # park for reset / short cooldown instead of permanently killing worker.
                                q_lim = await get_pro_quota_rich(client, force=True)
                                rem_lim = q_lim.get("remaining")
                                low_q = rem_lim is not None and int(rem_lim) < min_quota_remaining
                                if low_q and q_lim.get("reset_at"):
                                    reset_target = q_lim.get("reset_at")
                                    park_reason = "high_downgrade_low_quota"
                                    status_val = "low_quota"
                                else:
                                    reset_target = (
                                        datetime.now().astimezone() + timedelta(minutes=10)
                                    ).isoformat(timespec="seconds")
                                    park_reason = "high_downgrade_cooldown"
                                    status_val = "retired_HighDowngradeCooldown"
                                mark_recoverable_quota_retire(
                                    profile, reset_target, reason=park_reason
                                )
                                await update_quota_live(
                                    profile,
                                    status=status_val,
                                    current_batch=None,
                                    remaining=rem_lim,
                                    limit=q_lim.get("limit"),
                                    used_pct=q_lim.get("used_pct"),
                                    left_pct=q_lim.get("left_pct"),
                                    reset_in_s=q_lim.get("reset_in_s"),
                                    reset_in_human=q_lim.get("reset_in_human"),
                                    reset_at=reset_target,
                                    api_credits=q_lim.get("api_credits"),
                                    last_error=f"{type(exc).__name__}: {str(exc)[:140]}",
                                )
                                log(
                                    f"[{slot_tag}][{bid}] WORKER PARK ({type(exc).__name__}: {exc}); "
                                    f"returning {bid} to shared pool; auto-unretire scheduled ({park_reason})."
                                )
                                continue
                            if _is_token_factory_error(exc):
                                err_low = str(exc).lower()
                                is_sorry = "google.com/sorry" in err_low
                                cooldown_s = 300 if is_sorry else 180
                                if not is_sorry:
                                    await asyncio.to_thread(_heal_profile_session_sync, profile, 2, True)
                                reset_target = (
                                    datetime.now().astimezone() + timedelta(seconds=cooldown_s)
                                ).isoformat(timespec="seconds")
                                mark_recoverable_quota_retire(
                                    profile, reset_target, reason="token_factory_cooldown"
                                )
                                await update_quota_live(
                                    profile,
                                    status="retired_TokenFactoryCooldown",
                                    current_batch=None,
                                    reset_in_s=cooldown_s,
                                    reset_in_human=f"{cooldown_s // 60}m 00s",
                                    reset_at=reset_target,
                                    last_error=f"{type(exc).__name__}: {str(exc)[:140]}",
                                )
                                log(
                                    f"[{slot_tag}][{bid}] WORKER PARK ({type(exc).__name__}: {exc}); "
                                    f"returning {bid} to shared pool; auto-unretire in {cooldown_s // 60}m."
                                )
                                continue
                            RETIRED_PROFILES.add(profile)
                            RETIRED_REASON[profile] = type(exc).__name__
                            RETIRED_UNTIL.pop(profile, None)
                            await update_quota_live(
                                profile,
                                status=f"retired_{type(exc).__name__}",
                                current_batch=None,
                                last_error=f"{type(exc).__name__}: {str(exc)[:140]}",
                            )
                            log(
                                f"[{slot_tag}][{bid}] WORKER RETIRE ({type(exc).__name__}: {exc}); "
                                f"returning {bid} to shared pool (without penalizing batch) & retiring {profile}!"
                            )
                            break
                        log(f"[{slot_tag}][{bid}] UNHANDLED ERROR: {type(exc).__name__}: {exc}")
                        await update_status(batch_id=bid, profile=profile, worker_slot=slot_tag, stage="error", error=f"{type(exc).__name__}: {exc}")
                        FAILED_ON.setdefault(bid, set()).add(profile)
                        prog_after = PROGRESS.get(bid, 0)
                        if prog_after > prog_before:
                            log(
                                f"[{slot_tag}][{bid}] Progress made (turns {prog_before}->{prog_after}); "
                                f"requeueing {bid} without incrementing requeue/faults (requeue={requeue_counts.get(bid, 0)}/4, faults={faults})"
                            )
                            shared_queue.put_nowait(bid)
                        else:
                            requeue_counts[bid] = requeue_counts.get(bid, 0) + 1
                            if requeue_counts[bid] <= 4:
                                log(f"[{slot_tag}][{bid}] Requeueing {bid} (attempt {requeue_counts[bid]}/4) to shared pool")
                                shared_queue.put_nowait(bid)
                            else:
                                results[bid] = (False, f"parked after 4 requeues: {exc}")
                            faults += 1
                            if faults >= 2:
                                log(
                                    f"[{slot_tag}] {faults} consecutive batch faults; "
                                    "cooling down slot for 45s and resetting fault counter."
                                )
                                faults = 0
                                await asyncio.sleep(45.0)
                    finally:
                        if registered_active and bid and bid in ACTIVE_BATCHES_BY_PROFILE.get(profile, []):
                            ACTIVE_BATCHES_BY_PROFILE[profile].remove(bid)
                        IN_FLIGHT_BATCHES -= 1
            finally:
                ALIVE_SLOTS.discard(slot_tag)
                if not any(s == profile or s.startswith(f"{profile}#") for s in ALIVE_SLOTS):
                    ALIVE_WORKERS.discard(profile)
        except Exception as init_exc:
            log(f"[{slot_tag}] Worker failed during init: {init_exc}")
            await update_quota_live(profile, status="init_error", last_error=str(init_exc)[:140])
        finally:
            worker_total_s = round(time.monotonic() - t_worker0, 2)
            log(
                f"[{slot_tag}] Worker slot exiting after {worker_total_s/60:.1f}m "
                f"(batches={done_count}, faults={faults}, quota_checks={quota_total_s:.1f}s, idle_wait={idle_wait_s:.1f}s)"
            )
            await record_event(
                "worker_exit", surah=SURAH_NUM, profile=profile, slot=slot_tag, total_s=worker_total_s,
                batches=done_count, faults=faults, quota_s=round(quota_total_s, 2), idle_wait_s=round(idle_wait_s, 1),
            )
            await safe_close_slot_client(client)


def _batch_input_size(batch_id: str) -> int:
    p = u.PROTO / f"{batch_id}_input.json"
    try:
        return p.stat().st_size if p.exists() else 0
    except OSError:
        return 0


async def run_queue(
    profiles: list[str],
    target_batches: list[str] | None = None,
    surah: int | None = None,
    chats_per_account: int = 2,
    surah_list: list[int] | None = None,
) -> int:
    """Run one Surah, or a shared pool across ``surah_list`` (lower Surah batches first)."""
    global IN_FLIGHT_BATCHES, CHATS_PER_ACCOUNT, BATCH_RANGE_MAP, SURAH_BATCHES
    CHATS_PER_ACCOUNT = max(1, int(chats_per_account))

    if surah_list is None:
        if surah is not None:
            surah_list = [int(surah)]
        elif target_batches:
            found = sorted({surah_from_batch(b) for b in target_batches})
            surah_list = found or [SURAH_NUM]
        else:
            surah_list = [SURAH_NUM]
    surah_list = [int(s) for s in surah_list]
    configure_surah(surah_list[0])

    IN_FLIGHT_BATCHES = 0
    PROGRESS.clear()
    FAILED_ON.clear()
    LAST_END.clear()
    STEP_A_SECONDS.clear()
    ALIVE_WORKERS.clear()
    ALIVE_SLOTS.clear()
    ACTIVE_BATCHES_BY_PROFILE.clear()
    OVERLAPPED_BATCHES.clear()
    RETIRED_PROFILES.clear()
    RETIRED_UNTIL.clear()
    RETIRED_REASON.clear()
    ACCOUNT_INIT_LOCKS.clear()
    ACCOUNT_INIT_CACHE.clear()
    global _PACE_LOCK, _LAST_GLOBAL_ACTION_TS
    _PACE_LOCK = None
    _LAST_GLOBAL_ACTION_TS = 0.0
    _LAST_ACCOUNT_ACTION_TS.clear()
    STATUS_STATE_BY_SURAH.clear()
    SURAH_BATCHES.clear()

    t0 = time.monotonic()
    lookup_nums = sorted({*surah_list, min(114, max(surah_list) + 1)})
    t_wl0 = time.monotonic()
    wl_cache, mw_cache = u.get_word_lookups(tuple(lookup_nums))
    lookup_load_s = round(time.monotonic() - t_wl0, 3)

    BATCH_RANGE_MAP = {}
    all_batches: list[str] = []
    for s in surah_list:
        discovered = discover_surah_batches(s)
        SURAH_BATCHES[s] = list(discovered)
        for bid, a, b in discovered:
            if target_batches is not None and bid not in target_batches:
                continue
            BATCH_RANGE_MAP[bid] = (a, b)
            all_batches.append(bid)
    if target_batches:
        for b in target_batches:
            if b not in BATCH_RANGE_MAP:
                m = BATCH_ID_RE.match(b)
                if m:
                    BATCH_RANGE_MAP[b] = (int(m.group(2)), int(m.group(3)))
                    if b not in all_batches:
                        all_batches.append(b)

    # Priority: lower Surah first; within Surah larger inputs first
    all_batches.sort(key=lambda bid: (surah_from_batch(bid), -_batch_input_size(bid), bid))

    shared_q: BatchPriorityQueue = BatchPriorityQueue()
    requeue_counts: dict[str, int] = {}
    for b in all_batches:
        shared_q.put_nowait(b)

    ordered_summary = [f"{b}({_batch_input_size(b)}B)" for b in all_batches[:12]]
    total_slots = sum(_profile_slot_count(p) for p in profiles)
    slot_summary = ", ".join(f"{p}×{_profile_slot_count(p)}" for p in profiles)
    range_label = (
        f"Surah {surah_list[0]}"
        if len(surah_list) == 1
        else f"Surahs {surah_list[0]}..{surah_list[-1]} (shared pool, lower-Surah priority)"
    )
    log(
        f"Starting {range_label} parallel Argon High extraction across {len(profiles)} workers [{slot_summary}] "
        f"({total_slots} total concurrent slots) "
        f"for {len(all_batches)} batches (priority lower-Surah first: {', '.join(ordered_summary)}"
        f"{'…' if len(all_batches) > 12 else ''}; lookups loaded in {lookup_load_s:.2f}s)"
    )
    results: dict[str, tuple[bool, str]] = {}
    ALIVE_WORKERS.update(profiles)
    coros = []
    for idx, prof in enumerate(profiles):
        prof_slots = _profile_slot_count(prof)
        for slot_idx in range(1, prof_slots + 1):
            coros.append(
                queue_worker(
                    idx,
                    prof,
                    None,
                    shared_q,
                    requeue_counts,
                    results,
                    wl_cache,
                    mw_cache,
                    min_quota_remaining=240,
                    max_batches=None,
                    slot_idx=slot_idx,
                    chats_per_account=prof_slots,
                )
            )

    await asyncio.gather(*coros)
    drained = is_drain_requested()
    while not shared_q.empty():
        b = shared_q.get_nowait()
        results.setdefault(
            b,
            (False, "drained (graceful stop requested)" if drained else "not picked up / all workers retired"),
        )

    dt = time.monotonic() - t0
    ok_cnt = sum(1 for ok, _ in results.values() if ok)
    try:
        ledger = build_all_surahs_ledger(surahs=surah_list)
    except Exception:
        ledger = {}
    await record_event(
        "run_done",
        surah=surah_list[0],
        surahs=surah_list,
        wall_s=round(dt, 2),
        lookup_load_s=lookup_load_s,
        ok=ok_cnt,
        total=len(all_batches),
        profiles=profiles,
        chats_per_account=CHATS_PER_ACCOUNT,
    )
    log(
        f"Finished {range_label} {ok_cnt}/{len(all_batches)} batches OK in {dt/60:.1f}m "
        + ("(drain stop — active batches finished, queue left for resume)" if drained else "(shared pool; lower-Surah priority)")
    )
    for s in surah_list:
        s_led = ((ledger.get("surahs") or {}).get(str(s)) or {}) if isinstance(ledger, dict) else {}
        s_batches = [b for b in all_batches if surah_from_batch(b) == s]
        s_ok = sum(1 for b in s_batches if results.get(b, (False, ""))[0])
        log(
            f"  Surah {s} ({surah_name(s)}): {s_ok}/{len(s_batches)} OK | "
            f"Quota={s_led.get('quota_credits_used', 0):,}cr "
            f"Tokens={s_led.get('total_tokens', 0):,} "
            f"Est.Cost=${float(s_led.get('estimated_cost_usd') or 0):.2f}"
        )
        for bid in s_batches:
            ok, info = results.get(bid, (False, "missing"))
            if not ok:
                log(f"    {bid}: FAIL ({info[:120]})")
    return 0 if ok_cnt == len(all_batches) else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generalized Parallel 4 Argon High Waqf & Ibtida Runner for any Surah (1..114)")
    p.add_argument(
        "--surah",
        type=int,
        default=6,
        help="Surah number (1..114, default: 6). Ignored when --from-surah is set.",
    )
    p.add_argument("--from-surah", type=int, default=None, help="Shared-pool mode: first Surah")
    p.add_argument("--to-surah", type=int, default=None, help="Shared-pool mode: last Surah (default=from-surah)")
    p.add_argument(
        "--profiles",
        default=",".join(DEFAULT_PROFILES_4),
        help="Comma-separated list of candidate profiles (dynamic Argon High check filters non-Pro accounts)",
    )
    p.add_argument(
        "--chats-per-account",
        type=int,
        default=2,
        help="Number of simultaneous chat worker slots per account (default: 2 -> 4 Pro accounts × 2 = 8 parallel chats)",
    )
    p.add_argument(
        "--batches",
        default="",
        help="Optional comma-separated subset of batch IDs",
    )
    p.add_argument(
        "--coarena-effort",
        default="high",
        help="Reasoning effort for coarena API worker (locked to high only)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.coarena_effort and str(args.coarena_effort).strip().lower() != "high":
        raise SystemExit(f"Invalid --coarena-effort={args.coarena_effort!r}: coarena is locked to 'high' only")
    cb.EFFORT_OVERRIDE = "high"
    profs = [x.strip() for x in args.profiles.split(",") if x.strip()]
    batches = [x.strip() for x in args.batches.split(",") if x.strip()] or None
    surah_list = None
    if args.from_surah is not None:
        to_s = args.to_surah if args.to_surah is not None else args.from_surah
        surah_list = list(range(int(args.from_surah), int(to_s) + 1))
    raise SystemExit(
        asyncio.run(
            run_queue(
                profs,
                batches,
                surah=args.surah,
                chats_per_account=args.chats_per_account,
                surah_list=surah_list,
            )
        )
    )
