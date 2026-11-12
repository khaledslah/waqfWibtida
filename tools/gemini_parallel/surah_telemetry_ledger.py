#!/usr/bin/env python3
"""General multi-Surah telemetry, quota, token, and cost ledger builder.

Computes and records:
- Per-turn & per-batch quota credits used (120 credits per 4 Argon High turn in qpEbW,
  or exact measured delta when available).
- Estimated tokens per turn & per batch:
  - new_input_tokens (~2.8 chars/token for Arabic+JSON prompts)
  - context_input_tokens (accumulated prior turns in same_chat sessions)
  - thinking_tokens (~3.5 chars/token for reasoning thoughts)
  - output_tokens (~2.8 chars/token for Arabic+JSON output)
  - total_tokens
- Estimated equivalent frontier API cost ($USD):
  - $2.00 / 1M new input tokens
  - $0.50 / 1M cached same-chat context input tokens
  - $12.00 / 1M output + thinking tokens
- Groups batches by the account (profile) that handled them, and persists the
  complete ledger to surah_telemetry_ledger.json.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

SCRATCH = Path(__file__).resolve().parent
PROTO = Path(r"D:\AI_Projects\waqfWibtida2\data\llm_prototype")
TURNS_FILE = SCRATCH / "turns.jsonl"
EVENTS_FILE = SCRATCH / "timing_events.jsonl"
QUOTAS_LIVE_FILE = SCRATCH / "quotas_live.json"
LEDGER_FILE = SCRATCH / "surah_telemetry_ledger.json"

# Observed qpEbW deduction per 4 Argon High turn:
# 120 credits per turn (= 5% of the 2,400 5h-reset pool, or 0.248% of the 48,384 weekly pool)
CREDITS_PER_ARGON_HIGH_TURN = 120
BURST_POOL_LIMIT = 2400
MACRO_POOL_LIMIT = 48384

# Equivalent Frontier Reasoning API Pricing (Gemini Pro / Argon High / GPT-5.4 class)
PRICE_NEW_INPUT_PER_M = 2.00
PRICE_CACHED_INPUT_PER_M = 0.50
PRICE_OUTPUT_THINK_PER_M = 12.00

SURAH_NAMES_AR: dict[int, str] = {
    1: "الفاتحة", 2: "البقرة", 3: "آل عمران", 4: "النساء", 5: "المائدة",
    6: "الأنعام", 7: "الأعراف", 8: "الأنفال", 9: "التوبة", 10: "يونس",
    11: "هود", 12: "يوسف", 13: "الرعد", 14: "إبراهيم", 15: "الحجر",
    16: "النحل", 17: "الإسراء", 18: "الكهف", 19: "مريم", 20: "طه",
    21: "الأنبياء", 22: "الحج", 23: "المؤمنون", 24: "النور", 25: "الفرقان",
    26: "الشعراء", 27: "النمل", 28: "القصص", 29: "العنكبوت", 30: "الروم",
    35: "فاطر", 36: "يس", 42: "الشورى", 47: "محمد", 52: "الطور",
    53: "النجم", 65: "الطلاق", 78: "النبأ", 81: "التكوير", 105: "الفيل", 106: "قريش",
}


def fmt_12h(dt: datetime | None = None, include_seconds: bool = True) -> str:
    """Format a datetime in 12-hour AM/PM style (e.g. '11:54:32 PM' or '02:44 AM')."""
    if dt is None:
        dt = datetime.now().astimezone()
    fmt = "%I:%M:%S %p" if include_seconds else "%I:%M %p"
    return dt.strftime(fmt)


def fmt_iso_to_12h(ts_str: str | None, include_seconds: bool = True, include_date: bool = False) -> str:
    """Convert an ISO timestamp or HH:MM:SS string into 12-hour AM/PM format."""
    if not ts_str:
        return "—"
    s = str(ts_str).strip()
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        time_part = fmt_12h(dt, include_seconds=include_seconds)
        if include_date:
            return f"{dt.strftime('%Y-%m-%d')} {time_part}"
        return time_part
    except Exception:
        pass
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        ss = int(m.group(3) or 0)
        ampm = "AM" if hh < 12 else "PM"
        hh12 = hh % 12 or 12
        if include_seconds and m.group(3) is not None:
            return f"{hh12:02d}:{mm:02d}:{ss:02d} {ampm}"
        return f"{hh12:02d}:{mm:02d} {ampm}"
    return s


FREE_POOL_LIMIT = 12096


def explain_plan_limit(limit: int | None, argon_high_ok: bool | None) -> dict[str, str]:
    """Explain what Google's qpEbW plan limit number means for this account."""
    if argon_high_ok is False or limit == FREE_POOL_LIMIT:
        return {
            "bucket_type": "Free / Auto Pool (12,096)",
            "short_label": "Free/Auto pool (no 4 Argon High)",
            "explanation": (
                "12,096 is Google's standard Free/Auto general-chat credit pool. "
                "This account does not have active Pro / 4 Argon High access in the model picker."
            ),
        }
    if limit == BURST_POOL_LIMIT:
        return {
            "bucket_type": "5h Reset Burst Cap (2,400)",
            "short_label": "5h reset (~20 Argon High turns @ 120 cr/turn)",
            "explanation": (
                "2,400 = 5-hour rolling reset burst cap. "
                "Each 4 Argon High turn uses 120 credits (~20 turns per 5h window). "
                "Google's qpEbW RPC reports whichever bucket (2,400 5h vs 48,384 weekly) "
                "has the higher % used right now."
            ),
        }
    if limit == MACRO_POOL_LIMIT:
        return {
            "bucket_type": "Weekly Pro Pool (48,384)",
            "short_label": "Weekly pool (~403 Argon High turns @ 120 cr/turn)",
            "explanation": (
                "48,384 = weekly Pro credit pool (~403 Argon High turns at 120 credits/turn). "
                "Shown when the 5h burst window is freshly reset (0% used) so the weekly pool "
                "has the higher % used."
            ),
        }
    return {
        "bucket_type": f"Plan Pool ({limit or '?'})",
        "short_label": "Pro/Thinking credit pool",
        "explanation": "Server-reported credit pool from Google's qpEbW usage RPC (~120 credits per 4 Argon High turn).",
    }


