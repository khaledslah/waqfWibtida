from __future__ import annotations

import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(r"d:\AI_Projects\waqfWibtida2")
PROTO = ROOT / "data" / "llm_prototype"
SCHEMA_PATH = ROOT / "schemas" / "app_feed.schema.json"
FEED_PATH = ROOT / "WaqfReader_Grok" / "assets" / "app_feed" / "surah_002.json"
BUILD_FEED_PATH = ROOT / "WaqfReader_Grok" / "build" / "flutter_assets" / "assets" / "app_feed" / "surah_002.json"
AGENT_MD = Path(
    r"C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\.agents\agents\waqf_llm_extractor\agent.md"
)
SCRATCH = Path(
    r"C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch"
)

if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import llm_waqf_extractor as lwe  # noqa: E402

VALID_SCHOLARS = {"السجاوندي", "الداني", "ابن الأنباري", "الأشموني", "النحاس"}
ALLOWED_DEMO_KEYS = {
    "verdict",
    "isQila",
    "attributedTo",
    "waqfSegmentWords",
    "ibtidaSegmentWords",
    "waqfDemo",
    "ibtidaDemo",
    "meaningAtWaqf",
    "meaningAtIbtida",
    "meaningIfConnected",
}
REQUIRED_DEMO_STR_KEYS = (
    "waqfDemo",
    "ibtidaDemo",
    "meaningAtWaqf",
    "meaningAtIbtida",
    "meaningIfConnected",
)


def strip_followup_and_fences(raw: str) -> str:
    txt = (raw or "").strip()
    # Remove trailing <FollowUp .../> tags if any
    txt_no_fu = re.sub(r"<FollowUp\b[^>]*/>\s*", "", txt).strip()
    # Check explicit ```json segments from last to first (handles stream-reopen
    # fence restarts where a truncated ```json prefix is followed by a restarted
    # ```json fence containing the full JSON payload).
    if "```json" in txt_no_fu:
        parts = txt_no_fu.split("```json")
        for seg in reversed(parts[1:]):
            candidate = seg.split("```", 1)[0].strip()
            if not candidate:
                continue
            try:
                json.loads(candidate)
                return candidate
            except Exception:
                continue
    fences = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", txt_no_fu)
    if fences:
        # Prefer the longest fence that successfully decodes as JSON
        best = None
        for blk in sorted(fences, key=len, reverse=True):
            try:
                json.loads(blk.strip())
                return blk.strip()
            except Exception:
                if best is None:
                    best = blk.strip()
        return best or fences[0].strip()
    return txt_no_fu


def extract_json_value(raw: str) -> Any:
    """Parse JSON robustly from model output (fences, prose, or trailing tags)."""
    cleaned = strip_followup_and_fences(raw)
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    decoder = json.JSONDecoder()
    best_top: tuple[int, int, Any] | None = None
    for text in (cleaned, raw or ""):
        idx = 0
        n = len(text)
        while idx < n:
            ch = text[idx]
            if ch in "{[":
                try:
                    val, end_idx = decoder.raw_decode(text, idx)
                    span_len = end_idx - idx
                    is_preferred = isinstance(val, list) or (
                        isinstance(val, dict) and "extractions" in val
                    )
                    rank = 1 if is_preferred else 0
                    cand_key = (rank, span_len)
                    if best_top is None or cand_key > (best_top[0], best_top[1]):
                        best_top = (rank, span_len, val)
                    idx = max(idx + 1, end_idx)
                    continue
                except Exception:
                    pass
            idx += 1
        if best_top is not None and best_top[0] == 1:
            return best_top[2]
    if best_top is not None:
        return best_top[2]
    raise ValueError("Could not extract valid JSON object/array from response")


def get_word_lookups(surahs: tuple[int, ...] = (2,)) -> tuple[dict[int, dict[tuple[int, int], dict[str, Any]]], dict[int, dict[int, int]]]:
    wl_cache: dict[int, dict[tuple[int, int], dict[str, Any]]] = {}
    mw_cache: dict[int, dict[int, int]] = {}
    for s in surahs:
        wl = lwe._load_surah_word_lookup(s)
        wl_cache[s] = wl
        mw: dict[int, int] = {}
        for ay_i, wi_i in wl:
            mw[ay_i] = max(mw.get(ay_i, 0), wi_i)
        mw_cache[s] = mw
    return wl_cache, mw_cache


