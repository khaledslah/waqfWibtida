## 1. Runner (from STATUS_STATE onward)
`python
# File: C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch\surah2_parallel_runner.py
STATUS_STATE: dict[str, dict[str, Any]] = {}


class HighDowngradeError(RuntimeError):
    """Raised when server downgraded from 4 Argon High or returned transient error text."""


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


async def update_status(batch_id: str, **fields: Any) -> None:
    async with STATUS_LOCK:
        entry = STATUS_STATE.setdefault(batch_id, {})
        entry.update(fields)
        entry["updatedAt"] = datetime.now().isoformat(timespec="seconds")
        STATUS_FILE.write_text(
            json.dumps(STATUS_STATE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def build_step_a_prompt(batch_id: str, start_ayah: int, end_ayah: int, input_text: str) -> str:
    return (
        "أنت خبير متمرس في علم الوقف والابتداء، والنحو القرآني، والقراءات القرآنية، وتحقيق كتب أئمة الوقف الخمسة:\n"
        "1. السجاوندي (علل الوقوف)\n"
        "2. الداني (المكتفى في الوقف والابتداء)\n"
        "3. ابن الأنباري (إيضاح الوقف والابتداء)\n"
        "4. الأشموني (منار الهدى في بيان الوقف والابتداء)\n"
        "5. النحاس (القطع والائتناف)\n\n"
        f"المهمة (المرحلة الأولى - الاستخراج الموحد للدفعة `{batch_id}`: سورة البقرة `surah: 2`، الآيات `{start_ayah}` إلى `{end_ayah}`):\n"
        "اقرأ ملف الإدخال JSON أدناه الذي يضم:\n"
        "- `ayahWordsCompact`: جدول الكلمات القرآنية المرقمة بدقة (`wordIndex:كلمة_عثمانية` مع وسوم `[مصحف]` و`[رأس آية]`).\n"
        "- `jamharahSections`: نصوص الأئمة الأربعة (`السجاوندي`, `الداني`, `ابن الأنباري`, `الأشموني`).\n"
        "- `nahhasEntries`: نصوص الإمام `النحاس`.\n"
        "- `boundaryContext`: كلمات ومقاطع الحدود المجاورة (`prevWordsCompact`, `nextWordsCompact`, `prevSections`, `nextSections`, `prevNahhasEntries`, `nextNahhasEntries`).\n\n"
        "استخرج **100%** من جميع مواضع الوقف التي حكم عليها كل إمام في الآيات المطلوبة وفق المخطط التالي بالضبط:\n"
        "```json\n"
        "{\n"
        '  "surah": 2,\n'
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
        if x.get("surah") and int(x["surah"]) != 2:
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
        "- `ibtidaSegmentWords`: `[wordIndex + 1, end]` ضمن كلمات الآية في الجدول، أو `null` عند `[رأس آية]`.\n"
        "- عنصر واحد لكل حكم غير `\"لا يوقف\"` في `verdicts` بالترتيب نفسه.\n"
        "- الحقول المسموحة فقط داخل `demosAndMeanings`: `verdict`, `isQila`, `attributedTo` (اختياري), `waqfSegmentWords`, `ibtidaSegmentWords`, `waqfDemo`, `ibtidaDemo`, `meaningAtWaqf`, `meaningAtIbtida`, `meaningIfConnected`.\n\n"
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
    )
    return any(m in t for m in markers)


async def verify_argon_high_turn(client: GeminiClient, resp: Any) -> tuple[bool, str]:
    """Verify server actually executed 4 Argon High without downgrade."""
    txt = (resp.text or "").strip()
    if _is_transient_error_reply(txt):
        return False, f"server failure reply: {txt[:120]!r}"

    thoughts_len = len(resp.thoughts or "")
    cid = resp.metadata.cid if resp.metadata else None
    rcid = resp.metadata.rcid if resp.metadata else None
    if not cid:
        if thoughts_len == 0:
            return False, "missing cid and thoughts_len=0"
        return True, f"no-cid thoughts={thoughts_len}"

    raw_txt = ""
    turn_txt = ""
    for _retry in range(2):
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
                turn_txt = matched_turn or raw_txt
                break
        except Exception:
            await asyncio.sleep(1.0)

    if turn_txt:
        low_t = turn_txt.lower()
        if "high demand" in low_t or "different model was used" in low_t:
            return False, "server downgraded due to high demand"
        has_high = any(
            marker in low_t
            for marker in (
                '"4 argon high"',
                '\\"4 argon high\\"',
                '"gemini-4-argon"',
                '\\"gemini-4-argon\\"',
            )
        )
        if not has_high:
            return False, f"missing 4 Argon High marker in hNvQHb turn (thoughts={thoughts_len})"
        return True, f"argon_high=True thoughts={thoughts_len}"

    if thoughts_len == 0:
        return False, "empty hNvQHb and thoughts_len=0"
    return True, f"hNvQHb-empty thoughts={thoughts_len}"


async def send_with_retry(
    profile: str,
    batch_id: str,
    client: GeminiClient,
    chat: ChatService,
    prompt: str,
    label: str,
    max_attempts: int = 3,
):
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        prev_meta = chat._metadata
        try:
            t0 = time.monotonic()
            resp = await chat.send(prompt, model="gemini-4-argon", thinking_level="high")
            dt = time.monotonic() - t0
            ok_high, why = await verify_argon_high_turn(client, resp)
            if not ok_high:
                raise HighDowngradeError(why)
            log(
                f"[{profile}][{batch_id}] {label} done in {dt:.1f}s "
                f"(chars={len(resp.text or '')}, {why}, cid={resp.metadata.cid if resp.metadata else None})"
            )
            return resp
        except (GeminiTimeoutError, GeminiReplyError, APIError, HighDowngradeError, Exception) as exc:
            last_exc = exc
            chat._metadata = prev_meta
            log(
                f"[{profile}][{batch_id}] {label} attempt {attempt}/{max_attempts} ERR: "
                f"{type(exc).__name__}: {exc}"
            )
            if isinstance(exc, HighDowngradeError) and "downgraded" in str(exc).lower():
                # Fast-fail downgraded account so another healthy High account can take the batch
                raise
            if attempt < max_attempts:
                await asyncio.sleep(5 * attempt)
    if isinstance(last_exc, HighDowngradeError):
        raise last_exc
    raise RuntimeError(f"[{profile}][{batch_id}] {label} failed after {max_attempts} attempts: {last_exc}")