def _pool_snapshot(
    *,
    key: str,
    label: str,
    limit: int,
    remaining: int | None,
    used_pct: float | None = None,
    left_pct: float | None = None,
    reset_in_s: int | None = None,
    reset_in_human: str | None = None,
    reset_at: str | None = None,
    reset_at_12h: str | None = None,
    last_seen_at: str | None = None,
    binding: bool = False,
    known: bool = False,
) -> dict[str, Any]:
    if remaining is not None and limit > 0:
        if used_pct is None:
            used_pct = round(100.0 * (limit - remaining) / limit, 1)
        if left_pct is None:
            left_pct = round(100.0 * remaining / limit, 1)
        known = True
    return {
        "key": key,
        "label": label,
        "limit": limit,
        "remaining": remaining,
        "used_pct": used_pct,
        "left_pct": left_pct,
        "reset_in_s": reset_in_s,
        "reset_in_human": reset_in_human,
        "reset_at": reset_at,
        "reset_at_12h": reset_at_12h,
        "lastSeenAt": last_seen_at,
        "binding": binding,
        "known": known,
    }


def merge_quota_pools(entry: dict[str, Any], prev_pools: dict[str, Any] | None = None) -> dict[str, Any]:
    """Keep both Pro pools (5h + weekly) per account.

    qpEbW returns only the currently binding bucket. We cache the last-seen
    reading for each pool so the dashboard can always show both.
    """
    prev_pools = prev_pools if isinstance(prev_pools, dict) else {}
    argon_ok = entry.get("argon_high_ok")
    rem = entry.get("remaining")
    lim = entry.get("limit")
    try:
        rem_i = int(rem) if rem is not None else None
    except (TypeError, ValueError):
        rem_i = None
    try:
        lim_i = int(lim) if lim is not None else None
    except (TypeError, ValueError):
        lim_i = None

    seen_at = entry.get("lastSeenAt")
    used_pct = entry.get("used_pct")
    left_pct = entry.get("left_pct")
    reset_in_s = entry.get("reset_in_s")
    reset_in_human = entry.get("reset_in_human")
    reset_at = entry.get("reset_at")
    reset_at_12h = entry.get("reset_at_12h")

    def _keep(key: str, label: str, default_limit: int) -> dict[str, Any]:
        prev = prev_pools.get(key) if isinstance(prev_pools.get(key), dict) else {}
        return _pool_snapshot(
            key=key,
            label=label,
            limit=int(prev.get("limit") or default_limit),
            remaining=prev.get("remaining"),
            used_pct=prev.get("used_pct"),
            left_pct=prev.get("left_pct"),
            reset_in_s=prev.get("reset_in_s"),
            reset_in_human=prev.get("reset_in_human"),
            reset_at=prev.get("reset_at"),
            reset_at_12h=prev.get("reset_at_12h"),
            last_seen_at=prev.get("lastSeenAt"),
            binding=False,
            known=bool(prev.get("known") and prev.get("remaining") is not None),
        )

    if argon_ok is False or lim_i == FREE_POOL_LIMIT:
        free = _pool_snapshot(
            key="free",
            label="Free / Auto",
            limit=FREE_POOL_LIMIT,
            remaining=rem_i,
            used_pct=float(used_pct) if used_pct is not None else None,
            left_pct=float(left_pct) if left_pct is not None else None,
            reset_in_s=reset_in_s,
            reset_in_human=reset_in_human,
            reset_at=reset_at,
            reset_at_12h=reset_at_12h,
            last_seen_at=seen_at,
            binding=True,
            known=rem_i is not None,
        )
        return {"free": free}

    burst = _keep("burst_5h", "5h reset", BURST_POOL_LIMIT)
    weekly = _keep("weekly", "Weekly", MACRO_POOL_LIMIT)

    # Seed weekly from a prior start_remaining if it looked like the macro pool.
    if not weekly.get("known"):
        try:
            start_rem = int(entry.get("start_remaining")) if entry.get("start_remaining") is not None else None
        except (TypeError, ValueError):
            start_rem = None
        if start_rem is not None and start_rem > BURST_POOL_LIMIT:
            weekly = _pool_snapshot(
                key="weekly",
                label="Weekly",
                limit=MACRO_POOL_LIMIT,
                remaining=min(start_rem, MACRO_POOL_LIMIT),
                last_seen_at=seen_at,
                binding=False,
                known=True,
            )

    binding_key = None
    if lim_i == BURST_POOL_LIMIT:
        binding_key = "burst_5h"
        burst = _pool_snapshot(
            key="burst_5h",
            label="5h reset",
            limit=BURST_POOL_LIMIT,
            remaining=rem_i,
            used_pct=float(used_pct) if used_pct is not None else None,
            left_pct=float(left_pct) if left_pct is not None else None,
            reset_in_s=reset_in_s,
            reset_in_human=reset_in_human,
            reset_at=reset_at,
            reset_at_12h=reset_at_12h,
            last_seen_at=seen_at,
            binding=True,
            known=rem_i is not None,
        )
    elif lim_i == MACRO_POOL_LIMIT:
        binding_key = "weekly"
        weekly = _pool_snapshot(
            key="weekly",
            label="Weekly",
            limit=MACRO_POOL_LIMIT,
            remaining=rem_i,
            used_pct=float(used_pct) if used_pct is not None else None,
            left_pct=float(left_pct) if left_pct is not None else None,
            reset_in_s=reset_in_s,
            reset_in_human=reset_in_human,
            reset_at=reset_at,
            reset_at_12h=reset_at_12h,
            last_seen_at=seen_at,
            binding=True,
            known=rem_i is not None,
        )
    elif lim_i is not None and rem_i is not None:
        # Unknown Pro limit — still keep both standard pools and mark current as other.
        other = _pool_snapshot(
            key="other",
            label=f"Plan ({lim_i})",
            limit=lim_i,
            remaining=rem_i,
            used_pct=float(used_pct) if used_pct is not None else None,
            left_pct=float(left_pct) if left_pct is not None else None,
            reset_in_s=reset_in_s,
            reset_in_human=reset_in_human,
            reset_at=reset_at,
            reset_at_12h=reset_at_12h,
            last_seen_at=seen_at,
            binding=True,
            known=True,
        )
        out = {"burst_5h": burst, "weekly": weekly, "other": other}
        out["burst_5h"]["binding"] = False
        out["weekly"]["binding"] = False
        return out

    burst["binding"] = binding_key == "burst_5h"
    weekly["binding"] = binding_key == "weekly"
    return {"burst_5h": burst, "weekly": weekly}