def ensure_surah_loaded(
    s_num: int,
    wl_cache: dict[int, dict[tuple[int, int], dict[str, Any]]],
    mw_cache: dict[int, dict[int, int]],
) -> None:
    if s_num not in wl_cache:
        wl = lwe._load_surah_word_lookup(s_num)
        wl_cache[s_num] = wl
        mw: dict[int, int] = {}
        for ay_i, wi_i in wl:
            mw[ay_i] = max(mw.get(ay_i, 0), wi_i)
        mw_cache[s_num] = mw


def norm_verdict(v: str | None) -> str:
    if v == "مفهوم":
        return "صالح"
    return str(v or "").strip()


def validate_step_a(
    data: Any,
    surah: int,
    start_ayah: int,
    end_ayah: int,
    input_data: dict[str, Any],
    wl_cache: dict[int, dict[tuple[int, int], dict[str, Any]]],
    mw_cache: dict[int, dict[int, int]],
    strict_in_range: bool = True,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict) or not isinstance(data.get("extractions"), list):
        return ["Top-level response must be a JSON object with 'extractions' list"], warnings

    exts = data["extractions"]
    if not exts:
        return ["'extractions' array is empty"], warnings

    seen_keys: dict[tuple[int, int, int, str], int] = {}
    extracted_ayahs_in_range: set[int] = set()
    extracted_nahhas_ayahs: set[int] = set()

    for idx, e in enumerate(exts):
        if not isinstance(e, dict):
            errors.append(f"extractions[{idx}] is not an object")
            continue
        try:
            s_num = int(e.get("surah") or surah)
            ay = int(e["ayah"])
            wi = int(e["wordIndex"])
        except Exception:
            errors.append(f"extractions[{idx}] missing/invalid integer surah/ayah/wordIndex: {e!r}")
            continue

        sch = e.get("scholar")
        if sch not in VALID_SCHOLARS:
            errors.append(f"Invalid scholar {sch!r} at s{s_num}:{ay}:{wi}")
            continue

        ensure_surah_loaded(s_num, wl_cache, mw_cache)
        if (ay, wi) not in wl_cache[s_num]:
            errors.append(
                f"Invalid word coordinate ({s_num}, {ay}, {wi}) maxW={mw_cache[s_num].get(ay)} "
                f"scholar={sch} target={e.get('targetWord')!r}"
            )
            continue

        if s_num == surah and start_ayah <= ay <= end_ayah:
            extracted_ayahs_in_range.add(ay)
            if sch == "النحاس":
                extracted_nahhas_ayahs.add(ay)
        else:
            if strict_in_range:
                errors.append(
                    f"Out-of-range extraction ({s_num}, {ay}, {wi}) {sch}: keep extractions strictly inside "
                    f"ayahRange {start_ayah}..{end_ayah} (note extensions in boundaryFlags only)"
                )
            elif ay < start_ayah - 3 or ay > end_ayah + 3:
                warnings.append(f"Far out-of-range extraction ({s_num}, {ay}, {wi}) {sch}")

        k = (s_num, ay, wi, sch)
        seen_keys[k] = seen_keys.get(k, 0) + 1
        if seen_keys[k] > 1:
            errors.append(f"Duplicate key {k}")

        verdicts = e.get("verdicts")
        is_qila = e.get("isQila")
        if not isinstance(verdicts, list) or not verdicts:
            errors.append(f"Empty/non-list verdicts at {k}")
        else:
            for v in verdicts:
                vn = norm_verdict(v)
                if vn not in lwe.ALLOWED_VERDICTS:
                    errors.append(f"Invalid verdict {v!r} at {k}")
            if not isinstance(is_qila, list) or len(is_qila) != len(verdicts):
                errors.append(f"isQila length mismatch vs verdicts at {k}: verdicts={verdicts}, isQila={is_qila}")

        if sch == "السجاوندي" and e.get("sajawandiSymbol") == "ص" and "صالح" in (verdicts or []):
            errors.append(f"Sajawandi symbol 'ص' mapped to 'صالح' instead of 'حسن' at {k}")

        comment = (e.get("comment") or "").strip()
        if not comment:
            errors.append(f"Empty comment at {k}")
        elif re.match(r"^\s*\((?:لا يوقف|تام|كاف|حسن|صالح|جائز|لازم|قيل فيه وقف)\)", comment):
            errors.append(f"Comment starts with bracketed verdict at {k}: {comment[:60]!r}")

        if e.get("typoDetected") is not None and not isinstance(e.get("typoDetected"), dict):
            errors.append(f"typoDetected must be null or object at {k}")

    # Coverage sanity check against source Nahhas entries
    for ne in input_data.get("nahhasEntries", []):
        ay = ne.get("ayah")
        txt = (ne.get("text") or "").strip()
        if isinstance(ay, int) and start_ayah <= ay <= end_ayah and len(txt) > 15:
            if ay not in extracted_nahhas_ayahs:
                warnings.append(f"Ayah {ay} has Nahhas source text ({len(txt)} chars) but 0 Nahhas stops extracted")

    missing_ayahs = sorted(set(range(start_ayah, end_ayah + 1)) - extracted_ayahs_in_range)
    if missing_ayahs:
        warnings.append(f"In-range ayahs with 0 extractions: {missing_ayahs}")

    return errors, warnings


