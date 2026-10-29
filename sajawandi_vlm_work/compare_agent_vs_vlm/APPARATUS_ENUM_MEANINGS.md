# Apparatus trial — enum meanings

Standalone glossary. Does not change the grilled pipeline schema.

## `verdict_label` (Sajawandi letter in bracket)

| Value | Meaning |
|-------|---------|
| `ط` | مطلق / تام — full stop allowed; speech complete |
| `م` | لازم — must stop; harmful to connect |
| `ج` | جائز — pause allowed; either stop or continue OK |
| `ز` | مجوز لوجه — allowed for a stated reason/face (maps to جائز) |
| `ص` | مرخص ضرورة — licensed/hasan pause (maps to حسن) |
| `لا` | لا يوقف — do not stop here |
| `ق` | قيل فيه وقف — some said there is a stop (reported, not primary) |
| `null` | **Trial only:** letter not printed / not safely known yet |

## `verdict` (mapped ruling string)

| Value | Meaning |
|-------|---------|
| `تام` | Complete stop (from `ط`) |
| `لازم` | Obligatory stop (from `م`) |
| `جائز` | Permissible stop (from `ج` or `ز`) |
| `حسن` | Good / licensed pause (from `ص`) |
| `لا يوقف` | No stop (from `لا`) |
| `قيل فيه وقف` | Reported stop opinion (from `ق`) |
| `null` | **Trial only:** no mapped ruling because label is null |

## `verdict_status`

| Value | Meaning |
|-------|---------|
| `resolved` | One clear letter for this stop (from matn and/or margin prose) |
| `unresolved` | Stop is real (e.g. `﴿تعلمون - ١٥١﴾`) but no letter yet — do not invent |
| `contested` | Conflict: dual letters (`ج ز`), or margin vs matn, or scholars disagree |

## `verdict_resolution_basis`

| Value | Meaning |
|-------|---------|
| `matn_symbol` | Letter taken from the matn catalog bracket itself |
| `page_prose` | Letter taken from explicit commentary (usually margin): e.g. “الرمز ج عن النسخة أ” |
| `dual_matn_symbol` | Matn prints two letters together (`ج ز`) — typically → `contested` |
| `unresolved` | No letter chosen; waiting / insufficient page evidence |

## `fix_type` (repair of printed text)

| Value | Meaning |
|-------|---------|
| `page_split` | Bracket/taʿlīl cut across pages; stitch continuation |
| `missing_delimiter` | Missing `-` / structure around ayah/label in bracket |
| `missing_symbol` | Letter absent in print; restore **only** if prose states it |
| `orthography` | Typos / stuck letters (لعدف→لعطف, etc.) |
| `ayah_number_correction` | Wrong ayah digit in bracket vs page evidence |
| `malformed_bracket` | Broken `﴿ ﴾` / mangled bracket form |

## `fix_basis`

| Value | Meaning |
|-------|---------|
| `page_prose` | Change justified by words on the page (matn or margin commentary) |
| `editor_policy` | Structural/editorial join (page split, delimiters) without inventing a ruling letter |

## `apparatus_source_kind` (where the note was read)

| Value | Meaning |
|-------|---------|
| `margin` | Footnote / hashiya below the separator rule |
| `matn_aside` | Inside matn taʿlīl but not a catalog letter line (e.g. “والوقف على ﴿تعلمون - ١٥١﴾”) |
| `header` | Page header / running title if it carries relevant witness |

## `apparatus_note_kind` (what the note is doing)

| Value | Meaning |
|-------|---------|
| `symbol_witness` | Attests or restores a waqf **letter** (نسخة أ = ج) |
| `scholar_opinion` | Named scholar’s view on the stop/grammar |
| `work_citation` | Citation of a book (إعراب القرآن, مشكل …) |
| `variant` | Manuscript/print variant not solely a letter restore |
| `other` | Useful margin text that doesn’t fit above |

## `known_scholar_or_work` (optional short names)

| Value | Meaning |
|-------|---------|
| `النحاس` | Abū Jaʿfar al-Naḥḥās (often إعراب القرآن) |
| `الداني` | Abū ʿAmr al-Dānī (waqf/ibtidāʾ tradition) |
| `الأخفش` | Al-Akhfash (معاني القرآن) |
| `الكسائي` | Al-Kisāʾī |
| `مكي` | Makkī (مشكل إعراب القرآن) |
| `ابن الأنباري` | Ibn al-Anbārī (البيان / غريب الإعراب) |
| `العكبري` | Al-ʿUkbarī (الإملاء) |
| `نسخة أ` | Editor’s manuscript witness أ in this edition |
| `نسخة ب` | Editor’s manuscript witness ب |
| `unknown` | Name/work not identified; put raw text in `apparatus.text` |

Free text is still allowed when the page names someone outside this list.
