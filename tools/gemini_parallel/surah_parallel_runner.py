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
from gemini_web_mcp_cli.services.chat import ChatService  # noqa: E402
from gemini_web_mcp_cli.services.limits import LimitsService  # noqa: E402

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
DEFAULT_PROFILES_4: list[str] = ["default", "qoun", "abod", "smallbusiness", "niyyah"]

STATUS_LOCK = asyncio.Lock()
VALIDATE_LOCK = asyncio.Lock()
EVENTS_LOCK = asyncio.Lock()
QUOTAS_LOCK = asyncio.Lock()
STATUS_FILE = SCRATCH / "surah6_parallel_status.json"
EVENTS_FILE = SCRATCH / "timing_events.jsonl"
QUOTAS_LIVE_FILE = SCRATCH / "quotas_live.json"
STATUS_STATE: dict[str, dict[str, Any]] = {}
PROGRESS: dict[str, int] = {}
FAILED_ON: dict[str, set[str]] = {}
LAST_END: dict[str, float] = {}
STEP_A_SECONDS: dict[str, float] = {}
ALIVE_WORKERS: set[str] = set()


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
        cr = int(cap.get("retries") or 0)
        cw = float(cap.get("wasted_retry_s") or 0.0)
        sub = [f"nav={cap.get('nav_wait_s', 0):.1f}", f"pick={cap.get('picker_s', 0):.1f}"]
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


def log(msg: str) -> None:
    ts = fmt_12h()
    print(f"[{ts}] {msg}", flush=True)