def validate_step_b(
    ext_data: dict[str, Any],
    raw_demos_list: Any,
    wl_cache: dict[int, dict[tuple[int, int], dict[str, Any]]],
    mw_cache: dict[int, dict[int, int]],
    default_surah: int = 2,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[tuple[int, int, int, str], list[dict[str, Any]]]]:
    """Return (missing_items, broken_items, valid_demo_map)."""
    if isinstance(raw_demos_list, dict) and isinstance(raw_demos_list.get("extractions"), list):
        raw_demos_list = raw_demos_list["extractions"]
    if not isinstance(raw_demos_list, list):
        raw_demos_list = []

    raw_map: dict[tuple[int, int, int, str], Any] = {}
    for d in raw_demos_list:
        if not isinstance(d, dict):
            continue
        try:
            k = (
                int(d.get("surah") or default_surah),
                int(d["ayah"]),
                int(d["wordIndex"]),
                str(d["scholar"]),
            )
        except Exception:
            continue
        raw_map[k] = d.get("demosAndMeanings")

    missing_items: list[dict[str, Any]] = []
    broken_items: list[dict[str, Any]] = []
    valid_demo_map: dict[tuple[int, int, int, str], list[dict[str, Any]]] = {}

    for e in ext_data.get("extractions", []):
        verdicts = e.get("verdicts") or []
        is_qila = e.get("isQila") or [False] * len(verdicts)
        non_la_pairs = [
            (norm_verdict(v), bool(is_qila[i]) if i < len(is_qila) else False)
            for i, v in enumerate(verdicts)
            if norm_verdict(v) != "لا يوقف"
        ]
        if not non_la_pairs:
            continue

        s_num = int(e.get("surah") or default_surah)
        ay = int(e["ayah"])
        wi = int(e["wordIndex"])
        sch = str(e["scholar"])
        k = (s_num, ay, wi, sch)
        dm = raw_map.get(k)

        req_desc = {
            "surah": s_num,
            "ayah": ay,
            "wordIndex": wi,
            "targetWord": e.get("targetWord"),
            "scholar": sch,
            "verdicts": e.get("verdicts"),
            "isQila": e.get("isQila"),
            "comment": e.get("comment"),
        }

        if not dm or not isinstance(dm, list):
            missing_items.append(req_desc)
            continue

        ensure_surah_loaded(s_num, wl_cache, mw_cache)
        mw = mw_cache[s_num].get(ay, 0)
        is_end = bool(wl_cache[s_num].get((ay, wi), {}).get("isVerseEnd"))
        reasons: list[str] = []

        exp_verdicts = [p[0] for p in non_la_pairs]
        got_verdicts = [norm_verdict(d.get("verdict")) if isinstance(d, dict) else None for d in dm]
        if got_verdicts != exp_verdicts:
            reasons.append(f"verdicts mismatch: expected {exp_verdicts}, got {got_verdicts}")

        cleaned_dm: list[dict[str, Any]] = []
        for idx_d, d in enumerate(dm):
            if not isinstance(d, dict):
                reasons.append(f"item[{idx_d}] is not object")
                continue
            extra_keys = set(d.keys()) - ALLOWED_DEMO_KEYS
            if extra_keys:
                reasons.append(f"item[{idx_d}] has unexpected keys {sorted(extra_keys)}")
            v_norm = norm_verdict(d.get("verdict"))
            if v_norm not in lwe.ALLOWED_VERDICTS or v_norm == "لا يوقف":
                reasons.append(f"item[{idx_d}] invalid verdict {d.get('verdict')!r}")
            if not isinstance(d.get("isQila"), bool):
                reasons.append(f"item[{idx_d}] isQila must be boolean")

            ws = d.get("waqfSegmentWords")
            ib = d.get("ibtidaSegmentWords")
            if (
                not isinstance(ws, list)
                or len(ws) != 2
                or not all(isinstance(n, int) for n in ws)
                or ws[0] < 1
                or ws[0] > ws[1]
                or ws[1] != wi
                or ws[1] > mw
            ):
                reasons.append(f"item[{idx_d}] bad waqfSegmentWords={ws!r} (expected [<= {wi}, {wi}], mw={mw})")

            if is_end:
                if ib is not None:
                    reasons.append(f"item[{idx_d}] verse-end word wi={wi} must have ibtidaSegmentWords=null, got {ib!r}")
            else:
                if (
                    not isinstance(ib, list)
                    or len(ib) != 2
                    or not all(isinstance(n, int) for n in ib)
                    or ib[0] != wi + 1
                    or ib[0] > ib[1]
                    or ib[1] > mw
                ):
                    reasons.append(f"item[{idx_d}] bad ibtidaSegmentWords={ib!r} (expected [{wi + 1}, <= {mw}], mw={mw})")

            for rk in REQUIRED_DEMO_STR_KEYS:
                val = d.get(rk)
                if not isinstance(val, str) or not val.strip():
                    reasons.append(f"item[{idx_d}] missing/empty {rk}")

            if not reasons:
                obj: dict[str, Any] = {
                    "verdict": v_norm,
                    "isQila": bool(d["isQila"]),
                }
                if isinstance(d.get("attributedTo"), str) and d["attributedTo"].strip():
                    obj["attributedTo"] = d["attributedTo"].strip()
                obj["waqfSegmentWords"] = ws
                obj["ibtidaSegmentWords"] = ib
                for rk in REQUIRED_DEMO_STR_KEYS:
                    obj[rk] = d[rk].strip()
                cleaned_dm.append(obj)

        if reasons:
            req_desc["reasons"] = reasons
            req_desc["previous"] = dm
            broken_items.append(req_desc)
        else:
            valid_demo_map[k] = cleaned_dm

    return missing_items, broken_items, valid_demo_map