def discover_surah_batches(surah: int) -> list[tuple[str, int, int]]:
    """Auto-discover the canonical contiguous chain of batch IDs and ayah ranges for a given surah."""
    prefix = f"s{surah:03d}_a"
    candidates: dict[str, tuple[int, int]] = {}
    for p in sorted(PROTO.glob(f"{prefix}*_input.json")):
        bid = p.name[: -len("_input.json")]
        m = re.match(rf"^s{surah:03d}_a(\d+)_(\d+)$", bid)
        if m:
            candidates[bid] = (int(m.group(1)), int(m.group(2)))
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            rng = d.get("ayahRange")
            if isinstance(rng, list) and len(rng) == 2:
                candidates[bid] = (int(rng[0]), int(rng[1]))
        except Exception:
            pass

    ordered = sorted(
        [(bid, a, b) for bid, (a, b) in candidates.items()],
        key=lambda x: (x[1], x[2]),
    )
    if not ordered:
        return ordered

    # Find the canonical contiguous chain (`next.a_start == cur.a_end + 1`) covering the maximum span
    by_start: dict[int, list[tuple[str, int, int]]] = {}
    for item in ordered:
        by_start.setdefault(item[1], []).append(item)

    memo: dict[tuple[str, int, int], list[tuple[str, int, int]]] = {}

    def longest_chain(node: tuple[str, int, int]) -> list[tuple[str, int, int]]:
        if node in memo:
            return memo[node]
        best_tail: list[tuple[str, int, int]] = []
        for nxt in by_start.get(node[2] + 1, []):
            cand_tail = longest_chain(nxt)
            if (cand_tail[-1][2], len(cand_tail)) > (
                (best_tail[-1][2], len(best_tail)) if best_tail else (-1, -1)
            ):
                best_tail = cand_tail
        res = [node] + best_tail
        memo[node] = res
        return res

    starts = by_start.get(1, ordered)
    best_chain: list[tuple[str, int, int]] = []
    for s in starts:
        ch = longest_chain(s)
        if (ch[-1][2] - ch[0][1], len(ch)) > (
            (best_chain[-1][2] - best_chain[0][1], len(best_chain)) if best_chain else (-1, -1)
        ):
            best_chain = ch
    return best_chain if len(best_chain) >= 2 else ordered