async def update_status(batch_id: str, **fields: Any) -> None:
    async with STATUS_LOCK:
        if not STATUS_STATE and STATUS_FILE.exists():
            try:
                loaded = json.loads(STATUS_FILE.read_text(encoding="utf-8-sig"))
                if isinstance(loaded, dict):
                    if "batches" in loaded and isinstance(loaded["batches"], dict):
                        STATUS_STATE.update(loaded["batches"])
                    else:
                        STATUS_STATE.update(loaded)
            except Exception:
                pass
        now_dt = datetime.now().astimezone()
        entry = STATUS_STATE.setdefault(batch_id, {})
        entry.update(fields)
        entry["updatedAt"] = now_dt.isoformat(timespec="seconds")
        entry["updatedAt_12h"] = fmt_12h(now_dt)
        doc = {
            "surah": SURAH_NUM,
            "surah_name_ar": SURAH_NAME_AR,
            "updatedAt": now_dt.isoformat(timespec="seconds"),
            "updatedAt_12h": fmt_iso_to_12h(now_dt.isoformat(timespec="seconds"), include_date=True),
            "batches": STATUS_STATE,
        }
        STATUS_FILE.write_text(
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
        merged = {
            **prev,
            "profile": profile,
            **{k: v for k, v in fields.items() if v is not None or k not in prev},
            "lastSeenAt": now_dt.isoformat(timespec="seconds"),
            "lastSeenAt_12h": fmt_12h(now_dt),
        }
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


def build_step_a_prompt(batch_id: str, start_ayah: int, end_ayah: int, input_text: str) -> str:
    return (
        "أنت خبير متمرس في علم الوقف والابتداء، والنحو القرآني، والقراءات القرآنية، وتحقيق كتب أئمة الوقف الخمسة:\n"
        "1. السجاوندي (علل الوقوف)\n"
        "2. الداني (المكتفى في الوقف والابتداء)\n"
        "3. ابن الأنباري (إيضاح الوقف والابتداء)\n"
        "4. الأشموني (منار الهدى في بيان الوقف والابتداء)\n"
        "5. النحاس (القطع والائتناف)\n\n"
        f"المهمة (المرحلة الأولى - الاستخراج الموحد للدفعة `{batch_id}`: سورة {SURAH_NAME_AR} `surah: {SURAH_NUM}`، الآيات `{start_ayah}` إلى `{end_ayah}`):\n"
        "اقرأ ملف الإدخال JSON أدناه الذي يضم:\n"
        "- `ayahWordsCompact`: جدول الكلمات القرآنية المرقمة بدقة (`wordIndex:كلمة_عثمانية` مع وسوم `[مصحف]` و`[رأس آية]`).\n"
        "- `jamharahSections`: نصوص الأئمة الأربعة (`السجاوندي`, `الداني`, `ابن الأنباري`, `الأشموني`).\n"
        "- `nahhasEntries`: نصوص الإمام `النحاس`.\n"
        "- `boundaryContext`: كلمات ومقاطع الحدود المجاورة (`prevWordsCompact`, `nextWordsCompact`, `prevSections`, `nextSections`, `prevNahhasEntries`, `nextNahhasEntries`).\n\n"
        "استخرج **100%** من جميع مواضع الوقف التي حكم عليها كل إمام في الآيات المطلوبة وفق المخطط التالي بالضبط:\n"
        "```json\n"
        "{\n"
        f'  "surah": {SURAH_NUM},\n'
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
    ext_data: dict[str, Any], include_comments: bool = False
) -> list[dict[str, Any]]:
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
        if x.get("surah") and int(x["surah"]) != SURAH_NUM:
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
    for _retry in range(3):
        vinfo["rpc_calls"] += 1
        try:
            res = await client.execute_rpc_with_browser_cookies(
                RPC.READ_CHAT, json.dumps([cid, 25, None, 1, [0], [4], None, 1])
            )
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
                    '\"4 argon high\"',
                    '"gemini-4-argon"',
                    '\"gemini-4-argon\"',
                )
                if m in low_t
            ),
            None,
        )
        if not matched_marker:
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
    if send_timeout_s is None:
        send_timeout_s = 800.0 if label.startswith("Step A") else 480.0
    turns_log = SCRATCH / "turns.jsonl"

    first_exc: Exception | None = None
    last_exc: Exception | None = None
    attempt_excs: list[Exception] = []
    for attempt in range(1, max_attempts + 1):
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

        vinfo: dict[str, Any] = {}
        bstats_turn_recorded = False
        sleep_s = 0.0
        try:
            try:
                resp = await asyncio.wait_for(
                    chat.send(prompt, model="gemini-4-argon", thinking_level="high"),
                    timeout=send_timeout_s,
                )
            except TimeoutError as timeout_exc:
                raise TimeoutError(f"chat.send timed out after {send_timeout_s:.0f}s") from timeout_exc
            t_send_done = time.monotonic()

            ver_failed = False
            ver_err_detail = ""
            t_v0 = time.monotonic()
            try:
                ok_high, why, vinfo = await verify_argon_high_turn(client, resp)
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

            PROGRESS[batch_id] = PROGRESS.get(batch_id, 0) + 1
            if bstats is not None:
                bstats["turns_ok"] += 1
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
            no_retry = (
                isinstance(exc, (HighDowngradeError, VerifyReadbackError, TokenFactoryError))
                or type(exc).__name__ in ("AuthError", "UsageLimitExceeded", "TokenFactoryError")
            )
            will_retry = (not no_retry) and attempt < max_attempts
            sleep_s = float(5 * (2 ** (attempt - 1))) if will_retry else 0.0
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

            rec_kw: dict[str, Any] = {
                "outcome": type(exc).__name__,
                "prompt_chars": len(prompt),
                "secs": round(dt, 1),
                "retry_sleep_s": sleep_s,
                "is_wasted": True,
                "err": str(exc)[:180],
                "timing": turn_t,
            }
            if isinstance(exc, VerifyReadbackError):
                rec_kw["verify"] = "readback_failed"
            _rec(**rec_kw)
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
            ok, msg = u.validate_candidate_file(batch_id, start_ayah, end_ayah, final_out, apply_to_feed=False, surah=SURAH_NUM)
        bstats["validate_s"] += time.monotonic() - t_v0
        if ok:
            dt_b = round(time.monotonic() - t_batch0, 3)
            log(f"[{profile}][{batch_id}] SKIP already complete & valid in {dt_b:.2f}s: {final_out.name}")
            await update_status(batch_id, profile=profile, stage="done_cached", valid=True, total_s=dt_b)
            await record_event("batch_done", surah=SURAH_NUM, batch=batch_id, profile=profile, ok=True, cached=True, total_s=dt_b)
            return True, "cached"

    inp_path = u.PROTO / f"{batch_id}_input.json"
    input_text = inp_path.read_text(encoding="utf-8")
    input_data = json.loads(input_text)

    chat = ChatService(client)
    ext_path = SCRATCH / f"{batch_id}_extract_only.json"
    ext_data: dict[str, Any] | None = None
    step_a_from_chat = False

    if ext_path.exists():
        try:
            cand = json.loads(ext_path.read_text(encoding="utf-8"))
            t_v0 = time.monotonic()
            errs, warns = u.validate_step_a(
                cand, SURAH_NUM, start_ayah, end_ayah, input_data, wl_cache, mw_cache, strict_in_range=True
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
        t_sa0 = time.monotonic()
        await update_status(batch_id, profile=profile, stage="step_a")
        prompt_a = build_step_a_prompt(batch_id, start_ayah, end_ayah, input_text)
        (SCRATCH / f"{batch_id}_stepA_prompt.txt").write_text(prompt_a, encoding="utf-8")

        resp_a = await send_with_retry(profile, batch_id, client, chat, prompt_a, "Step A", bstats=bstats)
        (SCRATCH / f"{batch_id}_stepA_raw.txt").write_text(resp_a.text or "", encoding="utf-8")
        step_a_from_chat = True

        for fix_round in range(1, 4):
            try:
                cand = u.extract_json_value(resp_a.text or "")
                t_v0 = time.monotonic()
                errs, warns = u.validate_step_a(
                    cand, SURAH_NUM, start_ayah, end_ayah, input_data, wl_cache, mw_cache, strict_in_range=True
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
                            cand2, SURAH_NUM, start_ayah, end_ayah, input_data, wl_cache, mw_cache, strict_in_range=True
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
    miss, brok, valid_map = u.validate_step_b(ext_data, collected_items, wl_cache, mw_cache, default_surah=SURAH_NUM)
    bstats["validate_s"] += time.monotonic() - t_v0

    perm_comment_map = {
        (
            int(it.get("surah") or SURAH_NUM),
            int(it["ayah"]),
            int(it["wordIndex"]),
            str(it["scholar"]),
        ): it.get("comment", "")
        for it in collect_permissive_items(ext_data, include_comments=True)
    }

    if miss:
        miss_keys = {
            (
                int(m.get("surah") or SURAH_NUM),
                int(m["ayah"]),
                int(m["wordIndex"]),
                str(m["scholar"]),
            )
            for m in miss
        }
        permissive_all = collect_permissive_items(ext_data, include_comments=False)
        permissive = [
            it
            for it in permissive_all
            if (
                int(it.get("surah") or SURAH_NUM),
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
            is_chunk1_same_chat = step_a_from_chat and ci == 1
            first_max_attempts = 1 if is_chunk1_same_chat else 3
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
                if is_chunk1_same_chat:
                    if _is_chunk1_no_fallback_error(exc):
                        raise
                elif (not step_a_from_chat) or _is_no_standalone_retry_error(exc):
                    raise
                log(
                    f"[{profile}][{batch_id}] Step B c{ci} same-chat failed ({exc}); "
                    "falling back to fresh standalone Step B chat"
                )
                chat = ChatService(client)
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
        miss, brok, valid_map = u.validate_step_b(ext_data, collected_items, wl_cache, mw_cache, default_surah=SURAH_NUM)
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
                bstats=bstats,
            )
        except Exception as exc:
            if (not was_existing_chat) or _is_no_standalone_retry_error(exc):
                raise
            log(f"[{profile}][{batch_id}] Step B repair #{rep_round} error ({exc}); resetting to fresh standalone chat")
            chat = ChatService(client)
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
        miss, brok, valid_map = u.validate_step_b(ext_data, collected_items, wl_cache, mw_cache, default_surah=SURAH_NUM)
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
            "batch_done", surah=SURAH_NUM, batch=batch_id, profile=profile, ok=False, total_s=dt_b,
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

    candidate = u.assemble_candidate_output(ext_data, valid_map, default_surah=SURAH_NUM)
    final_out.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    t_v0 = time.monotonic()
    async with VALIDATE_LOCK:
        ok, msg = u.validate_candidate_file(batch_id, start_ayah, end_ayah, final_out, apply_to_feed=False, surah=SURAH_NUM)
    bstats["validate_s"] += time.monotonic() - t_v0

    dt_b = round(time.monotonic() - t_batch0, 2)
    tot_wasted = round(bstats["wasted_fail_s"] + bstats["wasted_sleep_s"] + bstats["capture_wasted_s"], 2)
    # Compute token & cost estimates from turns.jsonl for this batch
    telem_map = compute_surah_turn_ledger(SURAH_NUM)
    bt = telem_map.get(batch_id) or {}
    est_quota_cr = int(bt.get("quota_credits_used") or ((bstats["turns_ok"] + bstats["turns_fail"]) * CREDITS_PER_ARGON_HIGH_TURN))
    est_tokens = int(bt.get("total_tokens") or 0)
    est_cost = float(bt.get("cost_usd") or 0.0)
    await update_status(
        batch_id,
        profile=profile,
        stage="validated_ready" if ok else "failed_validate",
        valid=ok,
        extractionsCount=len(candidate.get("extractions", [])),
        permissiveDemosCount=len(valid_map),
        total_s=dt_b,
        step_a_s=bstats["step_a_s"],
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
        "batch_done", surah=SURAH_NUM, batch=batch_id, profile=profile, ok=ok, cached=False, total_s=dt_b,
        step_a_s=bstats["step_a_s"], step_b_s=bstats["step_b_s"], validate_s=round(bstats["validate_s"], 2),
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
        f"(A={bstats['step_a_s']:.0f}s B={bstats['step_b_s']:.0f}s val={bstats['validate_s']:.2f}s | "
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
                if client.auth_manager.state.chrome_profile_path:
                    await asyncio.to_thread(
                        start_on_demand,
                        client.auth_manager.resolved_profile_name,
                        client.auth_manager.state.chrome_profile_path,
                    )
                daemon_start_s = round(time.monotonic() - t_d1, 3)

            port = pq.find_profile_daemon_port(profile, client)
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


async def get_pro_quota_rich(client: GeminiClient) -> dict[str, Any]:
    """Return rich quota dict (including reset_in_s and reset_at) for Thinking/Pro pool."""
    import probe_profile_quotas as pq

    t0 = time.monotonic()
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
            return {
                "remaining": rem,
                "limit": limit,
                "used_pct": used_pct,
                "left_pct": left_pct,
                "reset_in_s": reset_in_s,
                "reset_in_human": pq.fmt_duration(reset_in_s),
                "reset_at": reset_at,
                "name": str(q.name),
                "elapsed_s": round(time.monotonic() - t0, 3),
                "rpc_error": None,
            }
    except Exception as exc:
        return {
            "remaining": None,
            "limit": None,
            "used_pct": None,
            "left_pct": None,
            "reset_in_s": None,
            "reset_in_human": "—",
            "reset_at": None,
            "name": None,
            "elapsed_s": round(time.monotonic() - t0, 3),
            "rpc_error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "remaining": None,
        "limit": None,
        "used_pct": None,
        "left_pct": None,
        "reset_in_s": None,
        "reset_in_human": "—",
        "reset_at": None,
        "name": None,
        "elapsed_s": round(time.monotonic() - t0, 3),
        "rpc_error": None,
    }


async def get_pro_quota(client: GeminiClient) -> tuple[int | None, int | None, str | None, float]:
    """Return (remaining, plan_limit, feature_name, elapsed_s) for Thinking/Pro pool."""
    q = await get_pro_quota_rich(client)
    return q["remaining"], q["limit"], q["name"], q["elapsed_s"]


async def get_pro_remaining(client: GeminiClient) -> tuple[int | None, float]:
    rem, _limit, _name, dt = await get_pro_quota(client)
    return rem, dt


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
) -> None:
    global IN_FLIGHT_BATCHES
    client: GeminiClient | None = None
    done_count = 0
    faults = 0
    t_worker0 = time.monotonic()
    quota_total_s = 0.0
    idle_wait_s = 0.0
    with logger.contextualize(profile=profile):
        try:
            ALIVE_WORKERS.add(profile)
            try:
                client, launch_info = await init_client_with_retry(profile, stagger_s=worker_idx * 0.8)
                cap_info = launch_info.get("cap_info") or {}
                argon_ok = cap_info.get("argon_high_ok")
                q0 = await get_pro_quota_rich(client)
                rem0, lim0, qname0, q0_s = q0["remaining"], q0["limit"], q0["name"], q0["elapsed_s"]
                reset0_human = q0.get("reset_in_human") or "—"
                reset0_at = q0.get("reset_at")
                quota_total_s += q0_s
                launch_total_s = round(time.monotonic() - t_worker0, 3)
                qlabel = qname0 or "Thinking/Pro"
                lim_s = lim0 if lim0 is not None else "?"
                reset_str = f" reset_in={reset0_human}" if reset0_human != "—" else ""
                tier_str = (
                    "PRO(4 Argon High)"
                    if argon_ok is True
                    else (f"NON-PRO({cap_info.get('picker_result')})" if argon_ok is False else "tier=unknown")
                )
                log(
                    f"[{profile}] Worker ready in {launch_total_s:.2f}s "
                    f"(stagger={launch_info['stagger_s']:.1f}s init={launch_info['client_init_s']:.2f}s "
                    f"daemon={launch_info['daemon_start_s']:.2f}s lockWait={launch_info['daemon_lock_wait_s']:.2f}s "
                    f"quota={q0_s:.2f}s tier={tier_str}) {qlabel} remaining={rem0}/{lim_s}{reset_str} max_batches={max_batches}"
                )
                await record_event(
                    "worker_launch",
                    surah=SURAH_NUM,
                    profile=profile,
                    stagger_s=launch_info["stagger_s"],
                    client_init_s=launch_info["client_init_s"],
                    client_init_detail=launch_info["client_init_detail"],
                    daemon_lock_wait_s=launch_info["daemon_lock_wait_s"],
                    daemon_start_s=launch_info["daemon_start_s"],
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

                if argon_ok is False:
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
                        f"[{profile}] Dynamic tier check: account does NOT have 4 Argon High / Pro access "
                        f"(picker={cap_info.get('picker_result')}, label={cap_info.get('picker_label')!r}); "
                        "retiring cleanly before picking any batch."
                    )
                    return

                if rem0 is not None and rem0 < min_quota_remaining:
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
                        name=qlabel,
                    )
                    log(
                        f"[{profile}] Initial quota low (remaining={rem0}/{lim_s}{reset_str} < {min_quota_remaining}); "
                        "retiring cleanly."
                    )
                    return

                await update_quota_live(
                    profile,
                    email=client.auth_manager.state.email,
                    status="ready_pro",
                    argon_high_ok=True if argon_ok is None else argon_ok,
                    tier=cap_info.get("tier") or "pro_argon_high",
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

                while True:
                    if max_batches is not None and done_count >= max_batches:
                        log(f"[{profile}] Reached max_batches={max_batches}; retiring cleanly.")
                        break

                    bid: str | None = None
                    deferred_failed_only = False
                    if dedicated_queue is not None and not dedicated_queue.empty():
                        bid = dedicated_queue.get_nowait()
                    elif not shared_queue.empty():
                        q_items: list[str] = []
                        while not shared_queue.empty():
                            q_items.append(shared_queue.get_nowait())
                        pick_idx = next(
                            (i for i, cand_bid in enumerate(q_items) if profile not in FAILED_ON.get(cand_bid, ())),
                            None,
                        )
                        if pick_idx is not None:
                            bid = q_items.pop(pick_idx)
                            for rem_bid in q_items:
                                shared_queue.put_nowait(rem_bid)
                        else:
                            other_alive = ALIVE_WORKERS - {profile}
                            other_eligible = any(
                                bool(other_alive - FAILED_ON.get(cand_bid, ())) for cand_bid in q_items
                            )
                            other_idle_available = len(other_alive) > IN_FLIGHT_BATCHES
                            if other_eligible and (other_idle_available or faults > 0):
                                for rem_bid in q_items:
                                    shared_queue.put_nowait(rem_bid)
                                deferred_failed_only = True
                            else:
                                bid = q_items.pop(0)
                                for rem_bid in q_items:
                                    shared_queue.put_nowait(rem_bid)

                    if bid is None:
                        if deferred_failed_only or IN_FLIGHT_BATCHES > 0:
                            idle_wait_s += 5.0
                            await asyncio.sleep(5.0)
                            continue
                        break

                    IN_FLIGHT_BATCHES += 1
                    try:
                        q_now = await get_pro_quota_rich(client)
                        rem, lim, qname, q_s = q_now["remaining"], q_now["limit"], q_now["name"], q_now["elapsed_s"]
                        reset_h = q_now.get("reset_in_human") or "—"
                        quota_total_s += q_s
                        if rem is not None and rem < min_quota_remaining:
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
                                name=qlabel,
                            )
                            log(
                                f"[{profile}] Quota low ({qlabel} remaining={rem}/{lim_s} reset_in={reset_h} < {min_quota_remaining}); "
                                f"returning {bid} to shared pool & retiring cleanly."
                            )
                            shared_queue.put_nowait(bid)
                            break

                        await update_quota_live(
                            profile,
                            status="active_busy",
                            current_batch=bid,
                            remaining=rem,
                            limit=lim,
                            used_pct=q_now.get("used_pct"),
                            left_pct=q_now.get("left_pct"),
                            reset_in_s=q_now.get("reset_in_s"),
                            reset_in_human=reset_h,
                            reset_at=q_now.get("reset_at"),
                            name=qname or "Thinking/Pro",
                        )
                        start_ay, end_ay = BATCH_RANGE_MAP[bid]
                        rem_log = f" (remaining={rem}/{lim} reset_in={reset_h})" if rem is not None else ""
                        log(f"[{profile}] Picked up {bid} ({start_ay}..{end_ay}){rem_log}")
                        prog_before = PROGRESS.get(bid, 0)
                        ok, info = await process_batch(profile, client, bid, start_ay, end_ay, wl_cache, mw_cache)
                        q_after = await get_pro_quota_rich(client)
                        quota_total_s += q_after["elapsed_s"]
                        measured_delta: int | None = None
                        if (
                            rem is not None
                            and q_after.get("remaining") is not None
                            and lim == q_after.get("limit")
                            and int(rem) >= int(q_after["remaining"])
                        ):
                            measured_delta = int(rem) - int(q_after["remaining"])
                        await update_status(
                            bid,
                            quota_before=rem,
                            quota_after=q_after.get("remaining"),
                            quota_limit=q_after.get("limit") or lim,
                            quota_measured_delta=measured_delta,
                        )
                        await update_quota_live(
                            profile,
                            status="ready_pro",
                            current_batch=None,
                            remaining=q_after["remaining"],
                            limit=q_after["limit"],
                            used_pct=q_after.get("used_pct"),
                            left_pct=q_after.get("left_pct"),
                            reset_in_s=q_after.get("reset_in_s"),
                            reset_in_human=q_after.get("reset_in_human"),
                            reset_at=q_after.get("reset_at"),
                        )
                        if ok:
                            results[bid] = (True, info)
                            done_count += 1
                            faults = 0
                        else:
                            # Soft failure (incomplete Step B / validate) used to park the
                            # batch forever. Requeue like the exception path so another
                            # profile can finish it.
                            log(f"[{profile}][{bid}] SOFT FAIL: {info}")
                            FAILED_ON.setdefault(bid, set()).add(profile)
                            prog_after = PROGRESS.get(bid, 0)
                            if prog_after > prog_before:
                                log(
                                    f"[{profile}][{bid}] Progress made (turns {prog_before}->{prog_after}); "
                                    f"requeueing {bid} without incrementing requeue/faults "
                                    f"(requeue={requeue_counts.get(bid, 0)}/2, faults={faults})"
                                )
                                shared_queue.put_nowait(bid)
                            else:
                                requeue_counts[bid] = requeue_counts.get(bid, 0) + 1
                                if requeue_counts[bid] <= 2:
                                    log(
                                        f"[{profile}][{bid}] Requeueing {bid} "
                                        f"(attempt {requeue_counts[bid]}/2) to shared pool after soft fail"
                                    )
                                    shared_queue.put_nowait(bid)
                                else:
                                    results[bid] = (False, f"parked after 2 requeues: {info}")
                                faults += 1
                                if faults >= 2:
                                    log(f"[{profile}] Quarantining worker after {faults} faults.")
                                    break
                    except Exception as exc:
                        if _is_terminal_worker_error(exc):
                            # Account/worker-level failure (HighDowngradeError, AuthError,
                            # UsageLimitExceeded, or /sorry/ TokenFactoryError) must NEVER
                            # increment requeue_counts[bid] or park the batch!
                            FAILED_ON.setdefault(bid, set()).add(profile)
                            await update_quota_live(
                                profile,
                                status=f"retired_{type(exc).__name__}",
                                current_batch=None,
                                last_error=f"{type(exc).__name__}: {str(exc)[:140]}",
                            )
                            log(
                                f"[{profile}][{bid}] WORKER RETIRE ({type(exc).__name__}: {exc}); "
                                f"returning {bid} to shared pool (without penalizing batch) & retiring {profile}!"
                            )
                            shared_queue.put_nowait(bid)
                            break
                        log(f"[{profile}][{bid}] UNHANDLED ERROR: {type(exc).__name__}: {exc}")
                        await update_status(batch_id=bid, profile=profile, stage="error", error=f"{type(exc).__name__}: {exc}")
                        FAILED_ON.setdefault(bid, set()).add(profile)
                        prog_after = PROGRESS.get(bid, 0)
                        if prog_after > prog_before:
                            log(
                                f"[{profile}][{bid}] Progress made (turns {prog_before}->{prog_after}); "
                                f"requeueing {bid} without incrementing requeue/faults (requeue={requeue_counts.get(bid, 0)}/2, faults={faults})"
                            )
                            shared_queue.put_nowait(bid)
                        else:
                            requeue_counts[bid] = requeue_counts.get(bid, 0) + 1
                            if requeue_counts[bid] <= 2:
                                log(f"[{profile}][{bid}] Requeueing {bid} (attempt {requeue_counts[bid]}/2) to shared pool")
                                shared_queue.put_nowait(bid)
                            else:
                                results[bid] = (False, f"parked after 2 requeues: {exc}")
                            faults += 1
                            if faults >= 2:
                                log(f"[{profile}] Quarantining worker after {faults} faults.")
                                break
                    finally:
                        IN_FLIGHT_BATCHES -= 1
            finally:
                ALIVE_WORKERS.discard(profile)
        except Exception as init_exc:
            log(f"[{profile}] Worker failed during init: {init_exc}")
            await update_quota_live(profile, status="init_error", last_error=str(init_exc)[:140])
        finally:
            worker_total_s = round(time.monotonic() - t_worker0, 2)
            log(
                f"[{profile}] Worker exiting after {worker_total_s/60:.1f}m "
                f"(batches={done_count}, faults={faults}, quota_checks={quota_total_s:.1f}s, idle_wait={idle_wait_s:.1f}s)"
            )
            await record_event(
                "worker_exit", surah=SURAH_NUM, profile=profile, total_s=worker_total_s,
                batches=done_count, faults=faults, quota_s=round(quota_total_s, 2), idle_wait_s=round(idle_wait_s, 1),
            )
            if client is not None:
                await client.close()


def _batch_input_size(batch_id: str) -> int:
    p = u.PROTO / f"{batch_id}_input.json"
    try:
        return p.stat().st_size if p.exists() else 0
    except OSError:
        return 0


async def run_queue(profiles: list[str], target_batches: list[str] | None = None, surah: int | None = None) -> int:
    global IN_FLIGHT_BATCHES
    if surah is not None:
        configure_surah(surah)
    elif target_batches:
        import re as _re
        m = _re.match(r"^s(\d+)_a(\d+)_(\d+)$", target_batches[0])
        if m:
            configure_surah(int(m.group(1)))

    IN_FLIGHT_BATCHES = 0
    PROGRESS.clear()
    FAILED_ON.clear()
    LAST_END.clear()
    STEP_A_SECONDS.clear()
    ALIVE_WORKERS.clear()

    t0 = time.monotonic()
    t_wl0 = time.monotonic()
    wl_cache, mw_cache = u.get_word_lookups((SURAH_NUM, min(114, SURAH_NUM + 1)))
    lookup_load_s = round(time.monotonic() - t_wl0, 3)
    all_batches = [b for b, _, _ in REMAINING_BATCHES_8_18 if (target_batches is None or b in target_batches)]
    if target_batches:
        for b in target_batches:
            if b not in BATCH_RANGE_MAP:
                import re as _re
                m = _re.match(rf"^s{SURAH_NUM:03d}_a(\d+)_(\d+)$", b)
                if m:
                    BATCH_RANGE_MAP[b] = (int(m.group(1)), int(m.group(2)))
                    if b not in all_batches:
                        all_batches.append(b)
    all_batches.sort(key=_batch_input_size, reverse=True)

    small_q: asyncio.Queue[str] | None = None
    shared_q: asyncio.Queue[str] = asyncio.Queue()
    requeue_counts: dict[str, int] = {}

    for b in all_batches:
        shared_q.put_nowait(b)

    ordered_summary = [f"{b}({_batch_input_size(b)}B)" for b in all_batches]
    log(
        f"Starting Surah {SURAH_NUM} ({SURAH_NAME_AR}) parallel Argon High extraction across {len(profiles)} profiles {profiles} "
        f"for {len(all_batches)} batches (largest first: {', '.join(ordered_summary)}; lookups loaded in {lookup_load_s:.2f}s)"
    )
    results: dict[str, tuple[bool, str]] = {}
    ALIVE_WORKERS.update(profiles)
    coros = [
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
        )
        for idx, prof in enumerate(profiles)
    ]

    await asyncio.gather(*coros)
    # Mark any unpicked batches as failed
    while not shared_q.empty():
        b = shared_q.get_nowait()
        results.setdefault(b, (False, "not picked up / all workers retired"))
    if small_q is not None:
        while not small_q.empty():
            b = small_q.get_nowait()
            results.setdefault(b, (False, "not picked up"))

    dt = time.monotonic() - t0
    ok_cnt = sum(1 for ok, _ in results.values() if ok)
    try:
        ledger = build_all_surahs_ledger()
        s_led = (ledger.get("surahs") or {}).get(str(SURAH_NUM)) or {}
        tot_q = s_led.get("quota_credits_used", 0)
        tot_tok = s_led.get("total_tokens", 0)
        tot_cost = s_led.get("estimated_cost_usd", 0.0)
    except Exception:
        tot_q, tot_tok, tot_cost = 0, 0, 0.0
    await record_event(
        "run_done", surah=SURAH_NUM, wall_s=round(dt, 2), lookup_load_s=lookup_load_s,
        ok=ok_cnt, total=len(all_batches), profiles=profiles,
        quota_credits_used=tot_q, total_tokens=tot_tok, estimated_cost_usd=tot_cost,
    )
    log(
        f"Finished Surah {SURAH_NUM} ({SURAH_NAME_AR}) {len(results)}/{len(all_batches)} batches in {dt/60:.1f}m: "
        f"{ok_cnt} OK, {len(all_batches) - ok_cnt} FAILED | "
        f"Surah Quota={tot_q:,}cr Tokens={tot_tok:,} Est.Cost=${tot_cost:.2f}"
    )
    for bid in all_batches:
        ok, info = results.get(bid, (False, "missing"))
        log(f"  {bid}: {'OK' if ok else 'FAIL'} ({info[:120]})")
    return 0 if ok_cnt == len(all_batches) else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generalized Parallel 4 Argon High Waqf & Ibtida Runner for any Surah (1..114)")
    p.add_argument(
        "--surah",
        type=int,
        default=6,
        help="Surah number (1..114, default: 6)",
    )
    p.add_argument(
        "--profiles",
        default=",".join(DEFAULT_PROFILES_4),
        help="Comma-separated list of candidate profiles (dynamic Argon High check filters non-Pro accounts)",
    )
    p.add_argument(
        "--batches",
        default="",
        help="Optional comma-separated subset of batch IDs",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    profs = [x.strip() for x in args.profiles.split(",") if x.strip()]
    batches = [x.strip() for x in args.batches.split(",") if x.strip()] or None
    raise SystemExit(asyncio.run(run_queue(profs, batches, surah=args.surah)))
