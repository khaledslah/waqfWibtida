## 1. task-9936 & diag files
`python
# File: C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch\diagnose_monotonic_nahhas.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnose monotonic Al-Nahhas ayah anchors + comment-level page refinement."""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"d:\AI_Projects\waqfWibtida2\tools")
from upload_books_to_neon import RAW_SHAMELA_DIR, CATALOG_PATH, QAT_DIR

FEED_DIR = Path(r"d:\AI_Projects\waqfWibtida2\WaqfReader_Grok\assets\app_feed")

def norm_ar(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("ٱ", "ا").replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ى", "ي").replace("ة", "ه")
    s = re.sub(r"[\u064B-\u065F\u0670\u06D6-\u06ED\u0640\u0653-\u0655]", "", s)
    s = re.sub(r"[﴿﴾\(\)\[\]«»\.،,:؛\?\!\"'\-\/\\0-9\u0660-\u0669]", " ", s)
    return " ".join(s.split())

nh = json.loads((RAW_SHAMELA_DIR / "Al-Nahhas-Qatc-20966.json").read_text(encoding="utf-8"))
nh_pages = [(int(p["page"]), p.get("text") or "") for p in nh["pages"]]
nh_norm = {p: norm_ar(t) for p, t in nh_pages}
catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

name_to_num = {norm_ar(x["name"]): x["number"] for x in catalog["surahs"]}
alt_names = {
    "فاتحه الكتاب": 1, "سوره الشريعه": 45, "سوره سال": 70, "سوره القران": 50,
    "سوره سبحان": 17, "سوره بني اسرائيل": 17, "سوره الملائكه": 35, "سوره غافر": 40,
    "سوره الطول": 40, "سوره فصلت": 41, "سوره تنزيل": 32, "سوره حم السجده": 41,
    "سوره حم عسق": 42, "سوره والذاريات": 51, "سوره الذاريات": 51,
    "سوره المنافقين": 63, "سوره المرسلات": 77, "سوره والنازعات": 79,
    "سوره انفطرت": 82, "سوره والفجر": 89, "سوره والشمس": 91, "سوره والليل": 92,
    "سوره والضحي": 93, "سوره الم نشرح": 94, "سوره والتين": 95,
    "سوره والعاديات": 100, "سوره والعصر": 103, "سوره الدين": 107,
    "سوره تبت": 111, "سوره الاخلاص": 112, "سوره التوحيد": 112,
    "سوره الفلق": 113, "سوره الناس": 114, "سوره ام القران": 1,
}

surah_start: dict[int, int] = {1: 28}
last_surah = 1
for pnum, raw_txt in nh_pages:
    if pnum < 28:
        continue
    for m in re.finditer(r"<span[^>]*>([^<]+)</span>", raw_txt):
        raw_t = re.sub(r"[^\u0621-\u064A\s]", "", norm_ar(m.group(1))).strip()
        s_candidate = name_to_num.get(raw_t) or alt_names.get(raw_t)
        if not s_candidate and "محمد" in raw_t: s_candidate = 47
        elif not s_candidate and "نوح" in raw_t: s_candidate = 71
        elif not s_candidate and "الرحمن" in raw_t: s_candidate = 55
        elif not s_candidate and "انفطرت" in raw_t: s_candidate = 82
        elif not s_candidate and "القلم" in raw_t: s_candidate = 68 if last_surah < 68 else 96
        if s_candidate and s_candidate >= last_surah and s_candidate not in surah_start:
            surah_start[s_candidate] = pnum
            last_surah = s_candidate

# Fill any remaining missing surah_start monotonically from next found header - 1 / prev found header
for s in range(1, 115):
    if s not in surah_start:
        prev_p = max([surah_start[x] for x in range(1, s) if x in surah_start], default=28)
        surah_start[s] = prev_p

print("Header-based missing count check - surah_start for 40,42,51,63,79,112..114:",
      {s: surah_start[s] for s in [40, 42, 51, 63, 79, 96, 111, 112, 113, 114]})

# Compute strict monotonic anchors for all 2,837 entries in QAT_DIR
mono_anchors: dict[tuple[int, int], int] = {}
non_mono_fixes = []
surah_bounds: dict[int, tuple[int, int]] = {}

qat_files = sorted(QAT_DIR.glob("surah_*.json"))
for qf in qat_files:
    qd = json.loads(qf.read_text(encoding="utf-8"))
    s_num = int(qd["surah"])
    win_start = surah_start[s_num]
    win_end = 829
    for nxt in range(s_num + 1, 115):
        if nxt in surah_start and surah_start[nxt] > win_start:
            win_end = surah_start[nxt]
            break
    surah_bounds[s_num] = (win_start, win_end)

    last_p = win_start
    entries = sorted(qd.get("entries", []), key=lambda x: x["ayah"])
    # Search ONLY monotonically from last_p .. win_end! (never backwards before last_p)
    # Wait: if an entry jumps forward a lot (e.g. > 5 pages for a single ayah on a short surah, or repeats later like 26:9), check uniqueness / verify next entries!
    raw_matches = []
    for ent in entries:
        ay = int(ent["ayah"])
        words = norm_ar(ent["text"]).split()
        hits = []
        for nlen in [8, 5, 3]:
            if len(words) >= nlen:
                needle = " ".join(words[:nlen])
                hits = [p for p in range(win_start, win_end + 1) if needle in nh_norm.get(p, "")]
                if hits:
                    break
        if not hits and len(words) >= 8:
            needle = " ".join(words[3:7])
            hits = [p for p in range(win_start, win_end + 1) if needle in nh_norm.get(p, "")]
        raw_matches.append((ay, hits, ent["text"]))

    # Also build combined page string (p + p+1) for boundary-crossing phrases if hits was empty!
    # Monotonic DP / constrained progression:
    for idx, (ay, hits, txt) in enumerate(raw_matches):
        # Upper bound from earliest reliable hit >= last_p among subsequent entries? No, simpler: take smallest hit >= last_p!
        valid = [p for p in hits if p >= last_p]
        if valid:
            chosen = valid[0]
            # Sanity check if chosen jumps > 3 pages while a subsequent entry hits < chosen!
            later_mins = [
                min([p for p in h2 if p >= last_p], default=9999)
                for _, h2, _ in raw_matches[idx + 1 : idx + 6]
                if h2
            ]
            if later_mins and chosen > min(later_mins):
                # Re-try checking page-boundary concat pnum + pnum+1 in [last_p, min(later_mins)]
                words = norm_ar(txt).split()
                hi = min(later_mins)
                found_bound = None
                for nlen in [6, 4]:
                    if len(words) >= nlen:
                        needle = " ".join(words[:nlen])
                        for pnum in range(last_p, hi + 1):
                            comb = nh_norm.get(pnum, "") + " " + nh_norm.get(pnum + 1, "")
                            if needle in comb:
                                found_bound = pnum
                                break
                    if found_bound is not None:
                        break
                chosen = found_bound if found_bound is not None else last_p
            last_p = chosen
            p_final = chosen
        else:
            # Try page-boundary cross p + p+1 from last_p .. win_end
            words = norm_ar(txt).split()
            found_bound = None
            for nlen in [6, 4]:
                if len(words) >= nlen:
                    needle = " ".join(words[:nlen])
                    for pnum in range(last_p, win_end + 1):
                        comb = nh_norm.get(pnum, "") + " " + nh_norm.get(pnum + 1, "")
                        if needle in comb:
                            found_bound = pnum
                            break
                if found_bound is not None:
                    break
            p_final = found_bound if found_bound is not None else last_p
            last_p = p_final
        mono_anchors[(s_num, ay)] = p_final

# Verify strict global monotonicity
prev = (0, 0, 0)
nm = 0
for (s, a), p in sorted(mono_anchors.items()):
    if p < prev[2]:
        nm += 1
        print("STILL NON-MONO:", prev, "->", (s, a, p))
    prev = (s, a, p)
print(f"Monotonicity check across {len(mono_anchors)} anchors: {nm} violations!")
for s, a in [(1, 1), (2, 1), (2, 85), (2, 86), (2, 87), (12, 66), (12, 76), (26, 8), (26, 9), (26, 10), (41, 23), (41, 28), (42, 7), (42, 8), (42, 10)]:
    if (s, a) in mono_anchors:
        print(f"  anchor({s}, {a}) = p.{mono_anchors[(s, a)]}")

# Now test comment-level exact matching WITHIN [anc_p .. next_anc_p] for all 6,744 opinions
ayah_re_single = re.compile(r"^\s*آية\s*(\d+)\s*$")
surah_anc_list: dict[int, list[tuple[int, int]]] = {}
for (s, a), p in sorted(mono_anchors.items()):
    surah_anc_list.setdefault(s, []).append((a, p))

same_as_anc = 0
refined_forward = 0
kept_anc_no_comment = 0
kept_anc_not_found_in_win = 0
diff_examples = []
not_found_examples = []

for s in range(1, 115):
    d = json.loads((FEED_DIR / f"surah_{s:03d}.json").read_text(encoding="utf-8"))
    s_list = surah_anc_list.get(s, [])
    w_start, w_end = surah_bounds.get(s, (28, 829))
    for st in d["stops"]:
        for op in st["opinions"]:
            if "نحاس" not in (op.get("scholar") or "") and "القطع والائتناف" not in (op.get("book") or ""):
                continue
            pg = op.get("page") or ""
            m = ayah_re_single.match(pg)
            if not m:
                continue
            ay = int(m.group(1))
            anc_p = mono_anchors[(s, ay)]
            # Upper page bound: next ayah's anchor page (or w_end if last ayah of surah)
            hi_p = w_end
            for aa, ap in s_list:
                if aa > ay:
                    hi_p = max(anc_p, ap)
                    break
            comment = (op.get("comment") or "").strip()
            if not comment:
                kept_anc_no_comment += 1
                continue
            words = norm_ar(comment).split()
            matched_p = None
            for nlen in [8, 6, 4]:
                if len(words) >= nlen:
                    needle = " ".join(words[:nlen])
                    for pnum in range(anc_p, hi_p + 1):
                        if needle in nh_norm.get(pnum, ""):
                            matched_p = pnum
                            break
                if matched_p is not None:
                    break
            if matched_p is None and len(words) >= 6:
                needle = " ".join(words[-5:])
                for pnum in range(anc_p, hi_p + 1):
                    if needle in nh_norm.get(pnum, ""):
                        matched_p = pnum
                        break
            if matched_p is None:
                kept_anc_not_found_in_win += 1
                if len(not_found_examples) < 15:
                    not_found_examples.append((st["id"], ay, anc_p, hi_p, comment[:60]))
            elif matched_p == anc_p:
                same_as_anc += 1
            else:
                refined_forward += 1
                if len(diff_examples) < 20:
                    diff_examples.append((st["id"], ay, anc_p, matched_p, hi_p, comment[:60]))

print(f"\nComment resolution within [anc_p .. next_anc_p]:")
print(f"  same_as_anc={same_as_anc}")
print(f"  refined_forward={refined_forward}")
print(f"  kept_anc_no_comment={kept_anc_no_comment}")
print(f"  kept_anc_not_found_in_win={kept_anc_not_found_in_win}")
print("Sample refined_forward:")
for x in diff_examples:
    print(" ", x)
print("Sample kept_anc_not_found_in_win:")
for x in not_found_examples:
    print(" ", x)


# File: C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch\diag_argon_levels.py
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from gemini_web_mcp_cli.core.client import GeminiClient
from gemini_web_mcp_cli.services.chat import ChatService
from gemini_web_mcp_cli.services.limits import LimitsService

SCRATCH = Path(
    r"C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch"
)


async def check_qoun_chat_and_test() -> None:
    client = GeminiClient(profile_name="qoun", timeout=300.0)
    await client.init()
    try:
        # 1. Check if c_1ea2e77b2066f070 saved any answer via hNvQHb
        try:
            payload = json.dumps(["c_1ea2e77b2066f070", 10, None, 1, [1], [4], None, 1])
            res = await client.execute_rpc_with_browser_cookies("hNvQHb", payload=payload)
            raw_len = len(str(res[0].data)) if res else 0
            print(f"[qoun read c_1ea2e77b2066f070] len={raw_len} preview={str(res[0].data)[:300] if res else None}")
        except Exception as exc:
            print(f"[qoun read c_1ea2e77b2066f070] err={exc}")

        # 2. Test Batch 7 Part 3 with gemini-4-argon thinking_level="medium"
        prompt = (SCRATCH / "s002_a139_152_demos_prompt_part3_clean.txt").read_text(encoding="utf-8")
        chat = ChatService(client)
        t0 = time.monotonic()
        try:
            resp = await chat.send(prompt, model="gemini-4-argon", thinking_level="medium")
            dt = time.monotonic() - t0
            print(
                f"[qoun argon medium B7p3] OK in {dt:.1f}s chars={len(resp.text or '')} "
                f"thoughts={len(resp.thoughts or '')} hash={resp.server_model_hash} cid={resp.metadata.cid if resp.metadata else None}"
            )
            (SCRATCH / "s002_a139_152_demos_part3_raw_medium.txt").write_text(resp.text or "", encoding="utf-8")
        except Exception as exc:
            print(f"[qoun argon medium B7p3] ERR after {time.monotonic() - t0:.1f}s: {type(exc).__name__}: {exc}")
    finally:
        await client.close()


async def check_niyyah() -> None:
    client = GeminiClient(profile_name="niyyah", timeout=300.0)
    await client.init()
    try:
        ls = LimitsService(client)
        lim = await ls.get_limits()
        pro = [(q.name, q.used, q.remaining) for q in lim if "Pro" in q.name or "Thinking" in q.name]
        print(f"[niyyah limits] count={len(lim)} pro={pro}")

        chat = ChatService(client)
        for lvl in ("medium", "high"):
            t0 = time.monotonic()
            try:
                resp = await chat.send("Reply strictly with PONG.", model="gemini-4-argon", thinking_level=lvl)
                dt = time.monotonic() - t0
                print(
                    f"[niyyah argon {lvl} PONG] OK in {dt:.1f}s reply={resp.text!r} "
                    f"thoughts={len(resp.thoughts or '')} hash={resp.server_model_hash} cid={resp.metadata.cid if resp.metadata else None}"
                )
            except Exception as exc:
                print(f"[niyyah argon {lvl} PONG] ERR after {time.monotonic() - t0:.1f}s: {type(exc).__name__}: {exc}")
            chat.reset()
    finally:
        await client.close()


async def main() -> None:
    await asyncio.gather(check_qoun_chat_and_test(), check_niyyah())


if __name__ == "__main__":
    asyncio.run(main())


# File: C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch\diag_high_live.py
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

sys.stdout.reconfigure(encoding="utf-8")

SCRATCH = Path(
    r"C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch"
)
if str(SCRATCH) not in sys.path:
    sys.path.insert(0, str(SCRATCH))

import waqf_batch_utils as u  # noqa: E402
from gemini_web_mcp_cli.core.cdp import navigate_to_url, run_js  # noqa: E402
from gemini_web_mcp_cli.core.client import GeminiClient  # noqa: E402
from gemini_web_mcp_cli.core.constants import get_model  # noqa: E402
from gemini_web_mcp_cli.core.locks import profile_lock  # noqa: E402
from gemini_web_mcp_cli.core.token_factory import (  # noqa: E402
    CLICK_SEND_JS,
    TYPE_PROMPT_JS,
    TokenFactory,
)
from gemini_web_mcp_cli.core.webchannel import (  # noqa: E402
    MODEL_BIN_HEADER,
    _pb_fields,
    bodies_from_text,
    decode_forward_body,
    find_setup_message,
)
from gemini_web_mcp_cli.services.chat import ChatService  # noqa: E402


PASSIVE_HOOK_JS = """
(() => {
    window.__psLog = [];
    const origOpen = XMLHttpRequest.prototype.open;
    const origSend = XMLHttpRequest.prototype.send;
    const origSetHeader = XMLHttpRequest.prototype.setRequestHeader;
    XMLHttpRequest.prototype.open = function(m, u, ...r) {
        this.__u = String(u); this.__m = m; this.__h = {}; this.__t0 = Date.now();
        return origOpen.call(this, m, u, ...r);
    };
    XMLHttpRequest.prototype.setRequestHeader = function(n, v) {
        if (this.__h) this.__h[n] = v;
        return origSetHeader.call(this, n, v);
    };
    XMLHttpRequest.prototype.send = function(body) {
        const u = this.__u || '';
        if (u.includes('processSession') || u.includes('StreamGenerate')) {
            const rec = {
                t: Date.now(),
                kind: 'send',
                method: this.__m,
                url: u.slice(0, 600),
                headers: this.__h,
                bodyLen: typeof body === 'string' ? body.length : -1,
                bodySample: typeof body === 'string' ? body.slice(0, 400) : String(body),
                fullQuery: u.includes('?') ? u.split('?')[1] : '',
            };
            window.__psLog.push(rec);
            this.addEventListener('readystatechange', () => {
                if (this.readyState === 3 || this.readyState === 4) {
                    const txt = typeof this.responseText === 'string' ? this.responseText : '';
                    window.__psLog.push({
                        t: Date.now(),
                        kind: 'resp_state_' + this.readyState,
                        status: this.status,
                        method: this.__m,
                        urlHead: u.slice(0, 120),
                        len: txt.length,
                        tail: txt.slice(-400),
                    });
                }
            });
        }
        return origSend.call(this, body);
    };
})()
"""


def test_niyyah_native_chrome() -> None:
    prof = "niyyah"
    c_tmp = GeminiClient(profile_name=prof)
    chrome_path = c_tmp.auth_manager.load().chrome_profile_path
    tf = TokenFactory(chrome_profile_path=chrome_path, profile_name=prof)
    t0 = time.monotonic()
    with profile_lock(prof):
        tf._ensure_ready_locked()
        ws = tf._ws_url
        navigate_to_url(ws, "https://gemini.google.com/app")
        tf._wait_for_input(timeout=20)
        m = get_model("gemini-4-argon").with_thinking_level("high")
        picker_ok = tf._set_model_picker(m)
        tf._set_composer_mode(False)
        lbl = run_js(ws, "document.querySelector('[data-test-id=\"bard-mode-menu-button\"]')?.innerText")
        print(f"[native niyyah] picker_ok={picker_ok} lbl={lbl!r}", flush=True)

        run_js(ws, PASSIVE_HOOK_JS)
        run_js(ws, TYPE_PROMPT_JS.format(prompt="Reply strictly with PONG."))
        time.sleep(0.4)
        send_t0 = time.monotonic()
        run_js(ws, CLICK_SEND_JS)

        last_cnt = 0
        answer_seen = None
        for _ in range(110):  # up to ~220s
            time.sleep(2.0)
            logs = run_js(ws, "window.__psLog") or []
            if len(logs) > last_cnt:
                for item in logs[last_cnt:]:
                    dt = (item["t"] / 1000.0)
                    print(
                        f"[native niyyah +{time.monotonic()-send_t0:.1f}s] {item.get('kind')} {item.get('method','')} "
                        f"status={item.get('status')} bodyLen={item.get('bodyLen')} len={item.get('len')}",
                        flush=True,
                    )
                    if item.get("kind") == "send" and item.get("bodyLen", 0) > 10:
                        print(f"   headers={item.get('headers')}", flush=True)
                        print(f"   bodySample={item.get('bodySample')[:250]!r}", flush=True)
                    elif item.get("tail"):
                        print(f"   tail={item.get('tail')[-250:]!r}", flush=True)
                last_cnt = len(logs)

            dom = run_js(
                ws,
                """
                (() => {
                    const md = document.querySelectorAll('message-content, model-response');
                    const last = md.length ? (md[md.length - 1].innerText || '').trim() : '';
                    const stop = !!document.querySelector('button[aria-label*="Stop"], button[aria-label*="stop"]');
                    return {n: md.length, last: last.slice(0, 300), stop, url: location.href};
                })()
                """,
            )
            if dom and dom.get("last") and not dom.get("stop") and "PONG" in dom["last"]:
                answer_seen = dom
                print(
                    f"[native niyyah DONE in {time.monotonic()-send_t0:.1f}s] dom={dom}",
                    flush=True,
                )
                break
        if not answer_seen:
            dom = run_js(
                ws,
                "({n: document.querySelectorAll('model-response').length, txt: (document.body.innerText||'').slice(-400), url: location.href})",
            )
            print(f"[native niyyah TIMEOUT after {time.monotonic()-t0:.1f}s] dom={dom}", flush=True)
        navigate_to_url(ws, "https://gemini.google.com/app")
    tf.shutdown()


async def test_default_b7_part3_and_inspect() -> None:
    prof = "default"
    prompt_path = SCRATCH / "s002_a139_152_demos_prompt_part3_clean.txt"
    prompt = prompt_path.read_text(encoding="utf-8")
    client = GeminiClient(profile_name=prof, timeout=240.0)
    await client.init()
    try:
        chat = ChatService(client)
        t0 = time.monotonic()
        resp = await chat.send(prompt, model="gemini-4-argon", thinking_level="high")
        dt = time.monotonic() - t0
        print(
            f"[{prof} B7p3 high] OK in {dt:.1f}s chars={len(resp.text or '')} "
            f"thoughts={len(resp.thoughts or '')} model_hash={resp.server_model_hash} "
            f"label={resp.server_model_label} cid={resp.metadata.cid if resp.metadata else None}",
            flush=True,
        )
        raw_path = SCRATCH / "s002_a139_152_demos_part3_raw_high.txt"
        raw_path.write_text(resp.text or "", encoding="utf-8")
        # Quick inspect if valid
        val = u.extract_json_value(resp.text or "")
        ext_data = json.loads((SCRATCH / "s002_a139_152_extract_only.json").read_text(encoding="utf-8"))
        rec_data = json.loads((SCRATCH / "s002_a139_152_recovered_combined.json").read_text(encoding="utf-8"))
        wl_cache, mw_cache = u.get_word_lookups((2,))
        combined = list(rec_data) + (list(val) if isinstance(val, list) else [])
        miss, brok, valid_map = u.validate_step_b(ext_data, combined, wl_cache, mw_cache)
        print(
            f"[{prof} B7p3 validate] valid={len(valid_map)} missing={len(miss)} broken={len(brok)}",
            flush=True,
        )
        for b in brok:
            print(f"  broken ({b['ayah']}:{b['wordIndex']} {b['scholar']}): {b['reasons']}", flush=True)
    except Exception as exc:
        print(f"[{prof} B7p3 high] ERR: {type(exc).__name__}: {exc}", flush=True)
    finally:
        await client.close()


async def main() -> None:
    loop = asyncio.get_running_loop()
    native_fut = loop.run_in_executor(None, test_niyyah_native_chrome)
    await asyncio.gather(native_fut, test_default_b7_part3_and_inspect())


if __name__ == "__main__":
    asyncio.run(main())


# File: C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch\diag_high_pb.py
from __future__ import annotations

import base64
import json
import sys
import time
from urllib.parse import parse_qsl, urlsplit

sys.stdout.reconfigure(encoding="utf-8")

from gemini_web_mcp_cli.core.cdp import get_gemini_page_ws_url, navigate_to_url, run_js
from gemini_web_mcp_cli.core.chrome_manager import check_daemon_health
from gemini_web_mcp_cli.core.token_factory import CLICK_SEND_JS, TYPE_PROMPT_JS, XHR_INTERCEPTOR_JS
from gemini_web_mcp_cli.core.webchannel import MODEL_BIN_HEADER, _pb_fields, decode_forward_body, find_setup_message, setup_inner

info, _ = check_daemon_health("smallbusiness")
ws = get_gemini_page_ws_url(info.port)
navigate_to_url(ws, "https://gemini.google.com/app")
time.sleep(2)

for wanted in ("Medium", "High"):
    res = run_js(
        ws,
        f"""
        (() => {{
            document.body.click();
            const host = document.querySelector('[data-test-id="bard-mode-menu-button"]');
            const btn = host ? (host.tagName === 'BUTTON' ? host : (host.querySelector('button') || host)) : null;
            if (!btn) return 'no_btn';
            btn.click();
            return new Promise(resolve => setTimeout(() => {{
                const argon = document.querySelector('[data-test-id="bard-mode-option-argon"]');
                if (argon && !argon.className.includes('selected')) {{ argon.click(); btn.click(); }}
                setTimeout(() => {{
                    const row = Array.from(document.querySelectorAll('[role="menuitem"]')).find(e => e.getAttribute('value') === 'thinking_level');
                    if (!row) {{ resolve('no_thinking_row'); return; }}
                    if (row.getAttribute('aria-expanded') !== 'true') row.click();
                    setTimeout(() => {{
                        const items = Array.from(document.querySelectorAll('[role="menuitem"], [role="menuitemradio"]'));
                        const target = items.find(el => (el.innerText || '').trim().startsWith('{wanted}') && el.getAttribute('value') !== 'thinking_level');
                        if (target) target.click();
                        document.body.click();
                        resolve({{wanted: '{wanted}', clicked: !!target, labelText: (btn.innerText || '').trim()}});
                    }}, 400);
                }}, 400);
            }}, 400));
        }})()
        """,
    )
    print(f"UI set {wanted}:", res, flush=True)
    time.sleep(0.5)
    run_js(ws, XHR_INTERCEPTOR_JS)
    run_js(ws, TYPE_PROMPT_JS.format(prompt="Say OK"))
    time.sleep(0.3)
    run_js(ws, CLICK_SEND_JS)
    cap = None
    for _ in range(15):
        time.sleep(0.5)
        cap = run_js(ws, "window.__cap")
        if cap:
            break
    if not cap:
        print(f"Capture failed for {wanted}", flush=True)
        continue
    url = cap.get("url", "")
    for k, v in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        if k == "$httpHeaders":
            for line in v.split("\r\n"):
                name, _, val = line.partition(":")
                if name.strip().lower() == MODEL_BIN_HEADER:
                    raw = base64.b64decode(val.strip() + "=" * (-len(val.strip()) % 4))
                    fields = _pb_fields(raw)
                    dec = []
                    for f, w, enc in fields:
                        if w == 2:
                            dec.append((f, w, enc[1:].decode(errors="replace")))
                        else:
                            dec.append((f, w, int.from_bytes(enc, "big") if len(enc) == 1 else list(enc)))
                    print(f"[{wanted}] pb fields:", dec, flush=True)
    msgs = decode_forward_body(cap["body"])
    setup = find_setup_message(msgs)
    inner = setup_inner(setup) if setup else None
    print(f"[{wanted}] setup[0][0]:", setup[0][0] if setup else None, flush=True)
    print(f"[{wanted}] inner[78:85]:", inner[78:85] if inner and len(inner) > 78 else None, flush=True)
    navigate_to_url(ws, "https://gemini.google.com/app")
    time.sleep(2)


# File: C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch\diag_parallel_all5.py
import asyncio
import time
from gemini_web_mcp_cli.core.client import GeminiClient
from gemini_web_mcp_cli.core.keepalive import check_profile, refresh_profile
from gemini_web_mcp_cli.core.profiles import ProfileManager
from gemini_web_mcp_cli.services.chat import ChatService
from gemini_web_mcp_cli.services.limits import LimitsService

PROFILES = ["default", "smallbusiness", "abod", "qoun", "niyyah"]


async def test_one(name: str):
    t0 = time.monotonic()
    client = GeminiClient(profile_name=name, timeout=180.0)
    try:
        await client.init()
        lim_svc = LimitsService(client)
        limits = await lim_svc.get_limits()
        pro = [l for l in limits if "Pro Prompts" in l.name or "Thinking" in l.name]

        svc = ChatService(client)
        t1 = time.monotonic()
        r1 = await svc.send(
            "Reply with PONG and nothing else.",
            model="gemini-4-argon",
            thinking_level="high",
        )
        d1 = time.monotonic() - t1
        cid = r1.metadata.cid if r1.metadata else None

        t2 = time.monotonic()
        r2 = await svc.send(
            "Reply with OK2 and nothing else.",
            model="gemini-4-argon",
            thinking_level="high",
        )
        d2 = time.monotonic() - t2
        same_cid = (r2.metadata.cid == cid) if (r2.metadata and cid) else False
        return (
            name,
            "OK",
            f"limits={len(limits)} pro={[(p.name, p.used, p.remaining) for p in pro]} | "
            f"t1={d1:.1f}s reply1={r1.text!r} cid={cid} hash1={r1.server_model_hash} label1={r1.server_model_label!r} | "
            f"t2={d2:.1f}s reply2={r2.text!r} same_cid={same_cid} hash2={r2.server_model_hash} label2={r2.server_model_label!r}",
        )
    except Exception as e:
        return (name, "ERR", f"{type(e).__name__}: {e} (after {time.monotonic() - t0:.1f}s)")
    finally:
        await client.close()


async def main():
    pm = ProfileManager()
    print("=== Keepalive refresh check across all 5 ===")
    for name in PROFILES:
        h = refresh_profile(pm, name, recover=False)
        print(f"  {name}: status={h.status} email={h.email} method={h.method} detail={h.detail}")

    print("\n=== Parallel Limits + 2-turn Argon High test across all 5 ===")
    results = await asyncio.gather(*(test_one(n) for n in PROFILES))
    for name, st, info in results:
        print(f"[{name}] {st}: {info}")


if __name__ == "__main__":
    asyncio.run(main())


# File: C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch\diag_picker_menu.py
import time
from gemini_web_mcp_cli.core.cdp import get_gemini_page_ws_url, run_js
from gemini_web_mcp_cli.core.chrome_manager import check_daemon_health

JS_OPEN_AND_INSPECT = """
(() => {
    document.body.click();
    const host = document.querySelector('[data-test-id="bard-mode-menu-button"]')
        || Array.from(document.querySelectorAll('button')).find(b => {
            const a = b.getAttribute('aria-label') || '';
            return a.includes('Open mode picker') || a.includes('اختيار الوضع');
        });
    if (!host) return {err: 'no_button'};
    const btn = host.tagName === 'BUTTON' ? host : (host.querySelector('button') || host);
    btn.click();
    return new Promise(resolve => setTimeout(() => {
        const opts = Array.from(document.querySelectorAll('[data-test-id^="bard-mode-option"], [role="menuitem"], [role="menuitemradio"]')).map(el => ({
            tid: el.getAttribute('data-test-id') || '',
            role: el.getAttribute('role') || '',
            val: el.getAttribute('value') || '',
            text: (el.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 80),
            cls: (el.className || '').slice(0, 60),
        }));
        document.body.click();
        resolve({btnTag: btn.tagName, btnAria: btn.getAttribute('aria-label'), opts});
    }, 800));
})()
"""

for name in ["default", "smallbusiness", "abod", "qoun", "niyyah"]:
    info, _ = check_daemon_health(name)
    ws = get_gemini_page_ws_url(info.port)
    res = run_js(ws, JS_OPEN_AND_INSPECT)
    print(f"=== {name} (port {info.port}) ===")
    print(" ", res)


# File: C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch\diag_profiles.py
import asyncio
import json
from pathlib import Path
from gemini_web_mcp_cli.core.profiles import ProfileManager
from gemini_web_mcp_cli.core.cdp import (
    get_gemini_page_ws_url,
    get_page_cookies,
    run_js,
    _filter_gemini_cookies,
)
from gemini_web_mcp_cli.core.keepalive import _http_signed_in_email
from gemini_web_mcp_cli.core.chrome_manager import check_daemon_health
from gemini_web_mcp_cli.core.client import GeminiClient
from gemini_web_mcp_cli.services.chat import ChatService
from gemini_web_mcp_cli.services.limits import LimitsService

PROFILES = ["default", "smallbusiness", "abod", "qoun", "niyyah"]


def inspect_metadata():
    pm = ProfileManager()
    for name in PROFILES:
        auth = pm.load_auth(name)
        info, dstatus = check_daemon_health(name)
        port = info.port if info else None
        ws = get_gemini_page_ws_url(port) if port else None
        url = run_js(ws, "window.location.href") if ws else ""
        chrome_email = run_js(ws, "window.WIZ_global_data?.oPEP7c || ''") if ws else ""
        has_sn = bool(run_js(ws, "window.WIZ_global_data?.SNlM0e || ''")) if ws else False
        raw = get_page_cookies(ws) if ws else []
        filt = _filter_gemini_cookies(raw)
        http_email, http_tok = _http_signed_in_email(filt) if filt else ("", None)
        dups = {}
        for c in raw:
            if "google.com" in c.get("domain", ""):
                dups.setdefault(c["name"], []).append(
                    (c.get("domain"), bool(c.get("partitionKey")), len(c.get("value", "")))
                )
        multi = {k: v for k, v in dups.items() if len(v) > 1}
        print(f"=== {name} ===")
        print(
            "  auth.json:",
            "email=", auth.get("email"),
            "last_refreshed=", auth.get("last_refreshed"),
            "has_1psid=", bool(auth.get("cookies", {}).get("__Secure-1PSID")),
            "has_1psidts=", bool(auth.get("cookies", {}).get("__Secure-1PSIDTS")),
            "has_snlm0e=", bool(auth.get("tokens", {}).get("snlm0e")),
        )
        print("  daemon:", dstatus, "port:", port, "chrome_url:", url)
        print("  chrome_email:", chrome_email, "chrome_has_snlm0e:", has_sn)
        print(
            "  raw_cookies:", len(raw),
            "filtered:", len(filt),
            "has_1PSID:", "__Secure-1PSID" in filt,
            "has_1PSIDTS:", "__Secure-1PSIDTS" in filt,
            "http_email:", http_email,
            "http_has_sn:", bool(http_tok),
        )
        print("  multi_domain_cookies:", multi)


async def test_one_profile(name: str):
    print(f"\n--- Testing client + limits + PONG on '{name}' ---")
    client = GeminiClient(profile_name=name, timeout=60.0)
    try:
        await client.init()
        try:
            lim_svc = LimitsService(client)
            limits = await lim_svc.get_limits()
            pro = [l for l in limits if "Pro Prompts" in l.name or "Thinking" in l.name]
            print(f"  [{name}] limits count={len(limits)}, pro/thinking={pro}")
        except Exception as e:
            print(f"  [{name}] limits error: {e}")

        svc = ChatService(client)
        resp = await svc.send(
            "Reply with PONG and nothing else.",
            model="gemini-4-argon",
            thinking_level="high",
        )
        cid = resp.metadata.cid if resp.metadata else None
        print(f"  [{name}] PONG turn 1 ok! reply={resp.text!r} cid={cid} model_hash={resp.server_model_hash}")
        if cid:
            resp2 = await svc.send(
                "Reply with OK2 and nothing else.",
                model="gemini-4-argon",
                thinking_level="high",
            )
            print(f"  [{name}] PONG turn 2 ok! reply={resp2.text!r} same_cid={resp2.metadata.cid == cid if resp2.metadata else None}")
    except Exception as e:
        print(f"  [{name}] ERROR: {type(e).__name__}: {e}")
    finally:
        await client.close()


async def main():
    inspect_metadata()
    for name in PROFILES:
        await test_one_profile(name)


if __name__ == "__main__":
    asyncio.run(main())


# File: C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch\diag_real_argon.py
from __future__ import annotations

import asyncio
import base64
import json
import sys
import time
from urllib.parse import parse_qsl, urlsplit

sys.stdout.reconfigure(encoding="utf-8")

from gemini_web_mcp_cli.core.cdp import get_gemini_page_ws_url, navigate_to_url, run_js
from gemini_web_mcp_cli.core.client import GeminiClient
from gemini_web_mcp_cli.core.constants import get_model
from gemini_web_mcp_cli.core.token_factory import TokenFactory
from gemini_web_mcp_cli.core.webchannel import (
    MODEL_BIN_HEADER,
    _pb_fields,
    apply_model,
    decode_forward_body,
    find_setup_message,
    setup_inner,
)


def inspect_profile(prof: str) -> None:
    print(f"\n=== Inspecting {prof} ===", flush=True)
    c_tmp = GeminiClient(profile_name=prof)
    tf = TokenFactory(
        chrome_profile_path=c_tmp.auth_manager.load().chrome_profile_path,
        profile_name=prof,
    )
    tf.ensure_ready()
    navigate_to_url(tf._ws_url, "https://gemini.google.com/app")
    ready = tf._wait_for_input(timeout=20)
    print(f"ready={ready}", flush=True)

    # Check what DOM elements exist for mode picker
    picker_dom = run_js(
        tf._ws_url,
        """
        (() => {
            const btn = document.querySelector('[data-test-id="bard-mode-menu-button"]');
            return btn ? {tag: btn.tagName, text: btn.innerText, aria: btn.getAttribute('aria-label')} : null;
        })()
        """,
    )
    print("picker_dom:", picker_dom, flush=True)

    for lvl in ("low", "medium", "high"):
        m = get_model("gemini-4-argon").with_thinking_level(lvl)
        ok = tf._set_model_picker(m)
        # Re-read button label + capture raw XHR (aborted)
        lbl = run_js(tf._ws_url, "document.querySelector('[data-test-id=\"bard-mode-menu-button\"]')?.innerText")
        cap = tf.capture(prompt="Say PONG", model=m)
        pb_dec = []
        for k, v in parse_qsl(urlsplit(cap.url).query, keep_blank_values=True):
            if k == "$httpHeaders":
                for line in v.split("\r\n"):
                    name, _, val = line.partition(":")
                    if name.strip().lower() == MODEL_BIN_HEADER:
                        raw = base64.b64decode(val.strip() + "=" * (-len(val.strip()) % 4))
                        for f, w, enc in _pb_fields(raw):
                            pb_dec.append((f, w, enc[1:].decode(errors="replace") if w == 2 else int.from_bytes(enc, "big")))
        msgs = decode_forward_body(cap.body)
        setup = find_setup_message(msgs)
        inner = setup_inner(setup) if setup else None
        raw_req0 = dict(parse_qsl(cap.body, keep_blank_values=True)).get("req0___data__", "")
        is_b64 = not raw_req0.lstrip().startswith("[")
        print(f"[{prof}][{lvl}] picker_ok={ok} btn_text={lbl!r} is_b64={is_b64} body_len={len(raw_req0)}", flush=True)
        print(f"  pb_fields_before_apply={pb_dec}", flush=True)
        print(f"  setup[0][0]={setup[0][0] if setup else None}", flush=True)
        print(f"  inner[75:]={inner[75:] if inner else None}", flush=True)
        # Also print pb after apply_model
        applied_url = apply_model(cap.url, setup, m)
        pb_after = []
        for k, v in parse_qsl(urlsplit(applied_url).query, keep_blank_values=True):
            if k == "$httpHeaders":
                for line in v.split("\r\n"):
                    name, _, val = line.partition(":")
                    if name.strip().lower() == MODEL_BIN_HEADER:
                        raw = base64.b64decode(val.strip() + "=" * (-len(val.strip()) % 4))
                        for f, w, enc in _pb_fields(raw):
                            pb_after.append((f, w, enc[1:].decode(errors="replace") if w == 2 else int.from_bytes(enc, "big")))
        print(f"  pb_fields_after_apply={pb_after}", flush=True)

    # Check if native browser send (NO abort!) works quickly on niyyah/smallbusiness for High
    m_high = get_model("gemini-4-argon").with_thinking_level("high")
    tf._wait_for_input(timeout=15)
    tf._set_model_picker(m_high)
    # Check what menu items actually look like inside thinking_level submenu
    submenu = run_js(
        tf._ws_url,
        """
        (() => {
            document.body.click();
            const host = document.querySelector('[data-test-id="bard-mode-menu-button"]');
            const btn = host.tagName === 'BUTTON' ? host : (host.querySelector('button') || host);
            btn.click();
            return new Promise(resolve => setTimeout(() => {
                const row = Array.from(document.querySelectorAll('[role="menuitem"]')).find(e => e.getAttribute('value') === 'thinking_level');
                if (!row) { document.body.click(); resolve('no_row'); return; }
                row.click();
                setTimeout(() => {
                    const items = Array.from(document.querySelectorAll('[role="menuitem"], [role="menuitemradio"]')).map(el => ({
                        role: el.getAttribute('role'),
                        val: el.getAttribute('value'),
                        tid: el.getAttribute('data-test-id'),
                        text: (el.innerText || '').trim(),
                        cls: el.className,
                        ariaChecked: el.getAttribute('aria-checked'),
                    }));
                    document.body.click();
                    resolve(items);
                }, 400);
            }, 400));
        })()
        """,
    )
    print(f"[{prof}] actual submenu DOM items:", json.dumps(submenu, ensure_ascii=False), flush=True)
    tf.shutdown()


inspect_profile("smallbusiness")
inspect_profile("niyyah")


# File: C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch\diag_ui_cookies.py
from pathlib import Path
from gemini_web_mcp_cli.core.cdp import get_gemini_page_ws_url, get_page_cookies, run_js, get_pages
from gemini_web_mcp_cli.core.chrome_manager import check_daemon_health
from gemini_web_mcp_cli.core.keepalive import _http_signed_in_email

def filter_exact_google_com(raw):
    # First prefer exact .google.com / gemini.google.com / .clients6.google.com over ccTLDs like .google.com.eg
    cookies = {}
    # Order: less specific non-.google.com subdomains ending in .google.com? Wait:
    for c in raw:
        d = c.get("domain", "")
        if d == ".google.com" or d == "gemini.google.com" or d.endswith(".google.com"):
            if d == ".google.com":
                continue
            cookies[c["name"]] = c["value"]
    for c in raw:
        if c.get("domain") == ".google.com":
            cookies[c["name"]] = c["value"]
    for c in raw:
        if c.get("domain") == "gemini.google.com":
            cookies[c["name"]] = c["value"]
    return cookies

for name in ["default", "smallbusiness", "abod", "qoun", "niyyah"]:
    info, _ = check_daemon_health(name)
    port = info.port
    ws = get_gemini_page_ws_url(port)
    raw = get_page_cookies(ws)
    exact = filter_exact_google_com(raw)
    email, tok = _http_signed_in_email(exact)
    print(f"=== {name} (port {port}) ===")
    print("  pages:", [(p.get("title"), p.get("url", "")[:60]) for p in get_pages(port) if p.get("type") == "page"])
    print("  exact .google.com filter -> http_email:", email, "has_snlm0e:", bool(tok))
    # Also inspect mode picker buttons/elements in DOM
    ui_info = run_js(ws, """
    (() => {
        const btns = Array.from(document.querySelectorAll('button')).map(b => ({
            text: (b.innerText || '').trim().slice(0, 60),
            aria: b.getAttribute('aria-label') || '',
            tid: b.getAttribute('data-test-id') || '',
            cls: (b.className || '').slice(0, 60)
        })).filter(x => x.aria || x.tid || x.text);
        const tids = Array.from(document.querySelectorAll('[data-test-id]')).map(e => e.getAttribute('data-test-id'));
        return {btnCount: btns.length, interestingBtns: btns.filter(x => /mode|model|pro|flash|argon|thinking|fast|picker/i.test(x.text + ' ' + x.aria + ' ' + x.tid)), tids: tids.slice(0, 30)};
    })()
    """)
    print("  UI picker/btns:", ui_info)


# File: C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\.system_generated\tasks\task-9936.log
2026-11-10 21:33:51.498 | DEBUG    | gemini_web_mcp_cli.core.auth:refresh_tokens:227 - Refreshing tokens from Gemini app page...
2026-11-10 21:33:51.612 | DEBUG    | gemini_web_mcp_cli.core.auth:refresh_tokens:227 - Refreshing tokens from Gemini app page...
2026-11-10 21:33:52.210 | DEBUG    | gemini_web_mcp_cli.core.profiles:save_auth:379 - Saved auth for profile: qoun
2026-11-10 21:33:52.210 | DEBUG    | gemini_web_mcp_cli.core.auth:refresh_tokens:243 - Tokens refreshed successfully.
2026-11-10 21:33:52.217 | DEBUG    | gemini_web_mcp_cli.core.client:init:157 - Pre-populated 31 browser cookies from auth state
2026-11-10 21:33:52.217 | INFO     | gemini_web_mcp_cli.core.client:init:163 - GeminiClient initialized.
2026-11-10 21:33:52.225 | DEBUG    | gemini_web_mcp_cli.core.client:_execute_browser_batch:509 - batchexecute (browser cookies): ['hNvQHb']
2026-11-10 21:33:52.320 | DEBUG    | gemini_web_mcp_cli.core.profiles:save_auth:379 - Saved auth for profile: niyyah
2026-11-10 21:33:52.320 | DEBUG    | gemini_web_mcp_cli.core.auth:refresh_tokens:243 - Tokens refreshed successfully.
2026-11-10 21:33:52.329 | DEBUG    | gemini_web_mcp_cli.core.client:init:157 - Pre-populated 31 browser cookies from auth state
2026-11-10 21:33:52.330 | INFO     | gemini_web_mcp_cli.core.client:init:163 - GeminiClient initialized.
2026-11-10 21:33:52.338 | DEBUG    | gemini_web_mcp_cli.core.client:_execute_browser_batch:509 - batchexecute (browser cookies): ['qpEbW', 'qpEbW', 'qpEbW', 'qpEbW', 'qpEbW', 'qpEbW', 'qpEbW', 'qpEbW', 'qpEbW', 'qpEbW', 'qpEbW', 'qpEbW', 'qpEbW']
2026-11-10 21:33:54.642 | DEBUG    | gemini_web_mcp_cli.core.client:_ensure_browser_cookies:391 - Extracting browser cookies from Chrome daemon on port 9225
2026-11-10 21:33:54.702 | INFO     | gemini_web_mcp_cli.core.client:_extract_from_port:369 - Browser cookies extracted from Chrome (31 cookies)
2026-11-10 21:33:54.702 | DEBUG    | gemini_web_mcp_cli.core.client:_execute_browser_batch:509 - batchexecute (browser cookies): ['hNvQHb']
2026-11-10 21:33:54.775 | DEBUG    | gemini_web_mcp_cli.core.cdp:_find_browser_binary:539 - Browser detected: Google Chrome at C:\Program Files\Google\Chrome\Application\chrome.exe
2026-11-10 21:33:56.833 | DEBUG    | gemini_web_mcp_cli.core.cdp:find_existing_gemcli_chrome:339 - Reusing mapped Chrome on port 9226 for profile 'niyyah'
2026-11-10 21:33:56.844 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_ensure_ready_locked:795 - Token Factory: reusing Chrome on port 9226
2026-11-10 21:33:56.911 | DEBUG    | gemini_web_mcp_cli.core.daemon_idle:ensure_watcher:183 - Chrome idle watcher started (PID 70324)
2026-11-10 21:33:56.911 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_ensure_ready_locked:919 - Token Factory: ready
2026-11-10 21:33:57.040 | DEBUG    | gemini_web_mcp_cli.core.cdp:find_existing_gemcli_chrome:339 - Reusing mapped Chrome on port 9225 for profile 'qoun'
2026-11-10 21:33:57.050 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_ensure_ready_locked:795 - Token Factory: reusing Chrome on port 9225
2026-11-10 21:33:57.092 | DEBUG    | gemini_web_mcp_cli.core.daemon_idle:ensure_watcher:183 - Chrome idle watcher started (PID 70468)
2026-11-10 21:33:57.092 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_ensure_ready_locked:919 - Token Factory: ready
2026-11-10 21:33:59.965 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_set_model_picker:1277 - Token Factory: model picker set to argon
2026-11-10 21:34:00.128 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_set_model_picker:1277 - Token Factory: model picker set to argon
2026-11-10 21:34:00.269 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_set_composer_mode:1304 - Token Factory: composer mode Chat already
2026-11-10 21:34:00.434 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_set_composer_mode:1304 - Token Factory: composer mode Chat already
2026-11-10 21:34:02.059 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_capture_locked:1563 - Token Factory: captured processSession request
2026-11-10 21:34:02.071 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_capture_locked:1601 - Token Factory: captured Chrome SNlM0e (attempt 1, 42 chars)
2026-11-10 21:34:02.277 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_capture_locked:1563 - Token Factory: captured processSession request
2026-11-10 21:34:02.307 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_capture_locked:1601 - Token Factory: captured Chrome SNlM0e (attempt 1, 42 chars)
2026-11-10 21:34:06.241 | DEBUG    | gemini_web_mcp_cli.core.profiles:save_auth:379 - Saved auth for profile: qoun
2026-11-10 21:34:06.241 | DEBUG    | gemini_web_mcp_cli.core.client:_send_via_token_factory:1146 - Token Factory: synced fresh browser cookies back to AuthManager.
2026-11-10 21:34:06.258 | DEBUG    | gemini_web_mcp_cli.core.profiles:save_auth:379 - Saved auth for profile: niyyah
2026-11-10 21:34:06.258 | DEBUG    | gemini_web_mcp_cli.core.client:_send_via_token_factory:1146 - Token Factory: synced fresh browser cookies back to AuthManager.
2026-11-10 21:34:10.447 | DEBUG    | gemini_web_mcp_cli.core.client:_replay_process_session:1228 - Token Factory (processSession) response: text=True, images=False, video=False, music=False, model=56fdd199312815e2, candidates=1
2026-11-10 21:34:16.263 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_set_model_picker:1277 - Token Factory: model picker set to argon
2026-11-10 21:34:16.578 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_set_composer_mode:1304 - Token Factory: composer mode Chat already
2026-11-10 21:34:18.410 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_capture_locked:1563 - Token Factory: captured processSession request
2026-11-10 21:34:18.422 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_capture_locked:1601 - Token Factory: captured Chrome SNlM0e (attempt 1, 42 chars)
2026-11-10 21:34:22.494 | DEBUG    | gemini_web_mcp_cli.core.profiles:save_auth:379 - Saved auth for profile: niyyah
2026-11-10 21:34:22.494 | DEBUG    | gemini_web_mcp_cli.core.client:_send_via_token_factory:1146 - Token Factory: synced fresh browser cookies back to AuthManager.
2026-11-10 21:34:56.315 | DEBUG    | gemini_web_mcp_cli.core.client:_replay_process_session:1228 - Token Factory (processSession) response: text=True, images=False, video=False, music=False, model=56fdd199312815e2, candidates=1
2026-11-10 21:34:56.317 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_shutdown_locked:1715 - Token Factory: shutdown
2026-11-10 21:37:43.266 | DEBUG    | gemini_web_mcp_cli.core.webchannel:replay:519 - processSession transcript: 14
[[1,["noop"]]]12
[[2,[[[]]]]]147
[[3,[[null,["1",null,null,null,null,null,[[0,["64bffaa5-0fd7-4775-bbfc-47b2f204782c"],null,[null,null,null,[null,["c_9444b56dafa2f9b8",""]]]]]]]]]]301
[[4,[[null,["2",null,null,null,null,null,[[0,["r_7bc40cf1a3325bbb"],null,[null,null,null,[null,["c_9444b56dafa2f9b8","r_7bc40cf1a3325bbb"],null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,"r_7bc40cf1a3325bbb",null,null,["nD38AlZjTHZCcB2kVQCpcwgdhxBo4IkVivKrkjZaDLc"]]]]]]]]]]14
[[5,["noop"]]]14
[[6,["noop"]]]14
[[7,["noop"]]]14
[[8,["noop"]]]14
[[9,["noop"]]]15
[[10,["noop"]]]15
[[11,["noop"]]]15
[[12,["noop"]]]15
[[13,["noop"]]]28
[[14,[[null,null,null,[]]]]]
2026-11-10 21:37:43.271 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_shutdown_locked:1715 - Token Factory: shutdown
[niyyah limits] count=13 pro=[('Pro Prompts', 0, 2399), ('Thinking Prompts', 0, 2399), ('Nano Banana Pro', 0, 2399)]
[qoun read c_1ea2e77b2066f070] len=4 preview=None
[niyyah argon medium PONG] OK in 15.7s reply='PONG' thoughts=0 hash=56fdd199312815e2 cid=c_cd5b7bc461738961
[qoun argon medium B7p3] OK in 61.3s chars=10546 thoughts=0 hash=56fdd199312815e2 cid=c_4e85b3c0104621f1
[niyyah argon high PONG] ERR after 212.8s: APIError: Gemini ended the processSession stream without an answer after 201s.
2026-11-10 21:37:43.277 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_shutdown_locked:1715 - Token Factory: shutdown
2026-11-10 21:37:43.277 | DEBUG    | gemini_web_mcp_cli.core.token_factory:_shutdown_locked:1715 - Token Factory: shutdown


# File: d:\AI_Projects\waqfWibtida2\data\llm_prototype\all_114_surahs_diagnostic.json
{
  "nahhas_qiraat_or_wakadha_traps": [
    {
      "surah": 2,
      "ayah": 1,
      "stops": [
        [
          1,
          "الٓمٓ",
          [
            "تام",
            "كاف",
            "لا يوقف"
          ]
        ]
      ],
      "text": "﴿الم﴾ في القطع عليها والائتناف بما بعدها أربعة أقوال: منهن أن فيها ثلاثة أتمة، والقول الثاني: أن القطع على (الم) كاف وليس بتمام والقول الثالث: أن القطع عليها ليس بتام ولا كاف والقول الرابع: أن القطع على (الم) تمام. قال أبو جعفر وهذه الأقوال يبينها كلام العلماء"
    },
    {
      "surah": 2,
      "ayah": 2,
      "stops": [
        [
          1,
          "ذَٰلِكَ",
          [
            "لا يوقف"
          ]
        ],
        [
          2,
          "ٱلْكِتَـٰبُ",
          [
            "تام",
            "لا يوقف"
          ]
        ],
        [
          4,
          "رَيْبَ",
          [
            "تام",
            "لا يوقف"
          ]
        ],
        [
          5,
          "فِيهِ",
          [
            "تام"
          ]
        ],
        [
          7,
          "لِّلْمُتَّقِينَ",
          [
            "تام",
            "حسن",
            "لا يوقف"
          ]
        ]
      ],
      "text": "التمام ﴿ذَٰلِكَ الْكِتَابُ﴾ على أن يكون ما بعده مستأنفًا فمن التقديرات أن يكون ذلك مرفوعًا بالابتداء و (الكتاب) خبره وهذا قول أبي حاتم وقال: ومثله ذلك، وقال أبو عبيدة ذلك بمعنى هذا وأنشدوا: أقول له والرمح يأطر متنه = تأمل خفافًا أنني أنا ذلكا أي: أنا هذا، قال "
    },
    {
      "surah": 2,
      "ayah": 7,
      "stops": [
        [
          4,
          "قُلُوبِهِمْ",
          [
            "تام",
            "لا يوقف"
          ]
        ],
        [
          6,
          "سَمْعِهِمْ",
          [
            "تام",
            "كاف",
            "لا يوقف"
          ]
        ],
        [
          9,
          "غِشَـٰوَةٌۭ",
          [
            "كاف"
          ]
        ],
        [
          12,
          "عَظِيمٌۭ",
          [
            "تام",
            "حسن"
          ]
        ]
      ],
      "text": "القطع على ﴿غِشَاوَةٌ وَلَهُمْ عَذَابٌ عَظِيمٌ﴾، تمام حسن لأنه قد انقضت القصة في الكافرين وابتدأت قصة المنافقين. كما حدثنا أبو علي محمد بن جعفر بالأنبار قال: أخبرنا محمد بن إسماعيل حدثنا عمر وحدثنا أسباط بن نصر عن السدي ﴿وَمِنَ النَّاسِ مَن يَقُولُ آمَنَّا بِال"
    },
    {
      "surah": 2,
      "ayah": 37,
      "stops": [
        [
          4,
          "رَّبِّهِۦ",
          [
            "لا يوقف",
            "كاف"
          ]
        ],
        [
          7,
          "عَلَيْهِ",
          [
            "صالح"
          ]
        ],
        [
          11,
          "ٱلرَّحِيمُ",
          [
            "حسن"
          ]
        ]
      ],
      "text": "﴿فَتَلَقَّىٰ آدَمُ مِن رَّبِّهِ﴾ ليس بقطع كاف حتى يأتي بالمفعول، قال محمد بن سعدان: وحدثنا عبد الوهاب، قال حدثنا سعيد عن قتاده عن ابن عباس والحجاج عن جرير بن حازم عن حميد عن مجاهد وعبيد بن عقيل عن شبل بن عباد عن عبد الله بن كثير المكي (فتلقى آدم من ربه كلمات) "
    },
    {
      "surah": 2,
      "ayah": 102,
      "stops": [
        [
          13,
          "كَفَرُوا۟",
          [
            "كاف"
          ]
        ],
        [
          16,
          "ٱلسِّحْرَ",
          [
            "كاف",
            "لا يوقف"
          ]
        ],
        [
          20,
          "ٱلْمَلَكَيْنِ",
          [
            "كاف",
            "تام"
          ]
        ],
        [
          42,
          "وَزَوْجِهِۦ",
          [
            "صالح"
          ]
        ],
        [
          51,
          "ٱللَّهِ",
          [
            "كاف"
          ]
        ],
        [
          56,
          "يَنفَعُهُمْ",
          [
            "كاف"
          ]
        ],
        [
          66,
          "خَلَـٰقٍۢ",
          [
            "كاف"
          ]
        ],
        [
          74,
          "يَعْلَمُونَ",
          [
            "تام"
          ]
        ]
      ],
      "text": "﴿وَلَٰكِنَّ الشَّيَاطِينَ كَفَرُوا﴾ وقف كاف إن قدرت يعلمون مؤتنفًا، وإن قدرته خبر للكن أو في موضع نصب على الحال لم يقف على كفروا، ﴿يُعَلِّمُونَ النَّاسَ السِّحْرَ﴾ وقف كاف إن جعلت ما نافية وإن جعلتها في موضع نصب لم يقف على (السحر) لأنها معطوفة عليه. ﴿وَمَا أُن"
    },
    {
      "surah": 2,
      "ayah": 107,
      "stops": [
        [
          17,
          "نَصِيرٍ",
          [
            "حسن"
          ]
        ]
      ],
      "text": "﴿وَمَا لَكُم مِّن دُونِ اللَّهِ مِن وَلِيٍّ وَلَا نَصِيرٍ﴾ وقف حسن وكذا على قراءة من قرأ ولا نصير لأنه معطوف على الموضع وليس بمبتدأ لأن المعنى وما لكم سوى الله وما لكم بعد الله من ولي ولا نصير، قال أميه: يا نفس ما لك دون الله من واق = وما على حدثان الدهر من با"
    },
    {
      "surah": 2,
      "ayah": 119,
      "stops": [
        [
          5,
          "وَنَذِيرًۭا",
          [
            "لا يوقف",
            "تام"
          ]
        ]
      ],
      "text": "﴿إِنَّا أَرْسَلْنَاكَ بِالْحَقِّ بَشِيرًا وَنَذِيرًا﴾ ليس بتمام على ما روى في الحديث أن النبي صلى الله عليه وسلم قال: ليت شعري ما فعل أبواي، فأنزل الله جل وعز ﴿إِنَّا أَرْسَلْنَاكَ بِالْحَقِّ بَشِيرًا وَنَذِيرًا وَلَا تُسْأَلُ عَنْ أَصْحَابِ الْجَحِيمِ﴾، وقد ق"
    },
    {
      "surah": 2,
      "ayah": 179,
      "stops": [
        [
          8,
          "تَتَّقُونَ",
          [
            "كاف",
            "تام"
          ]
        ]
      ],
      "text": "﴿وَلَكُمْ فِي الْقِصَاصِ حَيَاةٌ يَا أُولِي الْأَلْبَابِ لَعَلَّكُمْ تَتَّقُونَ﴾ قطع كاف، وحكى ابن شاذان عن أبي عبد الله وهو محمد بن عيسى المقرئ قال كتب عليكم إذا حضر أحدكم الموت إن ترك خيرًا وقف تام قال أبو جعفر: هذا غلط وقد بين ذلك النحويون، ففي قول الكسائي "
    },
    {
      "surah": 2,
      "ayah": 196,
      "stops": [
        [
          4,
          "لِلَّهِ",
          [
            "جائز"
          ]
        ],
        [
          10,
          "ٱلْهَدْىِ",
          [
            "كاف"
          ]
        ],
        [
          17,
          "مَحِلَّهُۥ",
          [
            "كاف"
          ]
        ],
        [
          33,
          "نُسُكٍۢ",
          [
            "كاف"
          ]
        ],
        [
          73,
          "ٱلْعِقَابِ",
          [
            "تام"
          ]
        ]
      ],
      "text": "ومن الوقف ﴿وَأَتِمُّوا الْحَجَّ وَالْعُمْرَةَ لِلَّهِ﴾ من رفع فقرأ (والعمرة لله) وقف (وأتموا الحج) قال أبو عبيدة (والعمرة لله) استئناف ﴿فَإِنْ أُحْصِرْتُمْ فَمَا اسْتَيْسَرَ مِنَ الْهَدْيِ﴾ قطع كاف وكذا ﴿حَتَّىٰ يَبْلُغَ الْهَدْيُ مَحِلَّهُ﴾ وكذلك ﴿أَوْ نُسُكٍ"
    },
    {
      "surah": 2,
      "ayah": 197,
      "stops": [
        [
          3,
          "مَّعْلُومَـٰتٌۭ",
          [
            "صالح",
            "حسن",
            "تام"
          ]
        ],
        [
          21,
          "ٱللَّهُ",
          [
            "كاف"
          ]
        ],
        [
          22,
          "وَتَزَوَّدُوا۟",
          [
            "كاف"
          ]
        ],
        [
          27,
          "وَٱتَّقُونِ",
          [
            "جائز"
          ]
        ],
        [
          29,
          "ٱلْأَلْبَـٰبِ",
          [
            "كاف",
            "تام"
          ]
        ]
      ],
      "text": "﴿الْحَجُّ أَشْهُرٌ مَّعْلُومَاتٌ﴾ قطع صالح والتقدير عند القراء وقت الحج أشهر معلومات فمن فرض فيهن الحج فلا رفث ولا فسوق ولا جدال في الحج هذا وقف حسن على هذه القراءة، أكثر القراء قرأ بها الحسن وقتادة وشيبة ونافع وعاصم والأعمش وحمزة والكسائي وتفسير ابن عباس يدل "
    },
    {
      "surah": 2,
      "ayah": 275,
      "stops": [
        [
          20,
          "ٱلرِّبَوٰا۟",
          [
            "حسن"
          ]
        ],
        [
          45,
          "خَـٰلِدُونَ",
          [
            "كاف"
          ]
        ]
      ],
      "text": "وخالفه أبو حاتم وغيره فقالوا الوقف ﴿ذَٰلِكَ بِأَنَّهُمْ قَالُوا إِنَّمَا الْبَيْعُ مِثْلُ الرِّبَا﴾، وقال أبو جعفر: وهذا قطع حسن لأنه قد انقطع كلامهم كما قرأ الحسن بن عبد الله بن محمد عن يحيى بن عبد الله بن بكير حدثني ابن لهيعه عن عطا بن دينار عن سعيد بن جبير "
    },
    {
      "surah": 2,
      "ayah": 282,
      "stops": [
        [
          47,
          "يُمِلَّ",
          [
            "كاف"
          ]
        ],
        [
          48,
          "هُوَ",
          [
            "تام"
          ]
        ],
        [
          65,
          "ٱلشُّهَدَآءِ",
          [
            "صالح"
          ]
        ],
        [
          77,
          "دُعُوا۟",
          [
            "كاف"
          ]
        ],
        [
          110,
          "تَبَايَعْتُمْ",
          [
            "كاف"
          ]
        ],
        [
          120,
          "بِكُمْ",
          [
            "حسن"
          ]
        ],
        [
          128,
          "عَلِيمٌۭ",
          [
            "حسن"
          ]
        ]
      ],
      "text": "قال يعقوب: ومن الوقف الكافي ﴿أَوْ لَا يَسْتَطِيعُ أَن يُمِلَّ﴾ قال واكتفاء التمام (أن يمل هو) قال والمعنى: أن يمله وجعل الواو صلة، قال أبو جعفر: هذا القول خطأ وكذا العلة لأنه إذا وقف أن يمل فلم يأت جواب الشرط ولم يأت بقوله هو فأفرد التوكيد أو الفاعل من الفعل ث"
    },
    {
      "surah": 2,
      "ayah": 284,
      "stops": [
        [
          17,
          "ٱللَّهُ",
          [
            "تام",
            "لا يوقف"
          ]
        ],
        [
          23,
          "يَشَآءُ",
          [
            "حسن"
          ]
        ],
        [
          28,
          "قَدِيرٌ",
          [
            "تام"
          ]
        ]
      ],
      "text": "﴿يُحَاسِبْكُم بِهِ اللَّهُ﴾ فهذا الوقف التمام تم، قال جل وعز ﴿فَيَغْفِرُ لِمَن يَشَاءُ وَيُعَذِّبُ مَن يَشَاءُ﴾، قال أبو جعفر: كذا قرأ يعقوب بالرفع وهي قراءة الحسن وأبي جعفر وعاصم وقراءة نافع وأبي عمرو وعيسى والأعمش وحمزة والكسائي ﴿فَيَغْفِرُ لِمَن يَشَاءُ وَي"
    },
    {
      "surah": 3,
      "ayah": 7,
      "stops": [
        [
          8,
          "مُّحْكَمَـٰتٌ",
          [
            "صالح"
          ]
        ],
        [
          11,
          "ٱلْكِتَـٰبِ",
          [
            "صالح"
          ]
        ],
        [
          13,
          "مُتَشَـٰبِهَـٰتٌۭ",
          [
            "كاف",
            "حسن"
          ]
        ],
        [
          26,
          "تَأْوِيلِهِۦ",
          [
            "صالح"
          ]
        ],
        [
          31,
          "ٱللَّهُ",
          [
            "تام"
          ]
        ],
        [
          32,
          "وَٱلرَّٰسِخُونَ",
          [
            "صالح"
          ]
        ],
        [
          37,
          "بِهِۦ",
          [
            "جائز"
          ]
        ],
        [
          46,
          "ٱلْأَلْبَـٰبِ",
          [
            "جائز"
          ]
        ]
      ],
      "text": "﴿مِنْهُ آيَاتٌ مُّحْكَمَاتٌ﴾ وقف صالح، قال نافع ﴿هُنَّ أُمُّ الْكِتَابِ﴾ وخالفه أبو حاتم، قال ﴿وَأُخَرُ مُتَشَابِهَاتٌ﴾ كاف حسن، ﴿وَابْتِغَاءَ تَأْوِيلِهِ﴾ وقف صالح. ﴿وَمَا يَعْلَمُ تَأْوِيلَهُ إِلَّا اللَّهُ﴾ مختلف فيه فمن العلماء من قال هو التمام ومنهم من قا"
    },
    {
      "surah": 3,
      "ayah": 11,
      "stops": [
        [
          11,
          "بِذُنُوبِهِمْ",
          [
            "لا يوقف",
            "حسن",
            "كاف"
          ]
        ],
        [
          14,
          "ٱلْعِقَابِ",
          [
            "تام"
          ]
        ]
      ],
      "text": "والتمام ﴿وَاللَّهُ شَدِيدُ الْعِقَابِ﴾. فأما (فأخذهم الله بذنوبهم) ليس بتمام لأنه متعلق بما بعده ولكنه وقف حسن كاف، وكذا ﴿وَتُحْشَرُونَ إِلَىٰ جَهَنَّمَ وَبِئْسَ الْمِهَادُ﴾، ﴿قَدْ كَانَ لَكُمْ آيَةٌ فِي فِئَتَيْنِ الْتَقَتَا﴾ قال نافع: تم، وتابعه على ذلك محمد"
    },
    {
      "surah": 3,
      "ayah": 37,
      "stops": [
        [
          7,
          "حَسَنًۭا",
          [
            "حسن"
          ]
        ],
        [
          34,
          "حِسَابٍ",
          [
            "كاف"
          ]
        ]
      ],
      "text": "﴿فَتَقَبَّلَهَا رَبُّهَا بِقَبُولٍ حَسَنٍ وَأَنبَتَهَا نَبَاتًا حَسَنًا﴾ قطع حسن على قراءة أهل الحرمين وأبي عمر ولأنهم قرأوا ﴿وَكَفَّلَهَا﴾ وكذا على قراءة من قرأ وكفلها رواه عمر بن موسى عن ابن كثير وأبي عبد الله المدني وهب لغة حكاها أبو زيد ومن قرأ وكفلها وهي "
    },
    {
      "surah": 3,
      "ayah":

# File: d:\AI_Projects\waqfWibtida2\.git\objects\13\bd869936f41a8115c1d79b0977c9800dd546db
xWNQ86ibHJA*E0BK(bZ( F_cS
~ߜ&%h"ݞ3;?73-UVJfvr٣Oʅ7kK9g<|ay~ɭ-hrŏW05.Z\]*W+8ɱݒf.(.,*R
GҴA*7<L'fw}kX0V*oZQ֨5M'출pکw^)<Dcl#Fcr`wDҷue:fl(]m|Jx֨PCSY
;pP6!!RkS-mQ6hC-)%}g&Z-yӞ)O(3B 虆@|
"@gb\FR7!â/=i
P5EQ~òJr ]/T48;$T8ռ8{ I-|6`LɦУ"κ|CJˤ,F|dpɏ/*t^W;| [NPH $r0f3J{/7M;iC!( )XeSl/u+\{{o߲5PSD+'Haq,ərhs ܵR?1L_ucapW؟iOu+.Yք)J5v!?st.9՝q3m\u/]˾Ky;+n3tTp#b1ltBv )ф+T_u҂^טZ7+9ɈthBKRsM?tjɾp6 afsحDF3vCxB|6¸;! Jv9F
 2ap2_!3+a?W;2Cqns*q	NLǏ#VNy~$[A6r0; "iP-E-Iđ	q >\^0!k<B~dn:Ȼ$?SG1cLqOln@F\
`

## 2. core\rpc.py
`python
1: """RPC transport for the Gemini web interface.
2: 
3: Handles building and sending requests to:
4: - batchexecute: for CRUD operations and polling
5: - StreamGenerate: for chat, image gen, video gen, and research
6: """
7: 
8: from __future__ import annotations
9: 
10: import json
11: import random
12: from urllib.parse import urlencode
13: 
14: import httpx
15: from loguru import logger
16: 
17: from .constants import (
18:     DEFAULT_MODEL,
19:     GEMINI_HEADERS,
20:     INNER_REQ_LIST_SIZE,
21:     REQID_INCREMENT,
22:     Endpoint,
23:     Model,
24: )
25: from .models import (
26:     BatchResult,
27:     Candidate,
28:     ConversationMetadata,
29:     RPCPayload,
30:     StreamResponse,
31: )
32: from .parser import (
33:     parse_batchexecute_response,
34:     parse_stream_response,
35: )
36: 
37: 
38: def build_batchexecute_body(
39:     payloads: list[RPCPayload],
40:     access_token: str,
41: ) -> str:
42:     """Build the form-encoded body for a batchexecute request.
43: 
44:     Body has two fields:
45:     - f.req: JSON-encoded batch payload
46:     - at: access token (SNlM0e)
47:     """
48:     serialized = [[p.serialize() for p in payloads]]
49:     f_req = json.dumps(serialized)
50:     return urlencode({"f.req": f_req, "at": access_token}) + "&"
51: 
52: 
53: def build_batchexecute_url(
54:     rpc_ids: list[str],
55:     reqid: int,
56:     build_label: str | None = None,
57:     session_id: str | None = None,
58:     source_path: str = "/app",
59: ) -> str:
60:     """Build the full URL for a batchexecute request."""
61:     params: dict[str, str | int] = {
62:         "rpcids": ",".join(rpc_ids),
63:         "source-path": source_path,
64:     }
65:     if build_label:
66:         params["bl"] = build_label
67:     if session_id:
68:         params["f.sid"] = session_id
69:     params["hl"] = "en"
70:     params["_reqid"] = reqid
71:     params["rt"] = "c"
72: 
73:     return f"{Endpoint.BATCH_EXEC}?{urlencode(params)}"
74: 
75: 
76: def build_streamgenerate_body(
77:     prompt: str,
78:     access_token: str,
79:     metadata: ConversationMetadata | None = None,
80:     file_data: list | None = None,
81:     gem_id: str | None = None,
82:     tool_id: int | None = None,
83:     style_preset: dict | None = None,
84:     botguard_token: str | None = None,
85:     botguard_hash: str | None = None,
86:     video_orientation: str | None = None,
87:     image_aspect: str | None = None,
88: ) -> str:
89:     """Build the form-encoded body for a StreamGenerate request.
90: 
91:     The inner_req_list is a 70-element list. Fields are based on captures
92:     from the Gemini web UI (Feb 2026). Many fields are required for the
93:     server to properly route model selection and enable features.
94: 
95:     Args:
96:         botguard_token: BotGuard token for inner[3]. Required for tool-based
97:                         generation (music, image, video). Obtained via Token Factory.
98:         botguard_hash: Challenge hash for inner[4]. Accompanies the BotGuard token.
99:         video_orientation: "landscape" (16:9) or "portrait" (9:16). Writes the
100:                            Omni video aspect-ratio fields (inner[55] and the
101:                            video-options array at inner[0][9]).
102:         image_aspect: Image aspect ratio ("1:1", "9:16", "3:4", "4:3", "16:9").
103:                       Writes inner[55] and the image-options array at inner[0][9].
104:     """
105:     import time
106:     import uuid
107: 
108:     from .constants import (
109:         IMAGE_ASPECTS,
110:         VIDEO_ORIENTATION_FLAGS,
111:         VIDEO_ORIENTATIONS,
112:         normalize_image_aspect,
113:         normalize_video_orientation,
114:     )
115: 
116:     inner = [None] * INNER_REQ_LIST_SIZE
117: 
118:     # [0] Message content
119:     inner[0] = [prompt, 0, None, file_data, None, None, 0]
120: 
121:     # Extend inner[0] for music style preset (inner[0][9] holds preset file data)
122:     if style_preset:
123:         from .music_presets import build_preset_file_data
124: 
125:         inner[0].extend([None, None, build_preset_file_data(style_preset)])
126: 
127:     # Extend inner[0] with video options for the Omni video tool.
128:     # Chrome sends: [..., null, null, [null*6, [[null, null, null, 1|2]]]]
129:     orientation = normalize_video_orientation(video_orientation)
130:     if orientation:
131:         flag = VIDEO_ORIENTATION_FLAGS[orientation]
132:         while len(inner[0]) < 9:
133:             inner[0].append(None)
134:         inner[0].append(
135:             [None, None, None, None, None, None, [[None, None, None, flag]]]
136:         )
137: 
138:     # Extend inner[0] with image options for the Images tool.
139:     # Chrome sends: [..., null, null, [null*6, [null, [null, "16:9"]]]]
140:     aspect = normalize_image_aspect(image_aspect)
141:     if aspect:
142:         while len(inner[0]) < 9:
143:             inner[0].append(None)
144:         inner[0].append(
145:             [None, None, None, None, None, None, [None, [None, aspect]]]
146:         )
147: 
148:     # [1] Language
149:     inner[1] = ["en"]
150: 
151:     # [2] Conversation metadata for multi-turn
152:     if metadata:
153:         inner[2] = metadata.to_list()
154:     else:
155:         inner[2] = ["", "", ""] + [None] * 7
156: 
157:     # [3] BotGuard token — required for tool-based generation (music, image, video)
158:     if botguard_token:
159:         inner[3] = botguard_token
160: 
161:     # [4] BotGuard challenge hash — accompanies the token
162:     if botguard_hash:
163:         inner[4] = botguard_hash
164: 
165:     # [6] Unknown, but web UI always sends [1]
166:     inner[6] = [1]
167: 
168:     # [7] Enable snapshot streaming
169:     inner[7] = 1
170: 
171:     # [10] Unknown, web UI sends 1
172:     inner[10] = 1
173: 
174:     # [11] Unknown, web UI sends 0
175:     inner[11] = 0
176: 
177:     # [17] Unknown, web UI sends [[0]]
178:     inner[17] = [[0]]
179: 
180:     # [18] Unknown, web UI sends 0
181:     inner[18] = 0
182: 
183:     # [19] Optional gem (custom system prompt)
184:     if gem_id:
185:         inner[19] = gem_id
186: 
187:     # [27] Unknown, web UI sends 1
188:     inner[27] = 1
189: 
190:     # [30] Capabilities array - web UI sends [4]
191:     inner[30] = [4]
192: 
193:     # [41] Unknown, web UI sends [1]
194:     inner[41] = [1]
195: 
196:     # [49] Tool activation ID (e.g. 21 for music generation)
197:     if tool_id is not None:
198:         inner[49] = tool_id
199: 
200:     # [54]/[55] Tool options (video aspect ratio / image aspect ratio)
201:     if orientation:
202:         inner[54] = []
203:         inner[55] = [[VIDEO_ORIENTATIONS[orientation]]]
204:     elif aspect:
205:         inner[54] = []
206:         inner[55] = [[IMAGE_ASPECTS[aspect]]]
207: 
208:     # [53] Unknown, web UI sends 0
209:     inner[53] = 0
210: 
211:     # [59] Session UUID (matches x-goog-ext-525005358-jspb header)
212:     inner[59] = str(uuid.uuid4()).upper()
213: 
214:     # [61] Empty array
215:     inner[61] = []
216: 
217:     # [66] Timestamp [seconds, nanoseconds]
218:     now = time.time()
219:     inner[66] = [int(now), int((now % 1) * 1_000_000_000)]
220: 
221:     # [68] Value 2 -- possibly model tier or response format
222:     inner[68] = 2
223: 
224:     f_req = json.dumps([None, json.dumps(inner)])
225:     return urlencode({"f.req": f_req, "at": access_token}) + "&"
226: 
227: 
228: def build_streamgenerate_url(
229:     reqid: int,
230:     build_label: str | None = None,
231:     session_id: str | None = None,
232: ) -> str:
233:     """Build the full URL for a StreamGenerate request."""
234:     params: dict[str, str | int] = {}
235:     if build_label:
236:         params["bl"] = build_label
237:     if session_id:
238:         params["f.sid"] = session_id
239:     params["hl"] = "en"
240:     params["_reqid"] = reqid
241:     params["rt"] = "c"
242: 
243:     return f"{Endpoint.GENERATE}?{urlencode(params)}"
244: 
245: 
246: def build_headers(model: Model | None = None) -> dict[str, str]:
247:     """Build request headers, optionally including model selection."""
248:     headers = dict(GEMINI_HEADERS)
249:     if model and model.header:
250:         headers.update(model.header)
251:     return headers
252: 
253: 
254: def build_stream_response(response_text: str) -> StreamResponse:
255:     """Parse StreamGenerate response text into a StreamResponse.
256: 
257:     Merges all frames into one StreamResponse. Media fields (generated_images,
258:     generated_music, generated_video) are preserved across frames — if a later
259:     frame's candidate lacks media data that an earlier frame had, the earlier
260:     data is kept. This prevents losing music/video data when a trailing frame
261:     has text-only candidates.
262: 
263:     Used by both RPCTransport.stream_generate() and Token Factory path.
264:     """
265:     return merge_stream_frames(parse_stream_response(response_text))
266: 
267: 
268: def build_process_session_response(transcript: str) -> StreamResponse:
269:     """Parse a processSession backchannel transcript into a StreamResponse."""
270:     from .parser import parse_stream_body
271:     from .webchannel import bodies_from_text
272: 
273:     return merge_stream_frames([parse_stream_body(b) for b in bodies_from_text(transcript)])
274: 
275: 
276: def merge_stream_frames(parsed_frames: list[dict]) -> StreamResponse:
277:     """Merge parsed StreamGenerate-shaped frames into one StreamResponse."""
278:     result = StreamResponse()
279:     # Track media data from previous frames, keyed by candidate index.
280:     # Used to preserve generated_images/music/video across frame overwrites.
281:     _prev_media: dict[int, dict] = {}
282: 
283:     for frame in parsed_frames:
284:         if frame.get("metadata"):
285:             result.metadata = ConversationMetadata.from_list(frame["metadata"])
286: 
287:         if frame.get("candidates"):
288:             new_candidates = []
289:             for i, c in enumerate(frame["candidates"]):
290:                 prev = _prev_media.get(i, {})
291:                 candidate = Candidate(
292:                     rcid=c.get("rcid"),
293:                     text=c.get("text"),
294:                     thoughts=c.get("thoughts"),
295:                     web_images=c.get("web_images"),
296:                     generated_images=c.get("generated_images") or prev.get("images"),
297:                     generated_music=c.get("generated_music") or prev.get("music"),
298:                     generated_video=c.get("generated_video") or prev.get("video"),
299:                 )
300:                 new_candidates.append(candidate)
301:                 # Update media tracking for this candidate index
302:                 _prev_media[i] = {
303:                     "images": candidate.generated_images,
304:                     "music": candidate.generated_music,
305:                     "video": candidate.generated_video,
306:                 }
307:             result.candidates = new_candidates
308: 
309:         if frame.get("text"):
310:             result.text = frame["text"]
311:         if frame.get("thoughts"):
312:             result.thoughts = frame["thoughts"]
313:         if frame.get("completion") is not None:
314:             result.is_complete = True
315: 
316:         # Server-confirmed model (appears in the final frame)
317:         if frame.get("server_model_hash"):
318:             result.server_model_hash = frame["server_model_hash"]
319:             result.server_model_label = frame.get("server_model_label")
320: 
321:     # The ids frame carries [cid, rid]; the reply candidate id lives on the
322:     # candidate. Follow-ups reply to it (to_list() -> [cid, rid, rcid, ...]).
323:     if result.metadata and not result.metadata.rcid and result.candidates:
324:         result.metadata.rcid = result.candidates[0].rcid or ""
325: 
326:     return result
327: 
328: 
329: class RPCTransport:
330:     """Handles HTTP communication with the Gemini web interface.
331: 
332:     Manages:
333:     - Request ID incrementing
334:     - batchexecute requests
335:     - StreamGenerate requests
336:     - Cookie management
337:     """
338: 
339:     def __init__(
340:         self,
341:         client: httpx.AsyncClient,
342:         access_token: str,
343:         build_label: str | None = None,
344:         session_id: str | None = None,
345:     ):
346:         self.client = client
347:         self.access_token = access_token
348:         self.build_label = build_label
349:         self.session_id = session_id
350:         self._reqid = random.randint(10000, 99999)
351: 
352:     def _next_reqid(self) -> int:
353:         """Get the next request ID and increment."""
354:         current = self._reqid
355:         self._reqid += REQID_INCREMENT
356:         return current
357: 
358:     async def batchexecute(
359:         self,
360:         payloads: list[RPCPayload],
361:         source_path: str = "/app",
362:     ) -> list[BatchResult]:
363:         """Execute one or more RPC calls via batchexecute.
364: 
365:         Returns a list of BatchResult objects.
366:         """
367:         rpc_ids = [p.rpc_id for p in payloads]
368:         url = build_batchexecute_url(
369:             rpc_ids=rpc_ids,
370:             reqid=self._next_reqid(),
371:             build_label=self.build_label,
372:             session_id=self.session_id,
373:             source_path=source_path,
374:         )
375:         body = build_batchexecute_body(payloads, self.access_token)
376:         headers = build_headers()
377: 
378:         logger.debug(f"batchexecute: {rpc_ids}")
379:         response = await self.client.post(url, content=body, headers=headers)
380:         response.raise_for_status()
381: 
382:         parsed = parse_batchexecute_response(response.text)
383:         return [
384:             BatchResult(rpc_id=r["rpc_id"], data=r["data"], raw=r["raw"])
385:             for r in parsed
386:         ]
387: 
388:     async def stream_generate(
389:         self,
390:         prompt: str,
391:         model: Model | None = None,
392:         metadata: ConversationMetadata | None = None,
393:         file_data: list | None = None,
394:         gem_id: str | None = None,
395:         tool_id: int | None = None,
396:         style_preset: dict | None = None,
397:         video_orientation: str | None = None,
398:         image_aspect: str | None = None,
399:     ) -> StreamResponse:
400:         """Send a message via StreamGenerate and parse the response.
401: 
402:         This is the primary endpoint for all generation: chat, images, video, music.
403:         """
404:         url = build_streamgenerate_url(
405:             reqid=self._next_reqid(),
406:             build_label=self.build_label,
407:             session_id=self.session_id,
408:         )
409:         body = build_streamgenerate_body(
410:             prompt=prompt,
411:             access_token=self.access_token,
412:             metadata=metadata,
413:             file_data=file_data,
414:             gem_id=gem_id,
415:             tool_id=tool_id,
416:             style_preset=style_preset,
417:             video_orientation=video_orientation,
418:             image_aspect=image_aspect,
419:         )
420:         headers = build_headers(model or DEFAULT_MODEL)
421: 
422:         logger.debug(f"StreamGenerate: {prompt[:50]}...")
423:         response = await self.client.post(url, content=body, headers=headers)
424:         response.raise_for_status()
425: 
426:         return build_stream_response(response.text)
`

## 2. core\webchannel.py
`python
1: """Gemini's processSession chat transport (a Closure WebChannel session).
2: 
3: Some accounts send chats to ``geminiweb-pa.clients6.google.com/v1/processSession``
4: instead of ``StreamGenerate``. The request is the same StreamGenerate ``inner``
5: array (BotGuard token at ``inner[3]``) wrapped in a setup message; the prompt
6: travels in a separate message; the model header is sent as protobuf inside the
7: channel's ``$httpHeaders`` URL parameter; the response frames carry
8: StreamGenerate-shaped bodies. See docs/research/transport/processSession.md.
9: 
10: Token Factory captures the channel-open URL and the setup message in Chrome
11: (aborting the data POST, so Chrome sends nothing). ``replay()`` then opens a
12: fresh channel from Python with Chrome's cookies and sends the real prompt.
13: """
14: 
15: from __future__ import annotations
16: 
17: import asyncio
18: import base64
19: import json
20: import random
21: import string
22: import time
23: from typing import Any
24: from urllib.parse import parse_qsl, urlencode, urlsplit
25: 
26: import httpx
27: from loguru import logger
28: 
29: from . import protojspb
30: from .exceptions import APIError, AuthError
31: from .exceptions import TimeoutError as GeminiTimeoutError
32: from .parser import _utf16_char_count
33: from .setup_shape import SETUP_SHAPE
34: 
35: TRANSPORT_STREAMGENERATE = "streamgenerate"
36: TRANSPORT_PROCESS_SESSION = "processSession"
37: 
38: PROCESS_SESSION_URL = "https://geminiweb-pa.clients6.google.com/v1/processSession"
39: MODEL_BIN_HEADER = "x-goog-ext-525001261-bin"
40: CONTENT_TYPE_HEADER = "X-WebChannel-Content-Type"
41: JSON_CONTENT_TYPE = "application/json+protobuf"
42: 
43: 
44: 
45: # Client -> server messages (see processSession.md, "Forward messages").
46: HALF_CLOSE_MESSAGE = [None, None, None, [1]]
47: # Server -> client: the stream is finished.
48: END_OF_STREAM = [None, None, None, []]
49: 
50: # How long to keep reading after the final candidate for the title/completion
51: # frames and the end-of-stream marker.
52: _TAIL_TIMEOUT = 8.0
53: 
54: 
55: def _zx() -> str:
56:     return "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
57: 
58: 
59: # --------------------------------------------------------------------------
60: # Framing
61: # --------------------------------------------------------------------------
62: 
63: 
64: def split_frames(text: str) -> tuple[list[tuple[int, Any]], str]:
65:     """Split backchannel text into ``(array_id, payload)`` entries.
66: 
67:     Frames are ``<length>\\n<json>`` where length counts the JSON's UTF-16 code
68:     units (the newline is not counted, unlike StreamGenerate). Each JSON is a
69:     list of ``[array_id, payload]``. Returns (entries, unparsed remainder).
70:     """
71:     entries: list[tuple[int, Any]] = []
72:     pos = 0
73:     while pos < len(text):
74:         nl = text.find("\n", pos)
75:         if nl == -1 or not text[pos:nl].strip().isdigit():
76:             break
77:         length = int(text[pos:nl])
78:         start = nl + 1
79:         count, units = _utf16_char_count(text, start, length)
80:         if units < length:
81:             break  # incomplete frame
82:         chunk = text[start:start + count]
83:         pos = start + count
84:         try:
85:             frame = json.loads(chunk)
86:         except ValueError:
87:             logger.debug(f"processSession: unparsable frame {chunk[:100]!r}")
88:             continue
89:         for item in frame if isinstance(frame, list) else []:
90:             if isinstance(item, list) and len(item) == 2 and isinstance(item[0], int):
91:                 entries.append((item[0], item[1]))
92:     return entries, text[pos:]
93: 
94: 
95: def payload_entry(payload: Any) -> list | None:
96:     """Return ``[flag, [id], null, [null, null, null, body]]`` from a data payload."""
97:     try:
98:         entry = payload[0][1][6][0]
99:     except (IndexError, KeyError, TypeError):
100:         return None
101:     return entry if isinstance(entry, list) else None
102: 
103: 
104: def payload_body(payload: Any) -> list | None:
105:     """The StreamGenerate-shaped body inside a data payload, if any."""
106:     entry = payload_entry(payload)
107:     try:
108:         body = entry[3][3] if entry else None
109:     except (IndexError, TypeError):
110:         return None
111:     return body if isinstance(body, list) else None
112: 
113: 
114: def is_final_candidate(payload: Any) -> bool:
115:     """True for the payload that carries the finished candidate (flag = 1)."""
116:     entry = payload_entry(payload)
117:     return bool(entry) and entry[0] == 1
118: 
119: 
120: def is_end_of_stream(payload: Any) -> bool:
121:     return isinstance(payload, list) and bool(payload) and payload[0] == END_OF_STREAM
122: 
123: 
124: def bodies_from_text(text: str) -> list[list]:
125:     """All StreamGenerate-shaped bodies in a backchannel transcript."""
126:     entries, _ = split_frames(text)
127:     return [b for _, p in entries if (b := payload_body(p)) is not None]
128: 
129: 
130: # --------------------------------------------------------------------------
131: # Forward-channel messages
132: # --------------------------------------------------------------------------
133: 
134: 
135: def decode_forward_body(body: str) -> list[Any]:
136:     """Decode ``count=N&ofs=K&req0___data__=...`` into JSPB messages.
137: 
138:     Messages are JSON arrays, or base64 binary protobuf on accounts whose page
139:     uses ``application/x-protobuf`` (converted to JSPB, see core/protojspb.py).
140:     """
141:     fields = dict(parse_qsl(body, keep_blank_values=True))
142:     count = int(fields.get("count", "0"))
143:     return [decode_message(fields[f"req{i}___data__"]) for i in range(count)]
144: 
145: 
146: def decode_message(data: str) -> Any:
147:     """One forward-channel message: JSON array or base64 binary protobuf."""
148:     if data.lstrip().startswith("["):
149:         return json.loads(data)
150:     try:
151:         raw = base64.b64decode(data + "=" * (-len(data) % 4), validate=True)
152:     except ValueError as e:
153:         raise ValueError(f"processSession message is neither JSON nor base64: {data[:40]!r}") from e
154:     return protojspb.to_jspb(raw, SETUP_SHAPE)
155: 
156: 
157: def use_json_encoding(open_url: str) -> str:
158:     """Declare JSON messages on the channel (the server accepts both encodings)."""
159:     parts = urlsplit(open_url)
160:     query = []
161:     for key, value in parse_qsl(parts.query, keep_blank_values=True):
162:         if key == "$httpHeaders":
163:             lines = [
164:                 f"{CONTENT_TYPE_HEADER}:{JSON_CONTENT_TYPE}"
165:                 if line.partition(":")[0].strip().lower() == CONTENT_TYPE_HEADER.lower()
166:                 else line
167:                 for line in value.split("\r\n")
168:             ]
169:             value = "\r\n".join(lines)
170:         query.append((key, value))
171:     return parts._replace(query=urlencode(query)).geturl()
172: 
173: 
174: def encode_forward_body(messages: list[Any], ofs: int) -> str:
175:     parts: dict[str, Any] = {"count": len(messages), "ofs": ofs}
176:     for i, m in enumerate(messages):
177:         parts[f"req{i}___data__"] = json.dumps(m, separators=(",", ":"), ensure_ascii=False)
178:     return urlencode(parts)
179: 
180: 
181: def find_setup_message(messages: list[Any]) -> list | None:
182:     """The setup message: ``[[[1, model_hash, lang, uuid], 0, ..., [.., [inner, ..]], ..]]``."""
183:     for m in messages:
184:         if isinstance(m, list) and m and isinstance(m[0], list) and setup_inner(m) is not None:
185:             return m
186:     return None
187: 
188: 
189: def setup_inner(setup: list) -> list | None:
190:     """The StreamGenerate ``inner`` array inside a setup message.
191: 
192:     ``setup[0][7] = [null, null, null, null, [inner, null, null, 1]]``.
193:     """
194:     try:
195:         inner = setup[0][7][4][0]
196:     except (IndexError, TypeError):
197:         return None
198:     return inner if isinstance(inner, list) else None
199: 
200: 
201: def extract_botguard(body: str) -> tuple[str | None, str | None]:
202:     """BotGuard token and challenge hash from a captured processSession data POST."""
203:     try:
204:         setup = find_setup_message(decode_forward_body(body))
205:     except (ValueError, KeyError, TypeError):
206:         return None, None
207:     inner = setup_inner(setup) if setup else None
208:     if not inner or len(inner) < 5:
209:         return None, None
210:     token = inner[3] if isinstance(inner[3], str) else None
211:     hash_val = inner[4] if isinstance(inner[4], str) else None
212:     return token, hash_val
213: 
214: 
215: # Conversation to continue: inner[71] = ["c_<cid>", null x6, ""] (processSession
216: # only; StreamGenerate uses inner[2]).
217: CONVERSATION_INDEX = 71
218: 
219: 
220: def set_conversation(inner: list, cid: str) -> None:
221:     """Point the setup at conversation ``cid`` unless Chrome already did."""
222:     cid = cid if cid.startswith("c_") else f"c_{cid}"
223:     current = inner[CONVERSATION_INDEX] if len(inner) > CONVERSATION_INDEX else None
224:     if isinstance(current, list) and current and current[0] == cid:
225:         return
226:     if len(inner) <= CONVERSATION_INDEX:
227:         inner.extend([None] * (CONVERSATION_INDEX + 1 - len(inner)))
228:     inner[CONVERSATION_INDEX] = [cid, None, None, None, None, None, None, ""]
229: 
230: 
231: def prompt_message(prompt: str) -> list:
232:     return [None, [1, None, None, None, None, None, None, None, [prompt]]]
233: 
234: 
235: # --------------------------------------------------------------------------
236: # Model header (protobuf) rewrite
237: # --------------------------------------------------------------------------
238: 
239: 
240: def _read_varint(b: bytes, i: int) -> tuple[int, int]:
241:     result = shift = 0
242:     while True:
243:         c = b[i]
244:         i += 1
245:         result |= (c & 0x7F) << shift
246:         shift += 7
247:         if c < 0x80:
248:             return result, i
249: 
250: 
251: def _varint(n: int) -> bytes:
252:     out = bytearray()
253:     while True:
254:         byte = n & 0x7F
255:         n >>= 7
256:         if n:
257:             out.append(byte | 0x80)
258:         else:
259:             out.append(byte)
260:             return bytes(out)
261: 
262: 
263: def _pb_fields(b: bytes) -> list[tuple[int, int, bytes]]:
264:     """Top-level protobuf fields as (field number, wire type, encoded value)."""
265:     fields = []
266:     i = 0
267:     while i < len(b):
268:         key, j = _read_varint(b, i)
269:         field, wire = key >> 3, key & 7
270:         if wire == 0:
271:             _, k = _read_varint(b, j)
272:             value = b[j:k]
273:         elif wire == 2:
274:             n, k = _read_varint(b, j)
275:             k += n
276:             value = b[j:k]
277:         elif wire == 1:
278:             k = j + 8
279:             value = b[j:k]
280:         elif wire == 5:
281:             k = j + 4
282:             value = b[j:k]
283:         else:
284:             raise ValueError(f"unsupported protobuf wire type {wire}")
285:         fields.append((field, wire, value))
286:         i = k
287:     return fields
288: 
289: 
290: def rewrite_model_header(value: str, model_hash: str, category: int, toggle: int) -> str:
291:     """Set hash (field 5, and field 25 if present) and category/thinking (fields 15/16)."""
292:     raw = base64.b64decode(value + "=" * (-len(value) % 4))
293:     hash_enc = (2, _varint(len(model_hash)) + model_hash.encode())
294:     replacements = {
295:         5: hash_enc,
296:         15: (0, _varint(category)),
297:         16: (0, _varint(toggle)),
298:     }
299:     out = bytearray()
300:     seen = set()
301:     for field, wire, encoded in _pb_fields(raw):
302:         if field == 25:
303:             wire, encoded = hash_enc
304:         elif field in replacements:
305:             wire, encoded = replacements[field]
306:             seen.add(field)
307:         out += _varint(field << 3 | wire) + encoded
308:     for field in sorted(set(replacements) - seen):
309:         wire, encoded = replacements[field]
310:         out += _varint(field << 3 | wire) + encoded
311:     return base64.b64encode(bytes(out)).decode()
312: 
313: 
314: def _header_tail(model) -> tuple[int, int] | None:
315:     parts = str(getattr(model, "header_tail", "")).split(",")
316:     if len(parts) != 2:
317:         return None
318:     try:
319:         return int(parts[0]), int(parts[1])
320:     except ValueError:
321:         return None
322: 
323: 
324: def apply_model(open_url: str, setup: list, model) -> str:
325:     """Point the captured channel at ``model``. Returns the new open URL.
326: 
327:     Chrome's UI picker decides the captured model; like the StreamGenerate path
328:     (which overwrites the JSPB header), the requested model wins.
329:     """
330:     tail = _header_tail(model)
331:     if not getattr(model, "hash", None) or tail is None:
332:         return open_url
333:     try:
334:         setup[0][0][1] = model.hash
335:     except (IndexError, TypeError):
336:         pass
337:     parts = urlsplit(open_url)
338:     query = parse_qsl(parts.query, keep_blank_values=True)
339:     new_query = []
340:     for key, value in query:
341:         if key == "$httpHeaders":
342:             lines = value.split("\r\n")
343:             for i, line in enumerate(lines):
344:                 name, sep, val = line.partition(":")
345:                 if sep and name.strip().lower() == MODEL_BIN_HEADER:
346:                     lines[i] = f"{name}:{rewrite_model_header(val.strip(), model.hash, *tail)}"
347:             value = "\r\n".join(lines)
348:         new_query.append((key, value))
349:     return parts._replace(query=urlencode(new_query)).geturl()
350: 
351: 
352: # --------------------------------------------------------------------------
353: # Replay
354: # --------------------------------------------------------------------------
355: 
356: 
357: async def replay(
358:     client: httpx.AsyncClient,
359:     open_url: str,
360:     messages: list[Any],
361:     cookies: dict[str, str],
362:     headers: dict[str, str],
363:     timeout: float,
364: ) -> str:
365:     """Open a channel, send ``messages`` and return the backchannel transcript.
366: 
367:     Reads until the final candidate plus its title/completion frames arrive (or
368:     the server ends the stream), then half-closes and terminates the channel.
369:     """
370:     base = {
371:         "Origin": "https://gemini.google.com",
372:         "Referer": "https://gemini.google.com/",
373:     }
374:     ua = headers.get("user-agent") or headers.get("User-Agent")
375:     if ua:
376:         base["User-Agent"] = ua
377:     form = {**base, "Content-Type": "application/x-www-form-urlencoded"}
378: 
379:     parts = urlsplit(open_url)
380:     open_query = dict(parse_qsl(parts.query, keep_blank_values=True))
381:     rid = random.randint(10000, 89999)
382:     open_query.update(RID=str(rid), zx=_zx(), t="1")
383: 
384:     resp = await client.post(
385:         PROCESS_SESSION_URL, params=open_query, content="count=0",
386:         headers=form, cookies=cookies,
387:     )
388:     if resp.status_code in (401, 403):
389:         raise AuthError(f"processSession rejected the session (HTTP {resp.status_code}).")
390:     if resp.status_code != 200:
391:         raise APIError(f"processSession open failed: HTTP {resp.status_code}")
392:     gsid = resp.headers.get("x-http-session-id")
393:     entries, _ = split_frames(resp.text)
394:     sid = None
395:     for _, payload in entries:
396:         if isinstance(payload, list) and payload and payload[0] == "c":
397:             sid = payload[1]
398:     if not gsid or not sid:
399:         raise APIError(f"processSession open: no session ids in {resp.text[:120]!r}")
400: 
401:     state = {"aid": max((a for a, _ in entries), default=0), "rid": rid}
402: 
403:     def fwd_params(extra: dict | None = None) -> dict:
404:         state["rid"] += 1
405:         p = {"VER": "8", "gsessionid": gsid, "SID": sid, "RID": str(state["rid"]),
406:              "AID": str(state["aid"]), "zx": _zx(), "t": "1"}
407:         p.update(extra or {})
408:         return p
409: 
410:     async def post_messages(msgs: list[Any], ofs: int) -> None:
411:         r = await client.post(
412:             PROCESS_SESSION_URL, params=fwd_params(),
413:             content=encode_forward_body(msgs, ofs), headers=form, cookies=cookies,
414:         )
415:         if r.status_code != 200:
416:             raise APIError(f"processSession send failed: HTTP {r.status_code}")
417: 
418:     transcript: list[str] = []
419:     started_at = time.monotonic()
420:     deadline = started_at + timeout
421:     final_at: float | None = None
422:     done = False
423:     sent = False
424:     half_closed = False
425:     completion_seen = False
426:     server_error: str | None = None
427:     closed = False
428:     ended_without_answer = False  # server sent end-of-stream with no final candidate
429:     empty_reopens = 0
430: 
431:     try:
432:         while not done and time.monotonic() < deadline:
433:             q = {"gsessionid": gsid, "VER": "8", "RID": "rpc", "SID": sid,
434:                  "AID": str(state["aid"]), "CI": "0", "TYPE": "xmlhttp", "zx": _zx(), "t": "1"}
435:             async with client.stream(
436:                 "GET", PROCESS_SESSION_URL, params=q, headers=base, cookies=cookies,
437:             ) as back:
438:                 if back.status_code != 200:
439:                     raise APIError(f"processSession backchannel: HTTP {back.status_code}")
440:                 if not sent:
441:                     await post_messages(messages, 0)
442:                     sent = True
443:                 buf = ""
444:                 got_data = False
445:                 chunks = back.aiter_text()
446:                 while True:
447:                     remaining = deadline - time.monotonic()
448:                     if final_at is not None:
449:                         remaining = min(remaining, final_at + _TAIL_TIMEOUT - time.monotonic())
450:                     if remaining <= 0:
451:                         done = True
452:                         break
453:                     try:
454:                         chunk = await asyncio.wait_for(chunks.__anext__(), timeout=remaining)
455:                     except StopAsyncIteration:
456:                         break  # server closed the backchannel; reopen it
457:                     except asyncio.TimeoutError:
458:                         done = final_at is not None
459:                         break
460:                     transcript.append(chunk)
461:                     got_data = got_data or bool(chunk)
462:                     buf += chunk
463:                     parsed, buf = split_frames(buf)
464:                     for aid, payload in parsed:
465:                         state["aid"] = max(state["aid"], aid)
466:                         error = status_error(payload)
467:                         if error:
468:                             server_error = error
469:                             done = True
470:                         if payload == ["close"]:
471:                             closed = True
472:                             done = True
473:                         body = payload_body(payload)
474:                         if body is not None and _has_completion(body):
475:                             completion_seen = True
476:                         if final_at is None and is_final_candidate(payload):
477:                             final_at = time.monotonic()
478:                         if is_end_of_stream(payload):
479:                             # End-of-stream with no final candidate means Gemini
480:                             # abandoned the turn (seen with long Argon thinking).
481:                             # Do not pretend this was a client timeout.
482:                             if final_at is None and not server_error:
483:                                 ended_without_answer = True
484:                             done = True
485:                     # Title and completion token follow the final candidate;
486:                     # then half-close so the server ends the stream.
487:                     if final_at is not None and completion_seen and not half_closed and not done:
488:                         await post_messages([HALF_CLOSE_MESSAGE], len(messages))
489:                         half_closed = True
490:                     if done:
491:                         break
492:             if not done:
493:                 # Backchannel closed by the server: reopen it (WebChannel does
494:                 # the same). Keep trying until the deadline — a hard cap of a
495:                 # few empty reconnects was aborting long thinking turns around
496:                 # ~210s while still reporting "within 300s".
497:                 if got_data:
498:                     empty_reopens = 0
499:                 else:
500:                     empty_reopens += 1
501:                     await asyncio.sleep(min(5.0, 0.5 * empty_reopens))
502:     finally:
503:         try:
504:             await client.post(
505:                 PROCESS_SESSION_URL,
506:                 params={"VER": "8", "gsessionid": gsid, "SID": sid,
507:                         "RID": str(state["rid"] + 1), "TYPE": "terminate", "zx": _zx()},
508:                 headers=base, cookies=cookies,
509:             )
510:         except Exception as e:  # best effort; the server times the channel out anyway
511:             logger.debug(f"processSession terminate failed: {e}")
512: 
513:     text = "".join(transcript)
514:     elapsed = time.monotonic() - started_at
515:     if server_error:
516:         logger.debug(f"processSession transcript: {text[:2000]}")
517:         raise APIError(f"Gemini rejected the request (processSession): {server_error}")
518:     if final_at is None:
519:         logger.debug(f"processSession transcript: {text[:2000]}")
520:         if closed:
521:             raise APIError(
522:                 f"Gemini closed the processSession channel without an answer "
523:                 f"after {elapsed:.0f}s."
524:             )
525:         if ended_without_answer:
526:             raise APIError(
527:                 f"Gemini ended the processSession stream without an answer "
528:                 f"after {elapsed:.0f}s."
529:             )
530:         raise GeminiTimeoutError(
531:             f"No answer from Gemini (processSession) after {elapsed:.0f}s "
532:             f"(timeout {timeout:.0f}s)."
533:         )
534:     return text
535: 
536: 
537: def status_error(payload: Any) -> str | None:
538:     """Message of a ``{"__sm__": {"status": [code, message, details]}}`` error frame."""
539:     if not isinstance(payload, dict) or "__sm__" not in payload:
540:         return None
541:     status = payload["__sm__"].get("status") if isinstance(payload["__sm__"], dict) else None
542:     # [[[code, message, details]]] in the captures; unwrap whatever nesting arrives.
543:     while isinstance(status, list) and status and isinstance(status[0], list):
544:         status = status[0]
545:     if not isinstance(status, list) or not status:
546:         return f"unrecognised status {json.dumps(payload)[:200]}"
547:     code = status[0]
548:     if code in (0, None):
549:         return None
550:     message = status[1] if len(status) > 1 else ""
551:     return f"status {code}: {message}"
552: 
553: 
554: def _has_completion(body: list) -> bool:
555:     return len(body) > 25 and body[25] is not None
`

## 3. services\chat.py (ChatService)
`python
1: """Chat service: send messages, stream responses, manage conversations."""
2: 
3: from __future__ import annotations
4: 
5: import os
6: import re
7: 
8: from gemini_web_mcp_cli.core.client import GeminiClient
9: from gemini_web_mcp_cli.core.constants import Model
10: from gemini_web_mcp_cli.core.exceptions import AttachmentNotRead
11: from gemini_web_mcp_cli.core.models import ConversationMetadata, StreamResponse
12: 
13: # Replies that mean Gemini never saw the attachment (issue #6). Only the start
14: # of the reply is checked: that is where Gemini says it, and it keeps normal
15: # answers that later discuss "unable to view" content from matching.
16: _ATTACHMENT_NOT_READ = re.compile(
17:     r"\b(?:can(?:no|')t|could(?:n't| not)|unable to|am not able to|I'm not able to)\s+"
18:     r"(?:open|view|access|read|see|play|watch|load|process)\s+"
19:     r"(?:the |this |that |your |any )?(?:attached |uploaded )?"
20:     r"(?:file|files|attachment|attachments|video|videos|image|images|document|pdf|audio)\b"
21:     r"|\b(?:no|don't see an?y?|do not see an?y?)\s+(?:file|attachment|video|image|document)s?\s+"
22:     r"(?:was |were |is |has been )?(?:attached|uploaded|provided|included)\b",
23:     re.IGNORECASE,
24: )
25: _CHECK_CHARS = 600
26: 
27: 
28: def attachment_not_read(text: str) -> bool:
29:     """True if the reply opens by saying the attachment could not be read."""
30:     return bool(_ATTACHMENT_NOT_READ.search((text or "")[:_CHECK_CHARS]))
31: 
32: 
33: class ChatService:
34:     """Service for chat interactions with Gemini.
35: 
36:     Wraps GeminiClient.send() with conversation state management
37:     and convenience methods.
38:     """
39: 
40:     def __init__(self, client: GeminiClient):
41:         self.client = client
42:         self._metadata: ConversationMetadata | None = None
43: 
44:     async def send(
45:         self,
46:         prompt: str,
47:         model: str | Model | None = None,
48:         conversation_id: str | None = None,
49:         gem_id: str | None = None,
50:         files: list[str] | None = None,
51:         extended_thinking: bool | None = None,
52:         thinking_level: str | None = None,
53:         task: bool = False,
54:     ) -> StreamResponse:
55:         """Send a message and get a complete response.
56: 
57:         For multi-turn conversations, the metadata is automatically
58:         tracked between calls.
59: 
60:         Args:
61:             files: Optional list of file paths to upload and attach.
62:             extended_thinking: Independently enable or disable Thinking
63:                                level High (formerly Extended thinking).
64:             thinking_level: ``low``, ``medium``, or ``high``. Wins over
65:                             ``extended_thinking`` when set.
66:             task: Send through the Task composer control instead of Chat.
67:         """
68:         import mimetypes
69:         from pathlib import Path
70: 
71:         from gemini_web_mcp_cli.services.file import FileService, build_file_data
72: 
73:         file_data = None
74:         if files:
75:             file_data = []
76:             file_service = FileService(self.client)
77:             for fpath in files:
78:                 p = Path(fpath)
79:                 file_id = await file_service.upload(p)
80:                 mime_type, _ = mimetypes.guess_type(p)
81:                 mime_type = mime_type or "application/octet-stream"
82: 
83:                 file_data.append(build_file_data(file_id, p.name, mime_type))
84: 
85:         # Use stored metadata for multi-turn, or start fresh
86:         metadata = self._metadata if self._metadata and not conversation_id else None
87: 
88:         response = await self.client.send(
89:             prompt=prompt,
90:             model=model,
91:             extended_thinking=extended_thinking,
92:             thinking_level=thinking_level,
93:             task=task,
94:             metadata=metadata,
95:             gem_id=gem_id,
96:             file_data=file_data,
97:         )
98: 
99:         # Update metadata for next turn
100:         if response.metadata and response.metadata.cid:
101:             self._metadata = response.metadata
102: 
103:         if (
104:             files
105:             and os.environ.get("GEMCLI_ATTACHMENT_CHECK", "1") != "0"
106:             and attachment_not_read(response.text)
107:         ):
108:             names = ", ".join(os.path.basename(f) for f in files)
109:             raise AttachmentNotRead(
110:                 f"Gemini did not read the attachment ({names}); its reply says it "
111:                 "could not open it, so the answer was withheld (it is often "
112:                 "invented). Retry, check `gemcli -p <profile> doctor --deep`, or "
113:                 "try another profile. Set GEMCLI_ATTACHMENT_CHECK=0 to disable.",
114:                 reply=response.text,
115:             )
116: 
117:         return response
118: 
119:     def reset(self) -> None:
120:         """Reset conversation state (start a new conversation)."""
121:         self._metadata = None
122: 
123:     @property
124:     def conversation_id(self) -> str | None:
125:         """Get the current conversation ID, if in a multi-turn conversation."""
126:         if self._metadata:
127:             return self._metadata.cid
128:         return None
`

## 4. diag_argon_levels.py, runner header, _raise_if_prompt_escaped, validate_step_b
`python
# C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch\diag_argon_levels.py
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from gemini_web_mcp_cli.core.client import GeminiClient
from gemini_web_mcp_cli.services.chat import ChatService
from gemini_web_mcp_cli.services.limits import LimitsService

SCRATCH = Path(
    r"C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch"
)


async def check_qoun_chat_and_test() -> None:
    client = GeminiClient(profile_name="qoun", timeout=300.0)
    await client.init()
    try:
        # 1. Check if c_1ea2e77b2066f070 saved any answer via hNvQHb
        try:
            payload = json.dumps(["c_1ea2e77b2066f070", 10, None, 1, [1], [4], None, 1])
            res = await client.execute_rpc_with_browser_cookies("hNvQHb", payload=payload)
            raw_len = len(str(res[0].data)) if res else 0
            print(f"[qoun read c_1ea2e77b2066f070] len={raw_len} preview={str(res[0].data)[:300] if res else None}")
        except Exception as exc:
            print(f"[qoun read c_1ea2e77b2066f070] err={exc}")

        # 2. Test Batch 7 Part 3 with gemini-4-argon thinking_level="medium"
        prompt = (SCRATCH / "s002_a139_152_demos_prompt_part3_clean.txt").read_text(encoding="utf-8")
        chat = ChatService(client)
        t0 = time.monotonic()
        try:
            resp = await chat.send(prompt, model="gemini-4-argon", thinking_level="medium")
            dt = time.monotonic() - t0
            print(
                f"[qoun argon medium B7p3] OK in {dt:.1f}s chars={len(resp.text or '')} "
                f"thoughts={len(resp.thoughts or '')} hash={resp.server_model_hash} cid={resp.metadata.cid if resp.metadata else None}"
            )
            (SCRATCH / "s002_a139_152_demos_part3_raw_medium.txt").write_text(resp.text or "", encoding="utf-8")
        except Exception as exc:
            print(f"[qoun argon medium B7p3] ERR after {time.monotonic() - t0:.1f}s: {type(exc).__name__}: {exc}")
    finally:
        await client.close()


async def check_niyyah() -> None:
    client = GeminiClient(profile_name="niyyah", timeout=300.0)
    await client.init()
    try:
        ls = LimitsService(client)
        lim = await ls.get_limits()
        pro = [(q.name, q.used, q.remaining) for q in lim if "Pro" in q.name or "Thinking" in q.name]
        print(f"[niyyah limits] count={len(lim)} pro={pro}")

        chat = ChatService(client)
        for lvl in ("medium", "high"):
            t0 = time.monotonic()
            try:
                resp = await chat.send("Reply strictly with PONG.", model="gemini-4-argon", thinking_level=lvl)
                dt = time.monotonic() - t0
                print(
                    f"[niyyah argon {lvl} PONG] OK in {dt:.1f}s reply={resp.text!r} "
                    f"thoughts={len(resp.thoughts or '')} hash={resp.server_model_hash} cid={resp.metadata.cid if resp.metadata else None}"
                )
            except Exception as exc:
                print(f"[niyyah argon {lvl} PONG] ERR after {time.monotonic() - t0:.1f}s: {type(exc).__name__}: {exc}")
            chat.reset()
    finally:
        await client.close()


async def main() -> None:
    await asyncio.gather(check_qoun_chat_and_test(), check_niyyah())


if __name__ == "__main__":
    asyncio.run(main())


# C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch\diag_argon_levels.py
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from gemini_web_mcp_cli.core.client import GeminiClient
from gemini_web_mcp_cli.services.chat import ChatService
from gemini_web_mcp_cli.services.limits import LimitsService

SCRATCH = Path(
    r"C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch"
)


async def check_qoun_chat_and_test() -> None:
    client = GeminiClient(profile_name="qoun", timeout=300.0)
    await client.init()
    try:
        # 1. Check if c_1ea2e77b2066f070 saved any answer via hNvQHb
        try:
            payload = json.dumps(["c_1ea2e77b2066f070", 10, None, 1, [1], [4], None, 1])
            res = await client.execute_rpc_with_browser_cookies("hNvQHb", payload=payload)
            raw_len = len(str(res[0].data)) if res else 0
            print(f"[qoun read c_1ea2e77b2066f070] len={raw_len} preview={str(res[0].data)[:300] if res else None}")
        except Exception as exc:
            print(f"[qoun read c_1ea2e77b2066f070] err={exc}")

        # 2. Test Batch 7 Part 3 with gemini-4-argon thinking_level="medium"
        prompt = (SCRATCH / "s002_a139_152_demos_prompt_part3_clean.txt").read_text(encoding="utf-8")
        chat = ChatService(client)
        t0 = time.monotonic()
        try:
            resp = await chat.send(prompt, model="gemini-4-argon", thinking_level="medium")
            dt = time.monotonic() - t0
            print(
                f"[qoun argon medium B7p3] OK in {dt:.1f}s chars={len(resp.text or '')} "
                f"thoughts={len(resp.thoughts or '')} hash={resp.server_model_hash} cid={resp.metadata.cid if resp.metadata else None}"
            )
            (SCRATCH / "s002_a139_152_demos_part3_raw_medium.txt").write_text(resp.text or "", encoding="utf-8")
        except Exception as exc:
            print(f"[qoun argon medium B7p3] ERR after {time.monotonic() - t0:.1f}s: {type(exc).__name__}: {exc}")
    finally:
        await client.close()


async def check_niyyah() -> None:
    client = GeminiClient(profile_name="niyyah", timeout=300.0)
    await client.init()
    try:
        ls = LimitsService(client)
        lim = await ls.get_limits()
        pro = [(q.name, q.used, q.remaining) for q in lim if "Pro" in q.name or "Thinking" in q.name]
        print(f"[niyyah limits] count={len(lim)} pro={pro}")

        chat = ChatService(client)
        for lvl in ("medium", "high"):
            t0 = time.monotonic()
            try:
                resp = await chat.send("Reply strictly with PONG.", model="gemini-4-argon", thinking_level=lvl)
                dt = time.monotonic() - t0
                print(
                    f"[niyyah argon {lvl} PONG] OK in {dt:.1f}s reply={resp.text!r} "
                    f"thoughts={len(resp.thoughts or '')} hash={resp.server_model_hash} cid={resp.metadata.cid if resp.metadata else None}"
                )
            except Exception as exc:
                print(f"[niyyah argon {lvl} PONG] ERR after {time.monotonic() - t0:.1f}s: {type(exc).__name__}: {exc}")
            chat.reset()
    finally:
        await client.close()


async def main() -> None:
    await asyncio.gather(check_qoun_chat_and_test(), check_niyyah())


if __name__ == "__main__":
    asyncio.run(main())


# surah2_parallel_runner.py (Header before STATUS_STATE)
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

SCRATCH = Path(
    r"C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch"
)
if str(SCRATCH) not in sys.path:
    sys.path.insert(0, str(SCRATCH))

import waqf_batch_utils as u  # noqa: E402
from gemini_web_mcp_cli.core.client import GeminiClient  # noqa: E402
from gemini_web_mcp_cli.core.constants import RPC  # noqa: E402
from gemini_web_mcp_cli.core.exceptions import (  # noqa: E402
    APIError,
    GeminiReplyError,
    TimeoutError as GeminiTimeoutError,
)
from gemini_web_mcp_cli.services.chat import ChatService  # noqa: E402
from gemini_web_mcp_cli.services.limits import LimitsService  # noqa: E402

REMAINING_BATCHES_8_18: list[tuple[str, int, int]] = [
    ("s002_a189_195", 189, 195),  # 7 ayahs (ideal 1-batch slot for smallbusiness)
    ("s002_a153_167", 153, 167),  # 15 ayahs
    ("s002_a204_215", 204, 215),  # 12 ayahs
    ("s002_a178_188", 178, 188),  # 11 ayahs
    ("s002_a235_245", 235, 245),  # 11 ayahs
    ("s002_a168_177", 168, 177),  # 10 ayahs
    ("s002_a216_225", 216, 225),  # 10 ayahs
    ("s002_a255_264", 255, 264),  # 10 ayahs
    ("s002_a265_274", 265, 274),  # 10 ayahs
    ("s002_a226_234", 226, 234),  # 9 ayahs
    ("s002_a246_254", 246, 254),  # 9 ayahs
]

BATCH_RANGE_MAP = {bid: (a, b) for bid, a, b in REMAINING_BATCHES_8_18}

# Healthy 4 Argon High profiles verified by live probe:
# - `smallbusiness` has ~461 Pro/Thinking quota remaining (~4 turns) -> capped at 1 small batch (`s002_a189_195`)
# - `default`, `abod`, `qoun` have 2000+ quota remaining -> dynamically pull remaining batches from shared queue
# - `niyyah` repeatedly failed/downgraded on 4 Argon High (`I encountered an error` / `high demand`, 0 thoughts)
DEFAULT_PROFILES_4: list[str] = ["default", "abod", "qoun", "smallbusiness"]

STATUS_LOCK = asyncio.Lock()
VALIDATE_LOCK = asyncio.Lock()
STATUS_FILE = SCRATCH / "surah2_parallel_status.json"


# token_factory.py (L1000-L1225: _raise_if_prompt_escaped & helpers)
1001:             logger.debug("Token Factory: no 'Sign in' button found")
1002:             return None
1003: 
1004:         # Monitor the redirect chain (max ~30s)
1005:         for attempt in range(15):
1006:             time.sleep(2)
1007:             try:
1008:                 url = run_js(ws, "window.location.href") or ""
1009:             except Exception:
1010:                 continue
1011: 
1012:             # Success: back on Gemini with valid session. The signed-out page
1013:             # also carries an SNlM0e, so require the account email (oPEP7c) —
1014:             # otherwise the first poll "succeeds" before the redirect happens.
1015:             if "gemini.google.com/app" in url:
1016:                 signed_in_email = run_js(
1017:                     ws, "window.WIZ_global_data?.oPEP7c || ''"
1018:                 )
1019:                 snlm0e = run_js(
1020:                     ws, "window.WIZ_global_data?.SNlM0e || ''"
1021:                 ) if signed_in_email else ""
1022:                 if snlm0e:
1023:                     logger.info(
1024:                         f"Token Factory: auto sign-in succeeded "
1025:                         f"(SNlM0e {len(snlm0e)} chars)"
1026:                     )
1027:                     # Save fresh cookies to auth state on disk
1028:                     try:
1029:                         cookies_list = get_page_cookies(ws)
1030:                         cookies = _filter_gemini_cookies(cookies_list)
1031:                         if cookies.get("__Secure-1PSID"):
1032:                             from .auth import AuthManager
1033:                             from .profiles import ProfileManager
1034: 
1035:                             pm = ProfileManager()
1036:                             am = AuthManager(
1037:                                 profile_manager=pm,
1038:                                 profile_name=self._profile_name,
1039:                             )
1040:                             am.load()
1041:                             am.state.cookies = cookies
1042:                             am.state.tokens.snlm0e = snlm0e
1043:                             am.state.last_refreshed = time.time()
1044:                             am.save()
1045:                             logger.debug(
1046:                                 "Token Factory: saved fresh auth state to disk"
1047:                             )
1048:                     except Exception as e:
1049:                         logger.debug(f"Token Factory: save auth state failed: {e}")
1050:                     return snlm0e
1051:                 # Page loaded but no SNlM0e yet — keep waiting
1052:                 continue
1053: 
1054:             # Google account chooser — auto-select first account
1055:             if "accounts.google.com" in url:
1056:                 try:
1057:                     page_text = (
1058:                         run_js(ws, "document.body.innerText.substring(0, 500)")
1059:                         or ""
1060:                     )
1061:                 except Exception:
1062:                     page_text = ""
1063: 
1064:                 if "password" in page_text.lower():
1065:                     logger.warning(
1066:                         "Token Factory: auto sign-in hit password page — "
1067:                         "can't auto-complete"
1068:                     )
1069:                     return None
1070: 
1071:                 # Google identifier page — headless profiles may have auth
1072:                 # cookies on disk but no browser-level saved account chooser.
1073:                 if auth_email:
1074:                     submitted_email = run_js(ws, f"""
1075:                         (() => {{
1076:                             const input = document.querySelector('input[type="email"]')
1077:                                 || document.querySelector('input#identifierId')
1078:                                 || document.querySelector('input[name="identifier"]');
1079:                             if (!input) return false;
1080: 
1081:                             input.focus();
1082:                             input.value = {auth_email!r};
1083:                             input.dispatchEvent(new Event('input', {{ bubbles: true }}));
1084:                             input.dispatchEvent(new Event('change', {{ bubbles: true }}));
1085: 
1086:                             const buttons = Array.from(document.querySelectorAll(
1087:                                 'button, div[role="button"]'
1088:                             ));
1089:                             const next = buttons.find((el) =>
1090:                                 el.textContent.trim().toLowerCase() === 'next'
1091:                             ) || document.querySelector('#identifierNext button')
1092:                               || document.querySelector('#identifierNext');
1093:                             if (!next) return false;
1094:                             next.click();
1095:                             return true;
1096:                         }})()
1097:                     """)
1098:                     if submitted_email:
1099:                         logger.debug(
1100:                             "Token Factory: submitted saved email on "
1101:                             "Google identifier page"
1102:                         )
1103:                         continue
1104: 
1105:                 # Try clicking the first account in the chooser
1106:                 run_js(ws, """
1107:                     (() => {
1108:                         const selectors = [
1109:                             '[data-identifier]',
1110:                             '[data-email]',
1111:                             'li[data-authuser]',
1112:                             'div[data-authuser]',
1113:                         ];
1114:                         for (const sel of selectors) {
1115:                             const el = document.querySelector(sel);
1116:                             if (el) { el.click(); return; }
1117:                         }
1118:                     })()
1119:                 """)
1120:                 continue
1121: 
1122:         logger.warning("Token Factory: auto sign-in timed out")
1123:         return None
1124: 
1125:     def _load_auth_state(self):
1126:         """Load saved auth state for the active Token Factory profile."""
1127:         try:
1128:             from .auth import AuthManager
1129:             from .profiles import ProfileManager
1130: 
1131:             pm = ProfileManager()
1132:             am = AuthManager(profile_manager=pm, profile_name=self._profile_name)
1133:             return am.load()
1134:         except Exception as e:
1135:             logger.debug(f"Token Factory: could not load auth state: {e}")
1136:             return None
1137: 
1138:     def _load_auth_email(self) -> str:
1139:         """Load the saved profile email for Google identifier-page sign-in."""
1140:         state = self._load_auth_state()
1141:         return state.email.strip() if state else ""
1142: 
1143:     def _activate_tool(self, tool_id: int) -> str:
1144:         """Activate a tool (Images/Videos/Music) in Chrome's Gemini UI.
1145: 
1146:         Opens the Tools drawer and clicks the corresponding tool toggle.
1147:         This ensures Chrome's BotGuard-signed request body includes the
1148:         tool activation, making generation deterministic.
1149: 
1150:         Args:
1151:             tool_id: Tool ID (14=Images, 11=Videos, 21=Music)
1152: 
1153:         Returns:
1154:             Raw activation result: 'activated', 'already_active', 'disabled'
1155:             (usage limit), 'not_found', 'no_drawer', or 'error'.
1156:         """
1157:         aliases = TOOL_ID_UI_ALIASES.get(tool_id)
1158:         if not aliases:
1159:             logger.debug(f"Token Factory: unknown tool_id {tool_id}, skipping activation")
1160:             return "unsupported"
1161: 
1162:         js = ACTIVATE_TOOL_JS.format(tool_names_json=json.dumps(list(aliases)))
1163:         result = run_js(self._ws_url, js) or "error"
1164: 
1165:         if result in ("activated", "already_active"):
1166:             logger.debug(f"Token Factory: tool '{aliases[0]}' {result}")
1167:             # Give the UI a moment to update placeholder/state
1168:             if result == "activated":
1169:                 time.sleep(0.5)
1170:             return result
1171: 
1172:         if result == "disabled":
1173:             logger.warning(
1174:                 f"Token Factory: tool '{aliases[0]}' is disabled for this account "
1175:                 "(usage limit reached)"
1176:             )
1177:         else:
1178:             logger.warning(
1179:                 f"Token Factory: failed to activate tool '{aliases[0]}' "
1180:                 f"(result: {result})"
1181:             )
1182:         return result
1183: 
1184:     def _set_template(self, template_name: str) -> bool:
1185:         """Select a template card on a Create videos / Create music page.
1186: 
1187:         Templates prefill the style (the captured body carries a template
1188:         descriptor at inner[0][9]); a custom prompt and options still apply.
1189: 
1190:         Best effort — returns False when the card is not found (the generation
1191:         then proceeds as a regular prompt).
1192:         """
1193:         name = (template_name or "").strip()
1194:         if not name:
1195:             return False
1196: 
1197:         # Escape single quotes so the name can be embedded in the JS call
1198:         escaped = name.replace("\\", "\\\\").replace("'", "\\'")
1199:         js = SELECT_TEMPLATE_JS.replace("{template_name}", escaped)
1200:         result = run_js(self._ws_url, js)
1201: 
1202:         if result in ("selected", "clicked"):
1203:             logger.debug(f"Token Factory: template '{name}' {result}")
1204:             time.sleep(0.5)
1205:             return True
1206: 
1207:         logger.warning(
1208:             f"Token Factory: template '{name}' not found "
1209:             f"(result: {result})"
1210:         )
1211:         return False
1212: 
1213:     def _set_aspect_ratio(self, label: str) -> bool:
1214:         """Pick an aspect-ratio option in Chrome's composer dropdown.
1215: 
1216:         Used for both video orientation ("Landscape (16:9)") and image aspect
1217:         ("1:1", "16:9", ...). Chrome encodes the pick in inner[55] and
1218:         inner[0][9]; driving the UI keeps the signed body consistent.
1219:         """
1220:         if not label:
1221:             return False
1222:         js = SELECT_COMPANION_OPTION_JS.format(
1223:             mode="aspect", control="Aspect ratio", label=label
1224:         )
1225:         result = run_js(self._ws_url, js)
1226:         if result in ("selected", "already_active"):

# waqf_batch_utils.py:validate_step_b
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
                
`