async def process_batch(
    profile: str,
    client: GeminiClient,
    batch_id: str,
    start_ayah: int,
    end_ayah: int,
    wl_cache: dict[int, dict[tuple[int, int], dict[str, Any]]],
    mw_cache: dict[int, dict[int, int]],
) -> tuple[bool, str]:
    final_out = u.PROTO / f"{batch_id}_llm_output.json"
    if final_out.exists():
        async with VALIDATE_LOCK:
            ok, msg = u.validate_candidate_file(batch_id, start_ayah, end_ayah, final_out, apply_to_feed=False)
        if ok:
            log(f"[{profile}][{batch_id}] SKIP already complete & valid: {final_out.name}")
            await update_status(batch_id, profile=profile, stage="done_cached", valid=True)
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
            errs, warns = u.validate_step_a(
                cand, 2, start_ayah, end_ayah, input_data, wl_cache, mw_cache, strict_in_range=True
            )
            if not errs:
                ext_data = cand
                log(
                    f"[{profile}][{batch_id}] Loaded cached valid Step A "
                    f"({len(cand['extractions'])} stops, warns={len(warns)})"
                )
        except Exception:
            pass

    if ext_data is None:
        await update_status(batch_id, profile=profile, stage="step_a")
        prompt_a = build_step_a_prompt(batch_id, start_ayah, end_ayah, input_text)
        (SCRATCH / f"{batch_id}_stepA_prompt.txt").write_text(prompt_a, encoding="utf-8")

        resp_a = await send_with_retry(profile, batch_id, client, chat, prompt_a, "Step A")
        (SCRATCH / f"{batch_id}_stepA_raw.txt").write_text(resp_a.text or "", encoding="utf-8")
        step_a_from_chat = True

        for fix_round in range(1, 4):
            try:
                cand = u.extract_json_value(resp_a.text or "")
                errs, warns = u.validate_step_a(
                    cand, 2, start_ayah, end_ayah, input_data, wl_cache, mw_cache, strict_in_range=True
                )
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
                    resp_a2 = await send_with_retry(
                        profile, batch_id, client, chat, recall_prompt, "Step A recall check"
                    )
                    (SCRATCH / f"{batch_id}_stepA_recall_raw.txt").write_text(
                        resp_a2.text or "", encoding="utf-8"
                    )
                    try:
                        cand2 = u.extract_json_value(resp_a2.text or "")
                        errs2, warns2 = u.validate_step_a(
                            cand2, 2, start_ayah, end_ayah, input_data, wl_cache, mw_cache, strict_in_range=True
                        )
                        if not errs2 and len(cand2.get("extractions", [])) >= len(cand.get("extractions", [])):
                            cand = cand2
                            warns = warns2
                    except Exception:
                        pass
                ext_data = cand
                log(
                    f"[{profile}][{batch_id}] Step A validated OK: "
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
                profile, batch_id, client, chat, fix_prompt, f"Step A fix #{fix_round}"
            )
            (SCRATCH / f"{batch_id}_stepA_fix{fix_round}_raw.txt").write_text(
                resp_a.text or "", encoding="utf-8"
            )

        assert ext_data is not None
        ext_path.write_text(json.dumps(ext_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Step B: chunked in chunks of <= 38 items in SAME ChatService session if Step A ran there
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

    miss, brok, valid_map = u.validate_step_b(ext_data, collected_items, wl_cache, mw_cache)

    if not collected_items and (miss or brok):
        permissive = collect_permissive_items(ext_data, include_comments=(not step_a_from_chat))
        chunk_size = 38
        chunks = [permissive[i : i + chunk_size] for i in range(0, len(permissive), chunk_size)]
        for ci, ch in enumerate(chunks, 1):
            ch_lbl = f"جزء {ci}/{len(chunks)}" if len(chunks) > 1 else ""
            prompt_b = build_step_b_chunk_prompt(batch_id, ch, input_data, ch_lbl)
            (SCRATCH / f"{batch_id}_stepB_c{ci}_prompt.txt").write_text(prompt_b, encoding="utf-8")
            try:
                resp_b = await send_with_retry(
                    profile, batch_id, client, chat, prompt_b, f"Step B c{ci}/{len(chunks)}"
                )
            except HighDowngradeError:
                raise
            except Exception as exc:
                log(
                    f"[{profile}][{batch_id}] Step B c{ci} same-chat failed ({exc}); "
                    "falling back to fresh standalone Step B chat"
                )
                chat = ChatService(client)
                step_a_from_chat = False
                ch_with_comments = []
                # Attach comments for standalone chat
                perm_full = collect_permissive_items(ext_data, include_comments=True)
                cmap = {(it["ayah"], it["wordIndex"], it["scholar"]): it.get("comment", "") for it in perm_full}
                for it in ch:
                    it2 = dict(it)
                    it2["comment"] = cmap.get((it["ayah"], it["wordIndex"], it["scholar"]), "")
                    ch_with_comments.append(it2)
                prompt_b = build_step_b_chunk_prompt(batch_id, ch_with_comments, input_data, ch_lbl)
                resp_b = await send_with_retry(
                    profile, batch_id, client, chat, prompt_b, f"Step B c{ci}/{len(chunks)} standalone"
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

        miss, brok, valid_map = u.validate_step_b(ext_data, collected_items, wl_cache, mw_cache)
        log(f"[{profile}][{batch_id}] Step B initial: valid={len(valid_map)} missing={len(miss)} broken={len(brok)}")

    # Continuation / Repair loop (up to 7 turns, chunked <= 35 items)
    for rep_round in range(1, 8):
        if not miss and not brok:
            break
        fix_list = miss + brok
        chunk = fix_list[:35]
        is_miss_only = len(miss) == len(fix_list)
        rep_prompt = build_step_b_repair_prompt(chunk, input_data, is_miss_only)
        try:
            resp_r = await send_with_retry(
                profile,
                batch_id,
                client,
                chat,
                rep_prompt,
                f"Step B cont/repair #{rep_round} ({len(chunk)} items)",
            )
        except HighDowngradeError:
            raise
        except Exception as exc:
            log(f"[{profile}][{batch_id}] Step B repair #{rep_round} error ({exc}); resetting to fresh standalone chat")
            chat = ChatService(client)
            resp_r = await send_with_retry(
                profile,
                batch_id,
                client,
                chat,
                rep_prompt,
                f"Step B cont/repair #{rep_round} standalone ({len(chunk)} items)",
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
        miss, brok, valid_map = u.validate_step_b(ext_data, collected_items, wl_cache, mw_cache)
        log(
            f"[{profile}][{batch_id}] Step B post-repair #{rep_round}: "
            f"valid={len(valid_map)} missing={len(miss)} broken={len(brok)}"
        )

    if miss or brok:
        await update_status(
            batch_id,
            profile=profile,
            stage="failed_step_b",
            valid=len(valid_map),
            missing=len(miss),
            broken=len(brok),
        )
        return False, f"incomplete Step B: missing={len(miss)} broken={len(brok)}"

    candidate = u.assemble_candidate_output(ext_data, valid_map)
    final_out.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    async with VALIDATE_LOCK:
        ok, msg = u.validate_candidate_file(batch_id, start_ayah, end_ayah, final_out, apply_to_feed=False)
    await update_status(
        batch_id,
        profile=profile,
        stage="validated_ready" if ok else "failed_validate",
        valid=ok,
        extractionsCount=len(candidate.get("extractions", [])),
        permissiveDemosCount=len(valid_map),
    )
    if not ok:
        log(f"[{profile}][{batch_id}] FAILED llm_waqf_extractor --validate:\n{msg}")
        return False, msg
    log(
        f"[{profile}][{batch_id}] COMPLETE & VALIDATED "
        f"({len(candidate['extractions'])} stops, {len(valid_map)} demos) -> {final_out.name}"
    )
    return True, "ok"


async def init_client_with_retry(profile: str, stagger_s: float) -> GeminiClient:
    if stagger_s > 0:
        await asyncio.sleep(stagger_s)
    client = GeminiClient(profile_name=profile, timeout=900.0)
    last_exc: Exception | None = None
    for attempt in range(1, 5):
        try:
            await client.init()
            return client
        except Exception as exc:
            last_exc = exc
            log(f"[{profile}] init attempt {attempt}/4 ERR: {type(exc).__name__}: {exc}")
            await asyncio.sleep(2.5 * attempt)
    raise RuntimeError(f"[{profile}] GeminiClient.init() failed after 4 tries: {last_exc}")


async def get_pro_remaining(client: GeminiClient) -> int | None:
    try:
        lim = await LimitsService(client).get_limits()
        for q in lim:
            if "Pro" in q.name or "Thinking" in q.name:
                return int(q.remaining)
    except Exception:
        pass
    return None


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
    client = await init_client_with_retry(profile, stagger_s=worker_idx * 1.5)
    done_count = 0
    try:
        rem0 = await get_pro_remaining(client)
        log(f"[{profile}] Worker ready. Pro/Thinking remaining={rem0} max_batches={max_batches}")

        while True:
            if max_batches is not None and done_count >= max_batches:
                log(f"[{profile}] Reached max_batches={max_batches}; retiring cleanly.")
                break
            rem = await get_pro_remaining(client)
            if rem is not None and rem < min_quota_remaining:
                log(f"[{profile}] Quota low (remaining={rem} < {min_quota_remaining}); retiring cleanly.")
                break

            bid: str | None = None
            from_dedicated = False
            if dedicated_queue is not None and not dedicated_queue.empty():
                bid = dedicated_queue.get_nowait()
                from_dedicated = True
            elif not shared_queue.empty():
                bid = shared_queue.get_nowait()
            else:
                break

            start_ay, end_ay = BATCH_RANGE_MAP[bid]
            log(f"[{profile}] Picked up {bid} ({start_ay}..{end_ay})")
            try:
                ok, info = await process_batch(profile, client, bid, start_ay, end_ay, wl_cache, mw_cache)
                results[bid] = (ok, info)
                done_count += 1
            except HighDowngradeError as exc:
                if requeue_counts.get(bid, 0) < 2:
                    requeue_counts[bid] = requeue_counts.get(bid, 0) + 1
                    log(f"[{profile}][{bid}] HIGH-ONLY GUARD TRIPPED ({exc}); requeueing {bid} & retiring {profile}!")
                    shared_queue.put_nowait(bid)
                else:
                    results[bid] = (False, f"HighDowngradeError (requeue cap): {exc}")
                break
            except Exception as exc:
                log(f"[{profile}][{bid}] UNHANDLED ERROR: {type(exc).__name__}: {exc}")
                await update_status(batch_id=bid, profile=profile, stage="error", error=f"{type(exc).__name__}: {exc}")
                if from_dedicated and requeue_counts.get(bid, 0) < 2:
                    requeue_counts[bid] = requeue_counts.get(bid, 0) + 1
                    log(f"[{profile}][{bid}] Returning {bid} to shared pool for remaining healthy accounts")
                    shared_queue.put_nowait(bid)
                    break
                results[bid] = (False, str(exc))
                done_count += 1
    finally:
        await client.close()


async def run_queue(profiles: list[str], target_batches: list[str] | None = None) -> int:
    t0 = time.monotonic()
    wl_cache, mw_cache = u.get_word_lookups((2,))
    all_batches = [b for b, _, _ in REMAINING_BATCHES_8_18 if (target_batches is None or b in target_batches)]

    small_q: asyncio.Queue[str] | None = None
    shared_q: asyncio.Queue[str] = asyncio.Queue()
    requeue_counts: dict[str, int] = {}

    if "smallbusiness" in profiles and "s002_a189_195" in all_batches:
        small_q = asyncio.Queue()
        small_q.put_nowait("s002_a189_195")
        for b in all_batches:
            if b != "s002_a189_195":
                shared_q.put_nowait(b)
    else:
        for b in all_batches:
            shared_q.put_nowait(b)

    log(f"Starting parallel Argon High extraction across {len(profiles)} profiles {profiles} for {len(all_batches)} batches")
    results: dict[str, tuple[bool, str]] = {}
    coros = []
    for idx, prof in enumerate(profiles):
        if prof == "smallbusiness":
            coros.append(
                queue_worker(
                    idx,
                    prof,
                    small_q,
                    shared_q,
                    requeue_counts,
                    results,
                    wl_cache,
                    mw_cache,
                    min_quota_remaining=200,
                    max_batches=1,
                )
            )
        else:
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
                )
            )

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
    log(f"Finished {len(results)}/{len(all_batches)} batches in {dt/60:.1f}m: {ok_cnt} OK, {len(all_batches) - ok_cnt} FAILED")
    for bid in all_batches:
        ok, info = results.get(bid, (False, "missing"))
        log(f"  {bid}: {'OK' if ok else 'FAIL'} ({info[:120]})")
    return 0 if ok_cnt == len(all_batches) else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--profiles",
        default="default,abod,qoun,smallbusiness",
        help="Comma-separated list of Argon-High-verified profiles to run",
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
    raise SystemExit(asyncio.run(run_queue(profs, batches)))

`

## 2. client.py (send, _execute_browser_batch, _send_via_token_factory, _replay_process_session)
`python
181:         self,
182:         prompt: str,
183:         model: str | Model | None = None,
184:         metadata: ConversationMetadata | None = None,
185:         file_data: list | None = None,
186:         gem_id: str | None = None,
187:         tool_id: int | None = None,
188:         style_preset: dict | None = None,
189:         force_token_factory: bool = False,
190:         extended_thinking: bool | None = None,
191:         thinking_level: str | None = None,
192:         task: bool = False,
193:         video_orientation: str | None = None,
194:         template: str | None = None,
195:         image_aspect: str | None = None,
196:         music_length: str | None = None,
197:         music_vocals: str | None = None,
198:         music_genre: str | None = None,
199:     ) -> StreamResponse:
200:         """Send a chat message via StreamGenerate.
201: 
202:         Routes through Token Factory when:
203:         - Pro/Thinking models are requested (need BotGuard for model header)
204:         - tool_id is set (music tools need BotGuard token in body)
205:         - force_token_factory is True (video generation needs BotGuard)
206: 
207:         Args:
208:             tool_id: Optional tool activation ID for inner_req_list[49].
209:                      Use VIDEO_TOOL_ID (11) for video, IMAGE_TOOL_ID (14) for
210:                      image, MUSIC_TOOL_ID (21) for music generation.
211:             style_preset: Optional music style preset dict (from music_presets.py).
212:                           Injected into inner[0][9] for remix-style generation.
213:             force_token_factory: Force Token Factory usage for BotGuard tokens
214:                                  even when tool_id alone would suffice.
215:             extended_thinking: Explicitly enable or disable Thinking level
216:                                High (formerly Extended thinking). ``None``
217:                                preserves the legacy model behavior, including
218:                                ``thinking``. ``thinking_level`` wins when set.
219:             thinking_level: ``low``, ``medium``, or ``high``. Medium is 4 and
220:                             High is 2 on the model-header tail and inner[80].
221:             task: Select the Task composer control (formerly Spark) before
222:                   capture. Chrome's signed body carries the mode.
223:             video_orientation: For video generation, "landscape" (16:9) or
224:                                "portrait" (9:16). Drives the Omni video tool's
225:                                aspect-ratio control in Chrome.
226:             template: Optional template name (video or music, e.g. "Anime",
227:                       "Logo reveal", "Soundscape"). Applied through the
228:                       Create videos / Create music page in Chrome.
229:             image_aspect: For image generation, an aspect label ("1:1", "16:9",
230:                           ...). Drives the Images tool's aspect control.
231:             music_length: For music generation, the UI length label ("Short" /
232:                           "Standard") from MUSIC_LENGTHS.
233:             music_vocals: For music generation, the UI vocals label from MUSIC_VOCALS.
234:             music_genre: For music generation, the UI genre label from
235:                          normalize_music_genre().
236:         """
237:         resolved_model = self._resolve_model(
238:             model, extended_thinking, thinking_level=thinking_level
239:         )
240: 
241:         # ALL requests now route through Token Factory.
242:         # Google requires BotGuard to cryptographically sign request bodies.
243:         # Python-built bodies always get 0 candidates, even with valid cookies
244:         # and BotGuard tokens, because the signature is tied to the exact body
245:         # content Chrome generates. Only Chrome's signed body works.
246:         #
247:         # The regular HTTP path is kept as a fallback only if Token Factory
248:         # is completely unavailable (no Chrome profile configured).
249:         try:
250:             response = await self._send_via_token_factory(
251:                 prompt=prompt,
252:                 model=resolved_model,
253:                 metadata=metadata,
254:                 file_data=file_data,
255:                 gem_id=gem_id,
256:                 tool_id=tool_id,
257:                 style_preset=style_preset,
258:                 video_orientation=video_orientation,
259:                 template=template,
260:                 image_aspect=image_aspect,
261:                 music_length=music_length,
262:                 music_vocals=music_vocals,
263:                 music_genre=music_genre,
264:                 task=task,
265:             )
266:             return _check_reply(response)
267:         except Exception as e:
268:             # Attachments, tools, and Task only work with Chrome's signed body.
269:             # Without it Gemini answers anyway ("I can't open the file" plus an
270:             # invented description, issue #6), so fail instead of returning that.
271:             if isinstance(e, TokenFactoryError) and (file_data or tool_id or task):
272:                 raise TokenFactoryError(
273:                     f"{e}\nNot retrying without Chrome: attachments, "
274:                     "image/video/music tools, and Task mode need its BotGuard token."
275:                 ) from e
276:             # If Token Factory fails (no Chrome profile, Chrome not available),
277:             # fall back to regular HTTP path as a last resort.
278:             if isinstance(e, TokenFactoryError):
279:                 logger.warning(
280:                     f"Token Factory unavailable ({e}), falling back to regular HTTP. "
281:                     "This may not work if BotGuard is required."
282:                 )
283:             else:
284:                 raise
285: 
286:         return _check_reply(await self.transport.stream_generate(
287:             prompt=prompt,
288:             model=resolved_model,
289:             metadata=metadata,
290:             file_data=file_data,
291:             gem_id=gem_id,
292:             tool_id=tool_id,
293:             style_preset=style_preset,
294:             video_orientation=video_orientation,
295:             image_aspect=image_aspect,
296:         ))
297: 
298:     async def execute_rpc(
299:         self,
300:         rpc_id: str,
301:         payload: str = "[]",
302:         source_path: str = "/app",
303:     ) -> list[BatchResult]:
304:         """Execute a single RPC via batchexecute."""
305:         return await self.transport.batchexecute(
306:             payloads=[RPCPayload(rpc_id=rpc_id, payload=payload)],
307:             source_path=source_path,
308:         )
309: 
310:     async def execute_rpcs(
311:         self,
312:         payloads: list[RPCPayload],
313:         source_path: str = "/app",
314:     ) -> list[BatchResult]:
315:         """Execute multiple RPCs in a single batchexecute call."""
316:         return await self.transport.batchexecute(
317:             payloads=payloads,
318:             source_path=source_path,
319:         )
320: 
321:     async def _ensure_browser_cookies(self, force: bool = False) -> bool:
322:         """Ensure browser cookies are available by extracting from Chrome via CDP.
323: 
324:         Tries the Chrome daemon first, then falls back to launching Token Factory.
325:         Does NOT waste an API call — only extracts cookies from an existing session.
326: 
327:         Args:
328:             force: Ignore cached cookies and re-extract live cookies from Chrome.
329:                    Used when pre-populated auth.json cookies turn out to be stale.
330: 
331:         Returns:
332:             True if browser cookies are now available, False otherwise.
333:         """
334:         if self._browser_cookies and not force:
335:             return True
336: 
337:         if force:
338:             self._browser_cookies = None
339:             self._raw_browser_cookies = []
340:             self._browser_access_token = None
341: 
342:         try:
343:             from .browser_auth import get_browser_auth_status_for_port
344:             from .cdp import find_existing_gemcli_chrome, run_js
345:             from .chrome_manager import check_daemon_health, same_chrome_profile_path
346: 
347:             profile_name = self.auth_manager.resolved_profile_name
348:             expected_email = (self.auth_manager.state.email or "").lower()
349: 
350:             # Helper: extract cookies + access token from Chrome on a given port.
351:             # Never injects saved cookies into that Chrome (issue #3), and
352:             # refuses a Chrome signed in to a different account.
353:             def _extract_from_port(port: int) -> bool:
354:                 status = get_browser_auth_status_for_port(port)
355:                 if not status.is_authenticated:
356:                     return False
357:                 if expected_email and status.ws_url:
358:                     chrome_email = (
359:                         run_js(status.ws_url, "window.WIZ_global_data?.oPEP7c || ''") or ""
360:                     ).lower()
361:                     if chrome_email and chrome_email != expected_email:
362:                         logger.warning(
363:                             f"Chrome on port {port} is signed in as {chrome_email}, "
364:                             f"not {expected_email} (profile '{profile_name}') — not using it"
365:                         )
366:                         return False
367:                 self._browser_cookies = status.cookies
368:                 self._raw_browser_cookies = status.raw_cookies
369:                 self._browser_access_token = status.access_token
370:                 logger.info(
371:                     f"Browser cookies extracted from Chrome "
372:                     f"({len(status.cookies)} cookies)"
373:                 )
374:                 return True
375: 
376:             # Use this profile's own daemon only; another profile's daemon
377:             # would return another account's cookies.
378:             daemon_info, status = check_daemon_health(profile_name)
379:             port = None
380:             daemon_is_ours = bool(
381:                 status == "running" and daemon_info and (
382:                     daemon_info.profile_name == profile_name
383:                     or same_chrome_profile_path(
384:                         daemon_info.chrome_profile_path,
385:                         self.profile_manager.get_chrome_profile_path(profile_name),
386:                     )
387:                 )
388:             )
389: 
390:             if daemon_is_ours:
391:                 port = daemon_info.port
392:                 logger.debug(
393:                     f"Extracting browser cookies from Chrome daemon on port {port}"
394:                 )
395:             else:
396:                 # Fall back: this profile's own gemcli Chrome from the port map
397:                 found_port, found_url = find_existing_gemcli_chrome(
398:                     profile_name=profile_name
399:                 )
400:                 if found_port:
401:                     port = found_port
402:                     logger.debug(
403:                         f"Extracting browser cookies from gemcli Chrome "
404:                         f"on port {port}"
405:                     )
406: 
407:             if port and _extract_from_port(port):
408:                 return True
409: 
410:             # Last resort: launch Token Factory to get Chrome running,
411:             # then extract cookies directly from the page via CDP
412:             logger.debug(
413:                 "No running Chrome found, launching Token Factory for cookies"
414:             )
415:             factory = self._ensure_token_factory()
416:             loop = asyncio.get_event_loop()
417:             await loop.run_in_executor(None, factory.ensure_ready)
418: 
419:             # Token Factory's get_raw_cookies() is only populated after
420:             # capture(), so we extract cookies directly from Chrome via CDP
421:             if factory._port and _extract_from_port(factory._port):
422:                 return True
423: 
424:         except Exception as e:
425:             logger.warning(f"Failed to extract browser cookies: {e}")
426: 
427:         return False
428: 
429:     async def execute_rpc_with_browser_cookies(
430:         self,
431:         rpc_id: str,
432:         payload: str = "[]",
433:         source_path: str = "/app",
434:     ) -> list[BatchResult]:
435:         """Execute a single RPC using full browser cookies.
436: 
437:         Required for RPCs that need full auth (e.g. hNvQHb conversation reload
438:         after Token Factory-initiated video generation). Auto-populates browser
439:         cookies from Chrome if not already available.
440:         """
441:         return await self.execute_rpcs_with_browser_cookies(
442:             [RPCPayload(rpc_id=rpc_id, payload=payload)],
443:             source_path=source_path,
444:         )
445: 
446:     async def execute_rpcs_with_browser_cookies(
447:         self,
448:         payloads: list[RPCPayload],
449:         source_path: str = "/app",
450:     ) -> list[BatchResult]:
451:         """Execute one or more RPCs in a single batchexecute call with full cookies.
452: 
453:         Batching lets RPCs that only process one payload per call (e.g. qpEbW
454:         usage queries) be fetched in a single HTTP round-trip.
455: 
456:         Cookies pre-populated from auth.json can be stale; when the request
457:         returns no data and the cookies did not come from a live Chrome
458:         session, the cookies are re-extracted from Chrome and the batch is
459:         retried once.
460:         """
461:         results = await self._execute_browser_batch(payloads, source_path)
462:         cookies_are_live = bool(self._raw_browser_cookies)
463: 
464:         if not any(r.data for r in results) and not cookies_are_live:
465:             refreshed = await self._ensure_browser_cookies(force=True)
466:             if refreshed:
467:                 results = await self._execute_browser_batch(payloads, source_path)
468: 
469:         return results
470: 
471:     async def _execute_browser_batch(
472:         self,
473:         payloads: list[RPCPayload],
474:         source_path: str = "/app",
475:     ) -> list[BatchResult]:
476:         """One batchexecute POST with whatever browser cookies are available."""
477:         # Auto-populate browser cookies if not already available
478:         if not self._browser_cookies:
479:             await self._ensure_browser_cookies()
480: 
481:         if not self._browser_cookies:
482:             return await self.execute_rpcs(payloads, source_path)
483: 
484:         from .parser import parse_batchexecute_response
485:         from .rpc import (
486:             build_batchexecute_body,
487:             build_batchexecute_url,
488:             build_headers,
489:         )
490: 
491:         rpc_ids = [p.rpc_id for p in payloads]
492:         url = build_batchexecute_url(
493:             rpc_ids=rpc_ids,
494:             reqid=self.transport._next_reqid(),
495:             build_label=self.transport.build_label,
496:             session_id=self.transport.session_id,
497:             source_path=source_path,
498:         )
499:         body = build_batchexecute_body(
500:             payloads,
501:             self._browser_access_token or self.transport.access_token,
502:         )
503:         headers = build_headers()
504: 
505:         if self._browser_http_client is None:
506:             self._browser_http_client = httpx.AsyncClient(
507:                 http2=True, timeout=self.timeout, follow_redirects=True,
508:             )
509: 
510:         logger.debug(f"batchexecute (browser cookies): {rpc_ids}")
511:         response = await self._browser_http_client.post(
512:             url, content=body, headers=headers, cookies=self._browser_cookies,
513:         )
514:         response.raise_for_status()
515: 
516:         parsed = parse_batchexecute_response(response.text)
517:         return [
518:             BatchResult(rpc_id=r["rpc_id"], data=r["data"], raw=r["raw"])
519:             for r in parsed
520:         ]
521: 
522:     async def process_gem_file(
523:         self, upload_id: str, filename: str, mime_type: str
524:     ) -> str:
525:         """Process an uploaded file for use as a gem knowledge file.
526: 
527:         Calls the ProcessFile endpoint to convert a resumable upload ID into a
528:         gem knowledge token (starts with "$Aed...") for embedding in gem create/update
529:         payloads at position 14.
530: 
531:         Discovered via Chrome DevTools (Feb 2026). Different from batchexecute:
532:         uses a dedicated endpoint with f.req=[null, "{inner_json}"] body format.
533: 
534:         Args:
535:             upload_id: File identifier from FileService.upload() (e.g. "/contrib_service/ttl_1d/..."
536:                        as returned by the resumable upload protocol)
537:             filename: Original filename (e.g. "knowledge.txt")
538:             mime_type: MIME type of the file (e.g. "text/plain")
539: 
540:         Returns:
541:             Gem knowledge token starting with "$" for use in gem payload position 14.
542:         """
543:         import json
544:         from urllib.parse import urlencode
545: 
546:         import orjson
547: 
548:         from .constants import Endpoint
549:         from .parser import extract_json_from_response, get_nested
550:         from .rpc import build_headers
551: 
552:         # Inner payload: [[[upload_id, null, 1, mime_type], filename, null×6, [1]], null, 1, ["en"]]
553:         # [1] at the end marks this as a gem knowledge file (vs [0] for chat attachments)
554:         inner_payload = [
555:             [[upload_id, None, 1, mime_type], filename, None, None, None, None, None, None, [1]],
556:             None,
557:             1,
558:             ["en"],
559:         ]
560:         inner_json = json.dumps(inner_payload)
561:         f_req = json.dumps([None, inner_json])
...
1051:                     continue
1052: 
1053:             raise last_error or GeminiError("CDP download failed after retries")
1054: 
1055:         return await loop.run_in_executor(None, _do_download)
1056: 
1057:     def _needs_token_factory(self, model: Model) -> bool:
1058:         """Check if this model requires BotGuard tokens (Pro/Thinking)."""
1059:         return model.name in TOKEN_FACTORY_MODELS or model.thinking_level != "low"
1060: 
1061:     def _ensure_token_factory(self):
1062:         """Lazy-initialize the Token Factory."""
1063:         if self._token_factory is None:
1064:             from .token_factory import TokenFactory
1065: 
1066:             auth_state = self.auth_manager.state
1067:             if not auth_state.chrome_profile_path:
1068:                 raise TokenFactoryError(
1069:                     "No Chrome profile configured. Run 'gemcli login' first."
1070:                 )
1071:             self._token_factory = TokenFactory(
1072:                 chrome_profile_path=auth_state.chrome_profile_path,
1073:                 profile_name=self.auth_manager.resolved_profile_name,
1074:             )
1075:         return self._token_factory
1076: 
1077:     async def _send_via_token_factory(
1078:         self,
1079:         prompt: str,
1080:         model: Model,
1081:         metadata: ConversationMetadata | None = None,
1082:         file_data: list | None = None,
1083:         gem_id: str | None = None,
1084:         tool_id: int | None = None,
1085:         style_preset: dict | None = None,
1086:         video_orientation: str | None = None,
1087:         template: str | None = None,
1088:         image_aspect: str | None = None,
1089:         music_length: str | None = None,
1090:         music_vocals: str | None = None,
1091:         music_genre: str | None = None,
1092:         task: bool = False,
1093:     ) -> StreamResponse:
1094:         """Send via Token Factory: Chrome captures BotGuard token, Python sends HTTP."""
1095:         factory = self._ensure_token_factory()
1096: 
1097:         # TokenFactory is sync (CDP uses sync websocket) — run in executor
1098:         loop = asyncio.get_event_loop()
1099:         captured = await loop.run_in_executor(
1100:             None,
1101:             lambda: factory.capture(
1102:                 prompt=prompt,
1103:                 model=model,
1104:                 metadata=metadata,
1105:                 tool_id=tool_id,
1106:                 video_orientation=video_orientation,
1107:                 template=template,
1108:                 image_aspect=image_aspect,
1109:                 music_length=music_length,
1110:                 music_vocals=music_vocals,
1111:                 music_genre=music_genre,
1112:                 task=task,
1113:             ),
1114:         )
1115: 
1116:         # Create a separate HTTP client for browser-replay requests
1117:         # (no preset cookies — we use the captured cookies directly)
1118:         if self._browser_http_client is None:
1119:             self._browser_http_client = httpx.AsyncClient(
1120:                 http2=True,
1121:                 timeout=self.timeout,
1122:                 follow_redirects=True,
1123:             )
1124: 
1125:         # Store browser cookies and access token for use by other operations
1126:         # (e.g., image download, video polling batchexecute calls).
1127:         # IMPORTANT: captured.access_token is Chrome's live SNlM0e token extracted
1128:         # from window.WIZ_global_data — use it for ANY subsequent calls that use
1129:         self._browser_cookies = captured.cookies
1130:         self._raw_browser_cookies = factory.get_raw_cookies()
1131:         self._browser_access_token = captured.access_token  # Chrome's live SNlM0e
1132: 
1133:         # Sync fresh CDP auth back to disk so parallel/future CLI runs get it
1134:         try:
1135:             from gemini_web_mcp_cli.core.auth import AuthManager
1136:             am = AuthManager(
1137:                 self.profile_manager, profile_name=self.auth_manager.resolved_profile_name
1138:             )
1139:             am.load()
1140:             am.state.tokens.snlm0e = captured.access_token
1141:             if self._raw_browser_cookies:
1142:                 from .cdp import _filter_gemini_cookies
1143: 
1144:                 cookie_dict = _filter_gemini_cookies(self._raw_browser_cookies)
1145:                 if cookie_dict:
1146:                     am.save_cookies(cookie_dict)
1147:                     logger.debug("Token Factory: synced fresh browser cookies back to AuthManager.")
1148:         except Exception as e:
1149:             logger.debug(f"Failed to sync Token Factory auth to disk: {e}")
1150: 
1151:         if captured.transport == TRANSPORT_PROCESS_SESSION:
1152:             return await self._replay_process_session(
1153:                 captured, prompt, model, file_data, metadata
1154:             )
1155: 
1156:         # We extract the BotGuard token from Chrome's captured body and inject it
1157:         # into our rebuilt body. We use Chrome's live SNlM0e access token
1158:         # (captured.access_token) to ensure the 'at=' parameter is always consistent
1159: 
1160:         # Relay Chrome's captured body with the real prompt (inner[0][0]),
1161:         # attachments (inner[0][3]) and conversation (inner[2]) patched in.
1162:         # Chrome types a newline-free copy of the prompt (typing a newline cut
1163:         # the captured prompt off at the first line, issue #2); BotGuard does
1164:         # not bind the prompt text, so patching it is safe (verified live).
1165:         body_str = self._patch_captured_body(
1166:             captured.body, prompt, metadata=metadata, file_data=file_data
1167:         )
1168: 
1169:         logger.debug(
1170:             f"Token Factory: relaying Chrome's signed body "
1171:             f"(model={model.name}, body_len={len(body_str)})"
1172:         )
1173:         response = await self._browser_http_client.post(
1174:             captured.url,
1175:             content=body_str,
1176:             headers=captured.headers,
1177:             cookies=captured.cookies,
1178:         )
1179:         response.raise_for_status()
1180: 
1181:         result = build_stream_response(response.text)
1182:         logger.debug(
1183:             f"Token Factory response: text={bool(result.text)}, "
1184:             f"images={result.has_images}, video={result.has_video}, "
1185:             f"music={result.has_music}, model={result.server_model_hash}, "
1186:             f"candidates={len(result.candidates)}"
1187:         )
1188:         return result
1189: 
1190:     async def _replay_process_session(
1191:         self,
1192:         captured,
1193:         prompt: str,
1194:         model: Model,
1195:         file_data: list | None,
1196:         metadata: ConversationMetadata | None,
1197:     ) -> StreamResponse:
1198:         """Replay a processSession capture: open a channel with Chrome's cookies,
1199:         send Chrome's setup message and the prompt, parse the streamed answer."""
1200:         try:
1201:             messages = webchannel.decode_forward_body(captured.body)
1202:         except ValueError as e:
1203:             raise APIError(f"Unrecognised processSession request from Chrome: {e}") from e
1204:         setup = webchannel.find_setup_message(messages)
1205:         if setup is None:
1206:             raise TokenFactoryError("processSession capture has no setup message.")
1207:         inner = webchannel.setup_inner(setup)
1208:         if metadata and metadata.cid:
1209:             webchannel.set_conversation(inner, metadata.cid)
1210:         if file_data:
1211:             while len(inner[0]) <= 3:
1212:                 inner[0].append(None)
1213:             inner[0][3] = file_data
1214:         # Chrome may encode the channel as binary protobuf; decode_forward_body
1215:         # converted its setup to JSON, so declare JSON for the replayed channel.
1216:         open_url = webchannel.use_json_encoding(
1217:             webchannel.apply_model(captured.url, setup, model)
1218:         )
1219: 
1220:         transcript = await webchannel.replay(
1221:             self._browser_http_client,
1222:             open_url,
1223:             [setup, webchannel.prompt_message(prompt)],
1224:             cookies=captured.cookies,
1225:             headers=captured.headers,
1226:             timeout=self.timeout,
1227:         )
1228:         result = build_process_session_response(transcript)
1229:         logger.debug(
1230:             f"Token Factory (processSession) response: text={bool(result.text)}, "
1231:             f"images={result.has_images}, video={result.has_video}, "
1232:             f"music={result.has_music}, model={result.server_model_hash}, "
1233:             f"candidates={len(result.candidates)}"
1234:         )
1235:         return result
1236: 
1237:     @staticmethod
1238:     def _extract_botguard(captured_body: str) -> tuple[str | None, str | None]:
1239:         """Extract BotGuard token and challenge hash from Chrome's captured request body.
1240: 
1241:         Chrome's body is URL-encoded form data with an f.req parameter containing
1242:         a nested JSON array. The BotGuard token is at inner[3] and the challenge
1243:         hash is at inner[4].
1244: 
1245:         Returns:
1246:             Tuple of (botguard_token, botguard_hash), either may be None.
1247:         """
1248:         import json
1249:         from urllib.parse import parse_qs, unquote
1250: 
1251:         try:
1252:             parsed = parse_qs(captured_body)
1253:             f_req_raw = parsed.get("f.req", [None])[0]
1254:             if not f_req_raw:
1255:                 # processSession data POST (req0___data__ = setup message)
1256:                 return webchannel.extract_botguard(captured_body)
1257:             f_req = unquote(f_req_raw)
1258:             outer = json.loads(f_req)
1259:             inner = json.loads(outer[1])
1260:             token = inner[3] if len(inner) > 3 and isinstance(inner[3], str) else None
1261:             hash_val = inner[4] if len(inner) > 4 and isinstance(inner[4], str) else None
1262:             if token:
1263:                 logger.debug(f"Extracted BotGuard token ({len(token)} chars) "
1264:                              f"and hash={hash_val is not None}")
1265:             return token, hash_val
1266:         except Exception as e:
1267:             logger.debug(f"Could not extract BotGuard from captured body: {e}")
1268:             return None, None
1269: 
1270:     @staticmethod
1271:     def _extract_at_from_body(captured_body: str) -> str | None:
1272:         """Extract the at= (SNlM0e) token from Chrome's captured request body.
1273: 
1274:         Chrome's body is URL-encoded form data containing an 'at' parameter
1275:         that holds the SNlM0e access token. This token is guaranteed to match
1276:         Chrome's cookies since it's the one Chrome was going to use.
1277: 
1278:         Returns:
1279:             The access token string, or None if not found.
1280:         """
1281:         from urllib.parse import parse_qs
1282: 
1283:         try:
1284:             parsed = parse_qs(captured_body)
1285:             at_values = parsed.get("at", [])
1286:             if at_values and at_values[0]:
1287:                 token = at_values[0]
1288:                 logger.debug(
1289:                     f"Extracted at= token from captured body "
1290:                     f"({len(token)} chars)"
1291:                 )
1292:                 return token
1293:         except Exception as e:
1294:             logger.debug(f"Could not extract at= from captured body: {e}")
1295:         return None
1296: 
1297:     @staticmethod
1298:     def _patch_captured_body(
1299:         captured_body: str,
1300:         prompt: str,
1301:         metadata: object = None,
`

## 3. token_factory.py (_ensure_ready_locked, _restart_owned_daemon, _set_model_picker, _set_composer_mode, _capture_locked)
`python
741:                     self._process.kill()
742:                 except Exception:
743:                     pass
744:                 self._process = None
745:             self._ready = False
746:             self._ws_url = None
747:             self._port = None
748:             self._we_launched = False
749: 
750:         chrome_path = get_chrome_path()
751:         if not chrome_path:
752:             raise TokenFactoryError(
753:                 "No Chromium browser found. Install Chrome, Brave, Edge, or another "
754:                 "Chromium browser for Pro/Thinking models.\n"
755:                 "Set preference: GEMCLI_BROWSER=brave or gemcli config set browser brave"
756:             )
757: 
758:         if not self._chrome_profile_path:
759:             raise TokenFactoryError(
760:                 "No Chrome profile configured. Run 'gemcli login' first."
761:             )
762: 
763:         # Try to find an existing gemcli Chrome instance for our profile
764:         # (profile-aware — won't accidentally grab Antigravity's browser).
765:         # If the daemon is running ('gemcli chrome start'), it's registered
766:         # in the port map and will be found here.  We should ALWAYS reuse
767:         # a running daemon — it has the authenticated session and avoids
768:         # launching a stale TF profile.
769:         #
770:         # Health-check first: this may auto-stop+cleanup a daemon whose age
771:         # or RSS has exceeded the limits, which clears the port map entry
772:         # so find_existing_gemcli_chrome() naturally returns nothing and we
773:         # fall through to launch a fresh TF Chrome below.
774:         from .chrome_manager import check_daemon_health
775: 
776:         check_daemon_health(self._profile_name)
777:         existing_port, existing_url = find_existing_gemcli_chrome(
778:             profile_name=self._profile_name
779:         )
780: 
781:         if not existing_port and self._on_demand_daemon:
782:             from .daemon_idle import start_on_demand
783: 
784:             if start_on_demand(self._profile_name, self._chrome_profile_path):
785:                 existing_port, existing_url = find_existing_gemcli_chrome(
786:                     profile_name=self._profile_name
787:                 )
788: 
789:         if existing_port:
790:             # Health check: verify the Chrome has functional pages before
791:             # committing to reuse it.  A zombie Chrome (PID alive, CDP
792:             # responding, but zero pages) will fail downstream.
793:             if is_chrome_healthy(existing_port):
794:                 self._port = existing_port
795:                 self._we_launched = False
796:                 logger.debug(f"Token Factory: reusing Chrome on port {existing_port}")
797:                 # Verify the connection actually works (catches stale target IDs
798:                 # left over from a Chrome restart — Bug 4)
799:                 try:
800:                     page = find_or_create_gemini_page(self._port)
801:                     if page and page.get("webSocketDebuggerUrl"):
802:                         ws_url = page["webSocketDebuggerUrl"]
803:                         get_current_url(ws_url)  # Probe — raises StaleTargetError if stale
804:                     else:
805:                         raise StaleTargetError("No functional Gemini page")
806:                 except (StaleTargetError, Exception) as e:
807:                     # A stale daemon is restarted once; a second failure
808:                     # falls through to a private Chrome below.
809:                     if not _healed and self._restart_owned_daemon(existing_port, e):
810:                         return self._ensure_ready_locked(_healed=True)
811:                     logger.warning(
812:                         f"Token Factory: Chrome on port {existing_port} has "
813:                         f"stale target IDs ({e}) — clearing and launching fresh"
814:                     )
815:                     _clear_port_map(existing_port)
816:                     existing_port = None  # Fall through to fresh launch
817:             else:
818:                 if not _healed and self._restart_owned_daemon(
819:                     existing_port, "no functional pages"
820:                 ):
821:                     return self._ensure_ready_locked(_healed=True)
822:                 logger.warning(
823:                     f"Token Factory: Chrome on port {existing_port} is unhealthy "
824:                     f"(no pages), launching fresh instance"
825:                 )
826:                 existing_port = None  # Fall through to fresh launch
827: 
828:         if not existing_port:
829:             # Launch on the profile's OWN user-data-dir. Never a copy: a copied
830:             # profile carries the same (device-bound) Google session, and using
831:             # one session from several browsers gets it revoked (issue #3).
832:             profile_dir = Path(self._chrome_profile_path)
833:             profile_dir.mkdir(parents=True, exist_ok=True)
834: 
835:             # Clean up orphaned Chrome processes on exactly this profile
836:             self._kill_stale_chrome(profile_dir)
837: 
838:             # Use a different port range (9300+) for headless TF instances
839:             # so they don't block `gemcli login` from using the 9222+ range
840:             # when searching for existing visible browsers.
841:             self._port = find_available_port(start=9300)
842:             from gemini_web_mcp_cli.core.constants import CHROME_USER_AGENT
843:             args = [
844:                 chrome_path,
845:                 f"--remote-debugging-port={self._port}",
846:                 "--no-first-run",
847:                 "--no-default-browser-check",
848:                 "--disable-extensions",
849:                 f"--user-data-dir={profile_dir}",
850:                 "--remote-allow-origins=*",
851:                 "--headless",
852:                 f"--user-agent={CHROME_USER_AGENT}",
853:                 "--disable-blink-features=AutomationControlled",
854:             ]
855:             try:
856:                 # DEVNULL, not PIPE: nobody reads these pipes, and a long-lived
857:                 # Chrome blocks once its stderr fills the 64 KB pipe buffer.
858:                 self._process = subprocess.Popen(
859:                     args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
860:                 )
861:                 time.sleep(3)
862:             except Exception as e:
863:                 raise TokenFactoryError(f"Failed to launch Chrome: {e}")
864:             self._we_launched = True
865:             # Register in port map so other gemcli components can discover us
866:             _write_port_map(self._port, self._profile_name, self._process.pid)
867:             logger.debug(
868:                 f"Token Factory: launched Chrome on port {self._port} "
869:                 f"with TF profile {profile_dir}"
870:             )
871: 
872:         # Find or create Gemini page (retry — headless Chrome may take
873:         # a moment for the debugger endpoint to become responsive)
874:         page = None
875:         for _ in range(5):
876:             page = find_or_create_gemini_page(self._port)
877:             if page:
878:                 break
879:             time.sleep(3)
880:         if not page:
881:             raise TokenFactoryError("Failed to open Gemini page in Chrome.")
882: 
883:         self._ws_url = page.get("webSocketDebuggerUrl")
884:         if not self._ws_url:
885:             raise TokenFactoryError("No WebSocket URL for Gemini page.")
886: 
887:         # Navigate to /app if not already there (this also leaves a Google
888:         # sign-in page a previous failed attempt may have parked Chrome on).
889:         current_url = get_current_url(self._ws_url)
890:         if "gemini.google.com/app" not in current_url:
891:             navigate_to_url(self._ws_url, GEMINI_APP_URL)
892: 
893:         # Wait for input field
894:         if not self._wait_for_input():
895:             raise TokenFactoryError("Gemini page failed to load (input field not found).")
896: 
897:         # Verify the page is signed in. The signed-out Gemini page also has an
898:         # SNlM0e, so only the account email (oPEP7c) proves a session. Saved
899:         # auth.json cookies are never injected into Chrome: this Chrome owns
900:         # the session, and mixing in another copy gets it revoked (issue #3).
901:         signed_in_email = run_js(self._ws_url, "window.WIZ_global_data?.oPEP7c || ''")
902:         snlm0e = run_js(
903:             self._ws_url, "window.WIZ_global_data?.SNlM0e || ''"
904:         ) if signed_in_email else ""
905: 
906:         if not snlm0e:
907:             logger.info(
908:                 "Token Factory: Chrome profile is signed out — attempting "
909:                 "one-click sign-in via CDP..."
910:             )
911:             snlm0e = self._auto_sign_in()
912:             if not snlm0e:
913:                 raise AuthError(
914:                     "Session expired — auto sign-in failed.\n"
915:                     f"Run 'gemcli login --profile {self._profile_name}' to sign in again."
916:                 )
917: 
918:         self._ready = True
919:         self._touch_daemon()
920:         logger.debug("Token Factory: ready")
921: 
922:     def _reset_connection(self) -> None:
923:         """Forget the Chrome this factory was attached to (it is not ours to close)."""
924:         self._ready = False
925:         self._ws_url = None
926:         self._port = None
927:         self._we_launched = False
928: 
929:     def _touch_daemon(self) -> None:
930:         """Reset the persistent daemon's idle clock and make sure it is watched.
931: 
932:         A missing watcher (it died, or the daemon was started by `gemcli chrome
933:         start` in another process) is replaced. Does nothing for a Chrome this
934:         factory launched itself.
935:         """
936:         if self._we_launched:
937:             return
938:         from .chrome_manager import load_daemon_info, touch_activity
939:         from .daemon_idle import ensure_watcher
940: 
941:         touch_activity(self._profile_name)
942:         info = load_daemon_info(self._profile_name)
943:         if info is not None and info.port == self._port:
944:             ensure_watcher(info)
945: 
946:     def _restart_owned_daemon(self, port: int, reason) -> bool:
947:         """Restart the persistent daemon on ``port`` (once per caller).
948: 
949:         Stops it (the profile lock is held, so no other request is using it)
950:         and starts a fresh one on the same profile. Returns True if a fresh
951:         daemon is up; this factory then reconnects from scratch. False when
952:         ``port`` is not the daemon's or it could not be restarted.
953:         """
954:         from .chrome_manager import _restart_daemon, load_daemon_info
955: 
956:         info = load_daemon_info(self._profile_name)
957:         if info is None or info.port != port:
958:             return False
959:         logger.warning(
960:             f"Token Factory: Chrome daemon on port {port} is stale ({reason}) — "
961:             "restarting it"
962:         )
963:         fresh, _ = _restart_daemon(info)
964:         self._reset_connection()
965:         return fresh is not None
966: 
967:     def _auto_sign_in(self) -> str | None:
968:         """Attempt automatic sign-in by clicking Gemini's Sign In button via CDP.
969: 
970:         Chrome's profile retains the Google account at the browser level even
971:         when Gemini session cookies expire.  Clicking "Sign in" triggers an
972:         OAuth redirect that Chrome auto-completes — zero user interaction.
973: 
974:         If the redirect lands on a Google account-chooser page, the first
975:         account is selected automatically. If Chrome has no saved Google
976:         account and lands on the email-entry page, the saved AuthManager email
977:         is submitted before continuing the OAuth flow.
978: 
979:         Returns:
980:             The SNlM0e token if sign-in succeeds, or None on failure.
981:         """
982:         from .cdp import _filter_gemini_cookies
983: 
984:         ws = self._ws_url
985:         auth_email = self._load_auth_email()
986: 
987:         # Click "Sign in" in the Gemini UI
988:         clicked = run_js(ws, """
989:             (() => {
990:                 const buttons = document.querySelectorAll('button');
991:                 for (const btn of buttons) {
992:                     if (btn.textContent.trim() === 'Sign in') {
993:                         btn.click();
994:                         return true;
995:                     }
996:                 }
997:                 return false;
998:             })()
999:         """)
1000:         if not clicked:
1001:             logger.debug("Token Factory: no 'Sign in' button found")
...
1221:             return False
1222:         js = SELECT_COMPANION_OPTION_JS.format(
1223:             mode="aspect", control="Aspect ratio", label=label
1224:         )
1225:         result = run_js(self._ws_url, js)
1226:         if result in ("selected", "already_active"):
1227:             logger.debug(f"Token Factory: aspect ratio '{label}' {result}")
1228:             time.sleep(0.3)
1229:             return True
1230:         logger.warning(
1231:             f"Token Factory: failed to set aspect ratio '{label}' (result: {result})"
1232:         )
1233:         return False
1234: 
1235:     def _set_music_option(self, control: str, label: str) -> bool:
1236:         """Pick a Length/Vocals/Genre option in Chrome's music composer.
1237: 
1238:         Chrome encodes music picks in inner[55] and inner[0][9].
1239:         """
1240:         if not label:
1241:             return False
1242:         js = SELECT_COMPANION_OPTION_JS.format(
1243:             mode="named", control=control, label=label
1244:         )
1245:         result = run_js(self._ws_url, js)
1246:         if result in ("selected", "already_active"):
1247:             logger.debug(f"Token Factory: music {control}='{label}' {result}")
1248:             time.sleep(0.3)
1249:             return True
1250:         logger.warning(
1251:             f"Token Factory: failed to set music {control}='{label}' "
1252:             f"(result: {result})"
1253:         )
1254:         return False
1255: 
1256:     def _set_model_picker(self, model) -> bool:
1257:         """Select the requested model in Chrome's Gemini mode picker.
1258: 
1259:         Chat requests mirror the same picker: inner[79] is the model category
1260:         and inner[80] is the thinking level (Low=1, Medium=4, High=2). The
1261:         base model is matched by hash via data-test-id. Thinking level is the
1262:         Low / Medium / High submenu.
1263: 
1264:         Best effort — returns False on failure and lets capture() continue,
1265:         since the model header override still applies. A page that selected the
1266:         base model but not the thinking level is reported separately, so the
1267:         log does not claim the model itself could not be chosen.
1268:         """
1269:         if not getattr(model, "hash", None):
1270:             return False
1271: 
1272:         js = SET_MODEL_PICKER_JS.replace("{hash}", model.hash).replace(
1273:             "{level}", model.thinking_label
1274:         )
1275:         result = run_js(self._ws_url, js)
1276: 
1277:         if result == "set":
1278:             logger.debug(f"Token Factory: model picker set to {model.name}")
1279:             time.sleep(0.3)
1280:             return True
1281: 
1282:         if result == "base_set_level_not_found":
1283:             logger.warning(
1284:                 f"Token Factory: model set to {model.name}, thinking level "
1285:                 f"{model.thinking_label} not applied (level control not found)"
1286:             )
1287:             return False
1288: 
1289:         logger.warning(
1290:             f"Token Factory: failed to set model picker to {model.name} "
1291:             f"(result: {result})"
1292:         )
1293:         return False
1294: 
1295:     def _set_composer_mode(self, task: bool) -> bool:
1296:         """Select Chat or Task on the segmented control under the prompt.
1297: 
1298:         Task is required: a missing control must not silently send a chat.
1299:         Chat is best effort so an account that has not received the toggle
1300:         still sends.
1301:         """
1302:         want = "Task" if task else "Chat"
1303:         result = run_js(self._ws_url, SET_COMPOSER_MODE_JS.replace("{mode}", want))
1304:         if result in ("set", "already"):
1305:             logger.debug(f"Token Factory: composer mode {want} {result}")
1306:             time.sleep(0.2)
1307:             return True
1308:         if task:
1309:             raise TokenFactoryError(
1310:                 "Could not select Task in Gemini. The Chat/Task control was "
1311:                 "not on the page. Reload gemini.google.com in the GemCLI "
1312:                 "Chrome window and try again."
1313:             )
1314:         logger.debug(f"Token Factory: Chat control not found ({result})")
1315:         return False
1316: 
1317:     def _deactivate_tool(self) -> None:
1318:         """Deactivate any active tool in Chrome's Gemini UI."""
1319:         try:
1320:             run_js(self._ws_url, DEACTIVATE_TOOL_JS)
1321:         except Exception:
1322:             pass  # Non-fatal
1323: 
1324:     def capture(
1325:         self,
1326:         prompt: str,
1327:         model,
1328:         metadata=None,
1329:         tool_id: int | None = None,
1330:         video_orientation: str | None = None,
1331:         template: str | None = None,
1332:         image_aspect: str | None = None,
1333:         music_length: str | None = None,
1334:         music_vocals: str | None = None,
1335:         music_genre: str | None = None,
1336:         task: bool = False,
1337:     ) -> CapturedRequest:
1338:         """Capture a BotGuard token while holding the profile lock.
1339: 
1340:         See _capture_locked() for arguments. Callers on the same profile (other
1341:         CLI runs, parallel MCP calls) wait; they would otherwise overwrite this
1342:         capture's prompt, tool state and token in the shared Gemini tab.
1343:         """
1344:         self._cancel_idle_timer()
1345:         with profile_lock(self._profile_name):
1346:             options = dict(
1347:                 metadata=metadata, tool_id=tool_id,
1348:                 video_orientation=video_orientation, template=template,
1349:                 image_aspect=image_aspect, music_length=music_length,
1350:                 music_vocals=music_vocals, music_genre=music_genre,
1351:                 task=task,
1352:             )
1353:             try:
1354:                 try:
1355:                     return self._capture_locked(prompt, model, **options)
1356:                 except (StaleTargetError, TokenFactoryError) as e:
1357:                     # The persistent daemon can go stale while it still answers
1358:                     # CDP. Restart it once and retry once; capture sends nothing
1359:                     # to Gemini, so a retry cannot duplicate a prompt. A second
1360:                     # failure propagates.
1361:                     if (
1362:                         self._we_launched
1363:                         or not self._port
1364:                         or not self._restart_owned_daemon(self._port, e)
1365:                     ):
1366:                         raise
1367:                 return self._capture_locked(prompt, model, **options)
1368:             finally:
1369:                 self._touch_daemon()
1370: 
1371:     def _capture_locked(
1372:         self,
1373:         prompt: str,
1374:         model,
1375:         metadata=None,
1376:         tool_id: int | None = None,
1377:         video_orientation: str | None = None,
1378:         template: str | None = None,
1379:         image_aspect: str | None = None,
1380:         music_length: str | None = None,
1381:         music_vocals: str | None = None,
1382:         music_genre: str | None = None,
1383:         task: bool = False,
1384:     ) -> CapturedRequest:
1385:         """Capture a BotGuard token by triggering a request in Chrome.
1386: 
1387:         Args:
1388:             prompt: The message to send
1389:             model: Model object with .name and .header attributes
1390:             metadata: ConversationMetadata for multi-turn (has .cid for conversation ID)
1391:             tool_id: Tool activation ID (11=Videos, 14=Images, 21=Music)
1392:             video_orientation: For the Videos tool, "landscape" (16:9) or
1393:                 "portrait" (9:16). Drives Chrome's aspect-ratio control so the
1394:                 signed body carries the requested Omni video orientation.
1395:             template: Optional template name (video or music). Clicks the
1396:                 template card on the Create videos / Create music page.
1397:             image_aspect: For the Images tool, an aspect label ("1:1", "9:16",
1398:                 "3:4", "4:3", "16:9"). Drives Chrome's aspect-ratio control.
1399:             music_length: For the Music tool, the UI length label ("Short" /
1400:                 "Standard") from MUSIC_LENGTHS.
1401:             music_vocals: For the Music tool, the UI vocals label from MUSIC_VOCALS.
1402:             music_genre: For the Music tool, the UI genre label(s) from
1403:                 normalize_music_genre().
1404: 
1405:         Returns:
1406:             CapturedRequest with URL, body, headers, and cookies for Python replay.
1407:         """
1408:         self._ensure_ready_locked()
1409: 
1410:         # Force a full page reload every N generations to refresh stale SNlM0e tokens.
1411:         self._generation_count += 1
1412:         if self._generation_count % _GENERATIONS_BEFORE_REFRESH == 0:
1413:             logger.debug(
1414:                 f"Token Factory: generation {self._generation_count}, "
1415:                 f"forcing page reload for fresh SNlM0e"
1416:             )
1417:             navigate_to_url(self._ws_url, GEMINI_APP_URL)
1418:             if not self._wait_for_input():
1419:                 raise TokenFactoryError("Gemini page failed to load after periodic token refresh.")
1420:             signed_in = run_js(self._ws_url, "window.WIZ_global_data?.oPEP7c || ''")
1421:             if not signed_in:
1422:                 raise AuthError(
1423:                     "Token Factory: SNlM0e missing after page refresh — "
1424:                     "session expired. Run 'gemcli login' to refresh."
1425:                 )
1426: 
1427:         # Navigate to the right conversation
1428:         target_url = GEMINI_APP_URL
1429:         if metadata and metadata.cid:
1430:             # Response cids are "c_<hex>"; the web app's URL is /app/<hex>.
1431:             # With the prefix Chrome opens a blank chat and the follow-up
1432:             # starts a new conversation.
1433:             target_url = f"{GEMINI_APP_URL}/{metadata.cid.removeprefix('c_')}"
1434: 
1435:         # Always verify Chrome is on the target page. Re-navigate if needed.
1436:         # This handles the race condition where a previous capture() left
1437:         # Chrome mid-navigation (Bug 3: parallel image gen race).
1438:         current = get_current_url(self._ws_url)
1439:         if target_url not in current or "gemini.google.com" not in current:
1440:             navigate_to_url(self._ws_url, target_url)
1441:             if not self._wait_for_input():
1442:                 raise TokenFactoryError("Gemini page failed to load after navigation.")
1443:         else:
1444:             # Even if on the right URL, ensure the input field is ready
1445:             if not self._wait_for_input(timeout=5):
1446:                 # Page may be in a bad state from aborted XHR — re-navigate
1447:                 navigate_to_url(self._ws_url, target_url)
1448:                 if not self._wait_for_input():
1449:                     raise TokenFactoryError("Gemini page failed to load after navigation.")
1450: 
1451:         # Activate the requested tool (Images/Videos/Music) in Chrome's UI
1452:         # BEFORE typing the prompt. This ensures the BotGuard-signed request
1453:         # body includes the tool activation data.
1454:         #
1455:         # A disabled tool means the account hit its usage limit for that
1456:         # feature. Sending the prompt anyway would silently produce a chat or
1457:         # image response instead of the requested media, so fail fast.
1458:         tool_activated = False
1459:         if tool_id and tool_id in TOOL_ID_UI_ALIASES:
1460:             tool_name = TOOL_ID_TO_NAME.get(tool_id, str(tool_id))
1461:             tool_result = self._activate_tool(tool_id)
1462:             if tool_result not in ("activated", "already_active", "disabled"):
1463:                 # The page may still be settling after the navigation above;
1464:                 # reload it and retry activation once before giving up.
1465:                 logger.warning(
1466:                     f"Token Factory: retrying '{tool_name}' activation "
1467:                     f"after page reload (result: {tool_result})"
1468:                 )
1469:                 navigate_to_url(self._ws_url, target_url)
1470:                 if self._wait_for_input():
1471:                     tool_result = self._activate_tool(tool_id)
1472: 
1473:             if tool_result in ("activated", "already_active"):
1474:                 tool_activated = tool_result == "activated"
1475:             elif tool_result == "disabled":
1476:                 # UsageLimitExceeded deliberately does NOT subclass
1477:                 # TokenFactoryError — the client must surface it instead of
1478:                 # falling back to a direct HTTP request that cannot work.
1479:                 raise UsageLimitExceeded(
1480:                     f"The {tool_name} tool is disabled — Gemini usage limit "
1481:                     "reached for this profile. Try another profile with "
1482:                     "'-p <profile>' or wait for the quota to reset."
1483:                 )
1484:             else:
1485:                 # Sending the request without the tool would silently produce a
1486:                 # chat or image response instead of the requested media.
1487:                 raise ToolActivationError(
1488:                     f"Could not activate the {tool_name} tool in Gemini "
1489:                     f"(result: {tool_result}). Open gemini.google.com in the "
1490:                     "GemCLI Chrome window to check the tool is available, "
1491:                     "or try again."
1492:                 )
1493: 
1494:         # Media options: drive the composer's template / aspect-ratio / music
1495:         # controls so the captured body matches the requested options. The
1496:         # model header is still overridden below, but inner[79]/inner[80]
1497:         # mirror the picker, so the UI must agree.
1498:         if tool_id == VIDEO_TOOL_ID:
1499:             if template:
1500:                 self._set_template(template)
1501:             if video_orientation:
1502:                 self._set_aspect_ratio(VIDEO_ORIENTATION_LABELS[video_orientation])
1503:         elif tool_id == IMAGE_TOOL_ID:
1504:             if image_aspect:
1505:                 self._set_aspect_ratio(image_aspect)
1506:         elif tool_id == MUSIC_TOOL_ID:
1507:             if template:
1508:                 self._set_template(template)
1509:             if music_length:
1510:                 self._set_music_option("Length", music_length)
1511:             if music_vocals:
1512:                 self._set_music_option("Vocals", music_vocals)
1513:             if music_genre:
1514:                 self._set_music_option("Genre", music_genre)
1515: 
1516:         if model is not None and getattr(model, "hash", None):
1517:             self._set_model_picker(model)
1518: 
1519:         # Chat and Task share the composer. Tools (image/video/music) use their
1520:         # own pages, which do not have the segmented control.
1521:         if tool_id is None:
1522:             self._set_composer_mode(task)
1523: 
1524:         # Install XHR interceptor (resets window.__cap = null as its first statement)
1525:         run_js(self._ws_url, XHR_INTERCEPTOR_JS)
1526: 
1527:         # Type the prompt via DOM (long/complex text is unreliable as keystrokes)
1528:         # and click Send so Chrome builds a BotGuard-signed request. The typed
1529:         # text only triggers the capture; Python puts the real prompt into the
1530:         # request (issue #2). Newlines are flattened because typing one into
1531:         # Gemini's editor cut the captured prompt off at that line.
1532:         typed = " ".join(prompt.split())
1533:         escaped_prompt = typed.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
1534:         run_js(self._ws_url, TYPE_PROMPT_JS.format(prompt=escaped_prompt))
1535:         time.sleep(0.5)
1536:         run_js(self._ws_url, CLICK_SEND_JS)
1537: 
1538:         # Poll for captured request
1539:         captured = self._poll_capture()
1540:         if not captured:
1541:             self._raise_if_prompt_escaped(target_url)
1542:             # Retry once: navigate fresh, re-install hook
1543:             logger.debug("Token Factory: first capture failed, retrying...")
1544:             navigate_to_url(self._ws_url, target_url)
1545:             if not self._wait_for_input():
1546:                 raise TokenFactoryError("Gemini page failed to load on retry.")
1547:             run_js(self._ws_url, XHR_INTERCEPTOR_JS)
1548:             run_js(self._ws_url, TYPE_PROMPT_JS.format(prompt=escaped_prompt))
1549:             time.sleep(0.5)
1550:             run_js(self._ws_url, CLICK_SEND_JS)
1551:             captured = self._poll_capture()
1552:             if not captured:
1553:                 self._raise_if_prompt_escaped(target_url)
1554:                 raise TokenFactoryError(
1555:                     "Failed to capture BotGuard token after retry. "
1556:                     "Chrome may not be on gemini.google.com."
1557:                 )
1558: 
1559:         transport = captured.get("transport") or TRANSPORT_STREAMGENERATE
1560:         if transport == TRANSPORT_PROCESS_SESSION:
1561:             url = captured["url"]  # absolute channel-open URL
1562:         else:
1563:             url = "https://gemini.google.com" + captured["url"]
1564:         logger.debug(f"Token Factory: captured {transport} request")
1565: 
1566:         # Get JS-set headers (model header, tracking headers, etc.)
1567:         js_headers = captured.get("headers", {})
1568: 
1569:         # Build complete Chrome-like headers
1570:         headers = dict(CHROME_HEADERS)
1571:         headers["x-browser-validation"] = compute_xbv(CHROME_USER_AGENT)
1572:         headers.update(js_headers)
1573: 
1574:         # Keep Chrome's captured model header and rewrite the hash, category,
1575:         # and thinking level in place. The live header continues past that pair.
1576:         if model and getattr(model, "hash", None):
1577:             replaced = False
1578:             for key, value in list(headers.items()):
1579:                 if key.lower() == MODEL_HEADER_KEY and isinstance(value, str):
1580:                     headers[key] = rewrite_captured_model_header(value, model)
1581:                     replaced = True
1582:             if not replaced and model.header:
1583:                 headers.update(model.header)
1584: 
1585:         # Grab ALL cookies from the browser
1586:         cookies = self._get_google_cookies()
1587: 
1588:         # Extract the live SNlM0e access token from Chrome's window global.
1589:         # This is the correct 'at=' token for the current Chrome session, which
1590:         # must be used when replaying batchexecute calls with Chrome's cookies.
1591:         # Mismatching Python's cached token with Chrome's cookies causes silent
1592:         # empty responses (0 candidates). Retry up to 5s since WIZ_global_data
1593:         # is populated by Gemini's JS bootstrap after page load.
1594:         chrome_access_token: str | None = None
1595:         for attempt in range(10):
1596:             try:
1597:                 chrome_access_token = run_js(
1598:                     self._ws_url,
1599:                     "window.WIZ_global_data && window.WIZ_global_data.SNlM0e",
1600:                 )
1601:                 if chrome_access_token:
1602:                     logger.debug(
1603:                         f"Token Factory: captured Chrome SNlM0e "
1604:                         f"(attempt {attempt + 1}, "
1605:                         f"{len(chrome_access_token)} chars)"
1606:                     )
1607:                     break
1608:             except Exception:
1609:                 pass
1610:             time.sleep(0.5)
1611: 
1612:         # Fallback: extract SNlM0e from page HTML source.
1613:         # The token is server-rendered in the HTML even if JS globals
1614:         # haven't populated yet (same technique used by auth.py).
1615:         if not chrome_access_token:
1616:             try:
1617:                 import re
1618: 
1619:                 from .cdp import get_page_html
1620:                 from .constants import TOKEN_PATTERNS
1621: 
1622:                 html = get_page_html(self._ws_url)
1623:                 match = re.search(TOKEN_PATTERNS["snlm0e"], html)
1624:                 if match:
1625:                     chrome_access_token = match.group(1)
1626:                     logger.debug(
1627:                         f"Token Factory: extracted SNlM0e from "
1628:                         f"page HTML ({len(chrome_access_token)} chars)"
1629:                     )
1630:             except Exception as e:
1631:                 logger.debug(f"Token Factory: HTML SNlM0e extraction failed: {e}")
`

## 4. constants.py (RPC & Model constants)
`python
2: """Constants for the Gemini web interface.
3: 
4: Endpoints, RPC IDs, model hashes, headers, error codes.
5: """
6: 
7: import base64
8: import hashlib
9: import json
10: from enum import IntEnum, StrEnum
11: 
12: 
13: class Endpoint(StrEnum):
14:     """Gemini web interface endpoints."""
15: 
16:     GOOGLE = "https://www.google.com"
17:     INIT = "https://gemini.google.com/app"
18:     GENERATE = (
19:         "https://gemini.google.com/_/BardChatUi/data/"
20:         "assistant.lamda.BardFrontendService/StreamGenerate"
21:     )
22:     BATCH_EXEC = "https://gemini.google.com/_/BardChatUi/data/batchexecute"
23:     UPLOAD = "https://content-push.googleapis.com/upload"
24:     ROTATE_COOKIES = "https://accounts.google.com/RotateCookies"
25:     PROCESS_GEM_FILE = (
26:         "https://gemini.google.com/_/BardChatUi/data/"
27:         "assistant.lamda.BardFrontendService/ProcessFile"
28:     )
29: 
30: 
31: class RPC(StrEnum):
32:     """Google RPC IDs used in the Gemini web interface via batchexecute."""
33: 
34:     # Chat management
35:     LIST_CHATS = "MaZiqc"
36:     READ_CHAT = "hNvQHb"
37:     DELETE_CHAT = "GzXR5e"
38: 
39:     # Gem management
40:     LIST_GEMS = "CNgdBe"
41:     CREATE_GEM = "oMH3Zd"
42:     UPDATE_GEM = "kHv0Vd"
43:     DELETE_GEM = "UXcSJb"
44:     LIST_NLM_NOTEBOOKS = "NXpLKc"
45: 
46:     # Activity
47:     BARD_ACTIVITY = "ESY5D"
48: 
49:     # Status / polling
50:     STATUS_POLL = "aPya6c"
51:     ASYNC_POLL = "kwDCne"  # Deep Research progress, video gen completion
52: 
53:     # Post-processing
54:     POST_PROCESS = "PCck7e"
55: 
56:     # Page init RPCs (discovered from live capture)
57:     INIT_CONFIG = "otAQ7b"
58:     INIT_FEATURES = "GPRiHf"
59:     INIT_SETTINGS = "maGuAc"
60:     INIT_STATE = "cYRIkd"
61:     INIT_CAPABILITIES = "ozz5Z"
62:     SYNC_STATE = "L5adhe"
63:     USER_PREFS = "K4WWud"
64:     USAGE_INFO = "qpEbW"
65:     ACCOUNT_INFO = "o30O0e"
66:     HISTORY_STATE = "DYBcR"
67:     NOTIFICATION_STATE = "ku4Jyf"
68: 
69: 
70: # Header used to select the model
71: MODEL_HEADER_KEY = "x-goog-ext-525001261-jspb"
72: 
73: # Additional headers discovered from live capture
74: TRACKING_HEADER_KEY = "x-goog-ext-73010989-jspb"
75: SESSION_HEADER_KEY = "x-goog-ext-525005358-jspb"
76: 
77: 
78: # Thinking level is the second header-tail number and inner[80].
79: # Captured from the live picker on 2026-10-13: Low=1, High=2 (the old
80: # Extended thinking toggle), Medium=4.
81: THINKING_TOGGLES: dict[str, int] = {"low": 1, "medium": 4, "high": 2}
82: THINKING_LABELS: dict[str, str] = {"low": "Low", "medium": "Medium", "high": "High"}
83: _TOGGLE_TO_THINKING = {str(value): name for name, value in THINKING_TOGGLES.items()}
84: 
85: 
86: class Model:
87:     """Gemini model definitions with hashes for the model selection header."""
88: 
89:     def __init__(
90:         self,
91:         name: str,
92:         hash: str | None = None,
93:         header_tail: str = "2",
94:         extended_thinking: bool = False,
95:     ):
96:         self.name = name
97:         self.hash = hash
98:         self.header_tail = header_tail
99:         self.extended_thinking = extended_thinking
100: 
101:     @property
102:     def header(self) -> dict[str, str]:
103:         """Return the model selection header dict. Empty if no hash (unspecified model)."""
104:         if not self.hash:
105:             return {}
106:         return {
107:             MODEL_HEADER_KEY: (
108:                 f'[1,null,null,null,"{self.hash}",null,null,0,[4,5,6,8],'
109:                 f"null,null,2,null,null,{self.header_tail}]"
110:             )
111:         }
112: 
113:     @property
114:     def thinking_level(self) -> str:
115:         """``low``, ``medium``, or ``high``. Models without a pair stay low."""
116:         category, sep, toggle = self.header_tail.partition(",")
117:         if not sep or not category:
118:             return "low"
119:         return _TOGGLE_TO_THINKING.get(toggle, "low")
120: 
121:     @property
122:     def thinking_label(self) -> str:
123:         """Picker label for this model's thinking level (Low, Medium, High)."""
124:         return THINKING_LABELS[self.thinking_level]
125: 
126:     def header_tail_pair(self) -> tuple[int, int] | None:
127:         """Category and thinking-level toggle, or None when the tail is not a pair."""
128:         category, sep, toggle = self.header_tail.partition(",")
129:         if not sep:
130:             return None
131:         try:
132:             return int(category), int(toggle)
133:         except ValueError:
134:             return None
135: 
136:     def with_thinking_level(self, level: str) -> "Model":
137:         """Return this model with Google's Thinking level set.
138: 
139:         Low is 1, Medium is 4, and High is 2. High is the control formerly
140:         labeled Extended thinking.
141:         """
142:         key = level.strip().lower()
143:         try:
144:             toggle = THINKING_TOGGLES[key]
145:         except KeyError:
146:             known = ", ".join(THINKING_LABELS)
147:             raise ValueError(
148:                 f"Unknown thinking level: {level!r}. Available: {known}"
149:             ) from None
150:         if self.thinking_level == key:
151:             return self
152:         category, sep, _ = self.header_tail.partition(",")
153:         if not sep:
154:             category = "1"
155:         return Model(
156:             self.name,
157:             self.hash,
158:             header_tail=f"{category},{toggle}",
159:             extended_thinking=(key == "high"),
160:         )
161: 
162:     def with_extended_thinking(self, enabled: bool = True) -> "Model":
163:         """Return this model with Thinking level High, the old Extended toggle."""
164:         if not enabled or self.thinking_level == "high":
165:             return self
166:         return self.with_thinking_level("high")
167: 
168:     def __repr__(self) -> str:
169:         return f"Model(name={self.name!r}, hash={self.hash!r})"
170: 
171:     def __eq__(self, other: object) -> bool:
172:         if isinstance(other, Model):
173:             return self.name == other.name
174:         return NotImplemented
175: 
176:     def __hash__(self) -> int:
177:         return hash(self.name)
178: 
179: 
180: # Known model-header metadata captured from the live Gemini web UI (Oct 13, 2026).
181: # 3.8 Flash kept the fast-category hash previously labeled 3.7 and 3.6.
182: # 4 Argon is a new hash. Thinking level is the tail's second number
183: # (Low=1, Medium=4, High=2) on whichever model is selected.
184: MODELS: dict[str, Model] = {
185:     "unspecified": Model("unspecified", None),
186:     # Current models (captured from live UI model picker)
187:     "lite": Model("lite", "8c46e95b1a07cecc", header_tail="6,1"),
188:     "fast": Model("fast", "56fdd199312815e2", header_tail="1,1"),  # Gemini 3.8 Flash
189:     "thinking": Model(
190:         "thinking",
191:         "56fdd199312815e2",
192:         header_tail="1,2",
193:         extended_thinking=True,
194:     ),
195:     "pro": Model("pro", "e6fa609c3fa255c0", header_tail="3,1"),
196:     "argon": Model("argon", "argon", header_tail="8,1"),  # Gemini 4 Argon
197: }
198: 
199: # Short aliases for convenience (gemcli chat "hi" -m pro)
200: MODEL_ALIASES: dict[str, str] = {
201:     "flash-lite": "lite",
202:     "gemini-3.5-flash-lite": "lite",
203:     "gemini-3.1-flash-lite": "lite",  # previous Flash-Lite generation
204:     "flash": "fast",       # "flash" is a common alias for the fast model
205:     "preview": "fast",     # backward compat with earlier config
206:     "default": "fast",
207:     "gemini-3.8-flash": "fast",
208:     "gemini-3.8-flash-thinking": "thinking",
209:     "gemini-3.8-flash-extended": "thinking",
210:     "gemini-3.7-flash": "fast",
211:     "gemini-3.7-flash-thinking": "thinking",
212:     "gemini-3.6-flash": "fast",
213:     "gemini-3.5-flash": "fast",
214:     "gemini-3.0-flash": "fast",
215:     "gemini-3.7-flash-extended": "thinking",
216:     "gemini-3.6-thinking": "thinking",
217:     "gemini-3.5-thinking": "thinking",
218:     "gemini-3.0-flash-thinking": "thinking",
219:     "gemini-3.1-pro": "pro",
220:     "gemini-3.5-pro": "pro",
221:     "gemini-3.0-pro": "pro",
`