def estimate_turn_tokens_and_cost(
    prompt_chars: int,
    thought_chars: int,
    output_chars: int,
    prior_chat_chars: int = 0,
) -> dict[str, Any]:
    """Estimate token counts and equivalent API cost ($USD) for a single turn."""
    new_in_tok = int(round(prompt_chars / 2.8))
    ctx_in_tok = int(round(prior_chat_chars / 2.8))
    think_tok = int(round(thought_chars / 3.5))
    out_tok = int(round(output_chars / 2.8))
    total_tok = new_in_tok + ctx_in_tok + think_tok + out_tok

    cost_in = (new_in_tok / 1_000_000.0) * PRICE_NEW_INPUT_PER_M
    cost_ctx = (ctx_in_tok / 1_000_000.0) * PRICE_CACHED_INPUT_PER_M
    cost_out = ((think_tok + out_tok) / 1_000_000.0) * PRICE_OUTPUT_THINK_PER_M
    cost_total = round(cost_in + cost_ctx + cost_out, 4)

    return {
        "new_input_tokens": new_in_tok,
        "context_input_tokens": ctx_in_tok,
        "thinking_tokens": think_tok,
        "output_tokens": out_tok,
        "total_tokens": total_tok,
        "cost_usd": cost_total,
    }


def compute_batch_telemetry(bid: str, steps: list[dict[str, Any]], status_entry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compute quota credits used, token estimates, and cost for a batch from its turns."""
    st = status_entry or {}
    new_in_total = 0
    ctx_in_total = 0
    think_total = 0
    out_total = 0
    cost_total = 0.0
    credits_by_profile: dict[str, int] = defaultdict(int)

    # Track accumulated conversation history per cid for same_chat context token estimation
    cid_history_chars: dict[str, int] = defaultdict(int)
    last_cid: str | None = None

    enriched_steps: list[dict[str, Any]] = []
    for s in steps:
        p_chars = int(s.get("prompt_chars") or 0)
        th_chars = int(s.get("thoughts") or 0)
        o_chars = int(s.get("chars") or 0)
        mode = str(s.get("mode") or "fresh")
        cid = s.get("cid") or (last_cid if mode == "same_chat" else None)
        prof = str(s.get("profile") or "unknown")
        outcome = str(s.get("outcome") or "")

        prior_chars = cid_history_chars.get(str(cid), 0) if (mode == "same_chat" and cid) else 0
        est = estimate_turn_tokens_and_cost(p_chars, th_chars, o_chars, prior_chat_chars=prior_chars)

        # Did this turn consume a server generation / quota credit?
        # Any turn that reached StreamGenerate (ok, or failed after generating/downgrade) consumes 1 turn credit,
        # whereas local pre-send errors (TokenFactoryError before send) consume 0.
        turn_credits = 0
        if outcome == "ok" or outcome in ("HighDowngradeError", "GeminiReplyError", "VerifyReadbackError"):
            turn_credits = CREDITS_PER_ARGON_HIGH_TURN
        elif float(s.get("secs") or 0) > 35.0 and "TokenFactoryError" not in outcome:
            turn_credits = CREDITS_PER_ARGON_HIGH_TURN

        credits_by_profile[prof] += turn_credits
        new_in_total += est["new_input_tokens"]
        ctx_in_total += est["context_input_tokens"]
        think_total += est["thinking_tokens"]
        out_total += est["output_tokens"]
        cost_total += est["cost_usd"]

        if outcome == "ok" and cid:
            cid_history_chars[str(cid)] += p_chars + o_chars
            last_cid = str(cid)

        enriched_steps.append(
            {
                **s,
                "ts_12h": fmt_iso_to_12h(s.get("ts"), include_seconds=True),
                "quota_credits": turn_credits,
                "tokens": est["total_tokens"],
                "cost_usd": round(est["cost_usd"], 3),
            }
        )

    measured_q = st.get("quota_used")
    computed_q = sum(credits_by_profile.values())
    quota_used = int(measured_q) if (isinstance(measured_q, (int, float)) and measured_q > 0) else computed_q

    return {
        "quota_credits_used": quota_used,
        "quota_credits_by_profile": dict(credits_by_profile),
        "turns_total": len(steps),
        "turns_ok": sum(1 for s in steps if s.get("outcome") == "ok"),
        "turns_fail": sum(1 for s in steps if s.get("outcome") != "ok"),
        "new_input_tokens": new_in_total,
        "context_input_tokens": ctx_in_total,
        "thinking_tokens": think_total,
        "output_tokens": out_total,
        "total_tokens": new_in_total + ctx_in_total + think_total + out_total,
        "cost_usd": round(cost_total, 2),
        "enriched_steps": enriched_steps,
    }


def build_all_surahs_ledger(surahs: list[int] | None = None) -> dict[str, Any]:
    """Build and persist the telemetry/quota/token/cost ledger for Surahs in turns/status.

    Optional `surahs` limits which Surah numbers are rebuilt (used by the live runner
    after each batch finishes). When omitted, all known Surahs are included.
    """
    turns: list[dict[str, Any]] = []
    if TURNS_FILE.exists():
        for line in TURNS_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    turns.append(json.loads(line))
                except Exception:
                    pass

    done_events: dict[str, dict[str, Any]] = {}
    if EVENTS_FILE.exists():
        for line in EVENTS_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    ev = json.loads(line)
                    if ev.get("event") == "batch_done" and ev.get("batch"):
                        bid = str(ev["batch"])
                        if ev.get("ok") or bid not in done_events:
                            done_events[bid] = ev
                except Exception:
                    pass

    surahs_from_turns = {
        int(m.group(1))
        for t in turns
        if (m := re.match(r"^s(\d{3})_", str(t.get("batch") or "")))
    }
    surahs_from_status: set[int] = set()
    for st_file in SCRATCH.glob("surah*_parallel_status.json"):
        m = re.match(r"^surah(\d+)_parallel_status\.json$", st_file.name)
        if m:
            surahs_from_status.add(int(m.group(1)))
            continue
        try:
            doc = json.loads(st_file.read_text(encoding="utf-8-sig"))
            if isinstance(doc, dict) and doc.get("surah") is not None:
                surahs_from_status.add(int(doc["surah"]))
        except Exception:
            pass
    surahs_seen = sorted(surahs_from_turns | surahs_from_status | {6})
    filter_only = surahs is not None
    if filter_only:
        surahs_seen = sorted({int(s) for s in surahs})

    surah_ledgers: dict[str, Any] = {}
    for s_num in surahs_seen:
        batches_meta = discover_surah_batches(s_num)
        batch_ids = [b for b, _, _ in batches_meta]
        by_batch: dict[str, list[dict[str, Any]]] = {b: [] for b in batch_ids}
        for t in turns:
            b = str(t.get("batch") or "")
            if b.startswith(f"s{s_num:03d}_"):
                by_batch.setdefault(b, []).append(t)

        status_path = SCRATCH / f"surah{s_num}_parallel_status.json"
        status_doc = json.loads(status_path.read_text(encoding="utf-8-sig")) if status_path.exists() else {}
        if isinstance(status_doc, dict) and isinstance(status_doc.get("batches"), dict):
            status_data = status_doc["batches"]
        elif isinstance(status_doc, dict):
            # Legacy flat map (batch-id keys only) — ignore metadata keys.
            status_data = {
                k: v
                for k, v in status_doc.items()
                if isinstance(v, dict) and re.match(rf"^s{s_num:03d}_", k)
            }
        else:
            status_data = {}
        for bid in status_data:
            by_batch.setdefault(bid, [])

        batch_summaries: dict[str, Any] = {}
        account_groups: dict[str, dict[str, Any]] = {}
        tot_quota = 0
        tot_tokens = 0
        tot_new_in = 0
        tot_ctx_in = 0
        tot_think = 0
        tot_out = 0
        tot_cost = 0.0
        tot_stops = 0
        tot_demos = 0

        for bid in sorted(by_batch.keys()):
            st = status_data.get(bid, {}) if isinstance(status_data, dict) else {}
            if not isinstance(st, dict):
                st = {}
            ev = done_events.get(bid, {})
            steps = by_batch[bid]
            telem = compute_batch_telemetry(bid, steps, st)

            out_file = PROTO / f"{bid}_llm_output.json"
            ext_cnt = st.get("extractionsCount")
            dem_cnt = st.get("permissiveDemosCount")
            if out_file.exists() and (ext_cnt is None or dem_cnt is None):
                try:
                    od = json.loads(out_file.read_text(encoding="utf-8"))
                    exts = od.get("extractions", [])
                    ext_cnt = len(exts)
                    dem_cnt = sum(1 for x in exts if x.get("demosAndMeanings"))
                except Exception:
                    pass

            ok_steps = [s for s in steps if s.get("outcome") == "ok"]
            prof = (
                st.get("profile")
                or ev.get("profile")
                or (ok_steps[-1].get("profile") if ok_steps else (steps[-1].get("profile") if steps else "unassigned"))
            )
            total_s = st.get("total_s") if st.get("total_s") is not None else ev.get("total_s")
            step_a_s = st.get("step_a_s") if st.get("step_a_s") is not None else ev.get("step_a_s")
            step_b_s = st.get("step_b_s") if st.get("step_b_s") is not None else ev.get("step_b_s")
            wasted_s = st.get("wasted_s") if st.get("wasted_s") is not None else ev.get("wasted_s")

            b_summary = {
                "batch": bid,
                "profile": prof,
                "stage": "validated_ready" if out_file.exists() else (st.get("stage") or "pending"),
                "extractions": ext_cnt,
                "demos": dem_cnt,
                "total_s": total_s,
                "step_a_s": step_a_s,
                "step_b_s": step_b_s,
                "wasted_s": wasted_s,
                "updatedAt": st.get("updatedAt") or ev.get("ts"),
                "updatedAt_12h": fmt_iso_to_12h(st.get("updatedAt") or ev.get("ts")),
                **{k: v for k, v in telem.items() if k != "enriched_steps"},
            }
            batch_summaries[bid] = b_summary

            tot_quota += telem["quota_credits_used"]
            tot_tokens += telem["total_tokens"]
            tot_new_in += telem["new_input_tokens"]
            tot_ctx_in += telem["context_input_tokens"]
            tot_think += telem["thinking_tokens"]
            tot_out += telem["output_tokens"]
            tot_cost += telem["cost_usd"]
            tot_stops += int(ext_cnt or 0)
            tot_demos += int(dem_cnt or 0)

            grp = account_groups.setdefault(
                str(prof),
                {
                    "profile": str(prof),
                    "batches_count": 0,
                    "batches": [],
                    "extractions": 0,
                    "demos": 0,
                    "turns_ok": 0,
                    "turns_fail": 0,
                    "quota_credits_used": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "total_min": 0.0,
                },
            )
            grp["batches_count"] += 1
            grp["batches"].append(bid)
            grp["extractions"] += int(ext_cnt or 0)
            grp["demos"] += int(dem_cnt or 0)
            grp["turns_ok"] += telem["turns_ok"]
            grp["turns_fail"] += telem["turns_fail"]
            grp["quota_credits_used"] += telem["quota_credits_used"]
            grp["total_tokens"] += telem["total_tokens"]
            grp["cost_usd"] = round(grp["cost_usd"] + telem["cost_usd"], 2)
            if total_s is not None:
                grp["total_min"] = round(grp["total_min"] + float(total_s) / 60.0, 1)

        surah_ledgers[str(s_num)] = {
            "surah": s_num,
            "surah_name_ar": SURAH_NAMES_AR.get(s_num, f"سورة {s_num}"),
            "batches_total": len(batch_summaries),
            "batches_done": sum(1 for b in batch_summaries.values() if b["stage"] == "validated_ready"),
            "extractions_total": tot_stops,
            "demos_total": tot_demos,
            "quota_credits_used": tot_quota,
            "quota_burst_windows_equiv": round(tot_quota / float(BURST_POOL_LIMIT), 2),
            "quota_macro_pct_equiv": round(100.0 * tot_quota / float(MACRO_POOL_LIMIT), 2),
            "new_input_tokens": tot_new_in,
            "context_input_tokens": tot_ctx_in,
            "thinking_tokens": tot_think,
            "output_tokens": tot_out,
            "total_tokens": tot_tokens,
            "estimated_cost_usd": round(tot_cost, 2),
            "by_account": account_groups,
            "batches": batch_summaries,
        }

        if status_path.exists():
            try:
                st_doc = json.loads(status_path.read_text(encoding="utf-8"))
                st_batches = st_doc.get("batches", {}) if isinstance(st_doc, dict) else {}
                for bid, b_sum in batch_summaries.items():
                    if bid in st_batches and isinstance(st_batches[bid], dict):
                        st_batches[bid]["quota_credits_used"] = b_sum["quota_credits_used"]
                        st_batches[bid]["total_tokens"] = b_sum["total_tokens"]
                        st_batches[bid]["new_input_tokens"] = b_sum["new_input_tokens"]
                        st_batches[bid]["context_input_tokens"] = b_sum["context_input_tokens"]
                        st_batches[bid]["thinking_tokens"] = b_sum["thinking_tokens"]
                        st_batches[bid]["output_tokens"] = b_sum["output_tokens"]
                        st_batches[bid]["cost_usd"] = b_sum["cost_usd"]
                        st_batches[bid]["updatedAt_12h"] = b_sum["updatedAt_12h"]
                st_doc["surah_totals"] = {
                    "quota_credits_used": tot_quota,
                    "quota_burst_windows_equiv": round(tot_quota / float(BURST_POOL_LIMIT), 2),
                    "quota_macro_pct_equiv": round(100.0 * tot_quota / float(MACRO_POOL_LIMIT), 2),
                    "total_tokens": tot_tokens,
                    "estimated_cost_usd": round(tot_cost, 2),
                    "by_account": account_groups,
                }
                if "updatedAt" in st_doc:
                    st_doc["updatedAt_12h"] = fmt_iso_to_12h(st_doc.get("updatedAt"), include_date=True)
                status_path.write_text(json.dumps(st_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass

    now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
    merged_surahs = dict(surah_ledgers)
    if filter_only and LEDGER_FILE.exists():
        try:
            prev = json.loads(LEDGER_FILE.read_text(encoding="utf-8-sig"))
            prev_map = prev.get("surahs") if isinstance(prev, dict) else {}
            if isinstance(prev_map, dict):
                merged = dict(prev_map)
                merged.update(surah_ledgers)
                merged_surahs = merged
        except Exception:
            pass
    payload = {
        "recordedAt": now_iso,
        "recordedAt_12h": fmt_iso_to_12h(now_iso, include_date=True),
        "pricing_model": {
            "description": "Equivalent Frontier Reasoning API (Gemini Pro / Argon High / GPT-5.4 tier)",
            "new_input_per_1m_usd": PRICE_NEW_INPUT_PER_M,
            "cached_context_per_1m_usd": PRICE_CACHED_INPUT_PER_M,
            "output_and_thinking_per_1m_usd": PRICE_OUTPUT_THINK_PER_M,
            "credits_per_argon_high_turn": CREDITS_PER_ARGON_HIGH_TURN,
        },
        "surahs": merged_surahs,
    }
    LEDGER_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def compute_surah_turn_ledger(surah: int) -> dict[str, dict[str, Any]]:
    """Build/refresh the telemetry ledger and return the per-batch dict for `surah`."""
    payload = build_all_surahs_ledger(surahs=[surah])
    return ((payload.get("surahs") or {}).get(str(surah)) or {}).get("batches") or {}


if __name__ == "__main__":
    ledger = build_all_surahs_ledger()
    print(f"Recorded telemetry ledger at {ledger['recordedAt_12h']} -> {LEDGER_FILE}")
    for s_key, s_data in ledger["surahs"].items():
        print(
            f"\n=== Surah {s_key} ({s_data['surah_name_ar']}) ===\n"
            f"  Batches: {s_data['batches_done']}/{s_data['batches_total']} done | "
            f"Stops: {s_data['extractions_total']:,} | Demos: {s_data['demos_total']:,}\n"
            f"  Quota Used: {s_data['quota_credits_used']:,} credits "
            f"({s_data['quota_burst_windows_equiv']}x 2400 5h-reset windows / {s_data['quota_macro_pct_equiv']}% of 48,384 weekly pool)\n"
            f"  Estimated Tokens: {s_data['total_tokens']:,} total "
            f"(new_in={s_data['new_input_tokens']:,}, ctx_in={s_data['context_input_tokens']:,}, "
            f"think={s_data['thinking_tokens']:,}, out={s_data['output_tokens']:,})\n"
            f"  Estimated Equivalent API Cost: ${s_data['estimated_cost_usd']:.2f} USD"
        )
        for prof, grp in s_data["by_account"].items():
            print(
                f"    [{prof:13s}] {grp['batches_count']} batches {grp['batches']} | "
                f"quota={grp['quota_credits_used']:,} cr | tokens={grp['total_tokens']:,} | "
                f"cost=${grp['cost_usd']:.2f} | time={grp['total_min']}m"
            )