def assemble_candidate_output(
    ext_data: dict[str, Any],
    demo_map: dict[tuple[int, int, int, str], list[dict[str, Any]]],
    default_surah: int = 2,
) -> dict[str, Any]:
    out = json.loads(json.dumps(ext_data, ensure_ascii=False))
    for e in out.get("extractions", []):
        non_la = [norm_verdict(v) for v in (e.get("verdicts") or []) if norm_verdict(v) != "لا يوقف"]
        if not non_la:
            e["demosAndMeanings"] = None
        else:
            k = (
                int(e.get("surah") or default_surah),
                int(e["ayah"]),
                int(e["wordIndex"]),
                str(e["scholar"]),
            )
            e["demosAndMeanings"] = demo_map[k]
    return out


def validate_candidate_file(
    batch_id: str,
    start_ayah: int,
    end_ayah: int,
    candidate_path: Path,
    apply_to_feed: bool = False,
    surah: int = 2,
) -> tuple[bool, str]:
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "llm_waqf_extractor.py"),
        "--surah",
        str(surah),
        "--start-ayah",
        str(start_ayah),
        "--end-ayah",
        str(end_ayah),
        "--validate",
        str(candidate_path),
    ]
    if apply_to_feed:
        cmd.append("--apply-to-feed")
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    combined_out = (res.stdout or "") + ("\nSTDERR:\n" + res.stderr if res.stderr else "")
    if res.returncode != 0 or "Validation errors: 0" not in (res.stdout or ""):
        return False, combined_out.strip()
    if apply_to_feed:
        feed_p = ROOT / "WaqfReader_Grok" / "assets" / "app_feed" / f"surah_{surah:03d}.json"
        bfeed_p = ROOT / "WaqfReader_Grok" / "build" / "flutter_assets" / "assets" / "app_feed" / f"surah_{surah:03d}.json"
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        feed = json.loads(feed_p.read_text(encoding="utf-8"))
        jsonschema.validate(instance=feed, schema=schema)
        if bfeed_p.exists():
            bfeed = json.loads(bfeed_p.read_text(encoding="utf-8"))
            jsonschema.validate(instance=bfeed, schema=schema)
    return True, combined_out.strip()
