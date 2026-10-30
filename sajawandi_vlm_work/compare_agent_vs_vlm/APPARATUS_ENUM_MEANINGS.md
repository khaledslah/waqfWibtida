# Apparatus raw — meanings

Files: `raw_waqf_apparatus.schema.json`, `raw_waqf_apparatus.enums.json`, `schema_definitions_apparatus.py`

## Link rule (core)

Only when the **closing waqf bracket is numbered**, e.g. `﴿خرابها - ١١٤ - ط﴾(٨)`  
and the **margin has the same number** `(٨) …`.

Then set `margin_ref: 8` and fill `apparatus` from that margin note.  
If no number on the bracket → `margin_ref: null`, `apparatus: []`.

## Waqf fields

| Field | Meaning |
|-------|---------|
| `verdict_label` | Sajawandi **letter** from matn; `null` if missing/unresolved |
| `verdict` | Mapped Sajawandi ruling; `null` with null label |
| `margin_ref` | Footnote number on/after `﴾`; else `null` |
| `fixes` | Print repairs; `missing_symbol` only if matn has no letter and margin states one |
| `apparatus` | Notes for **this** `margin_ref` only |

## `opinions[].scholar` (enum — exact JSON string)

| Enum value | Map variants such as… |
|------------|------------------------|
| `ابن الأنباري` | أبي البركات ابن الأنباري، الأنباري |
| `النحاس` | أبي جعفر النحاس |
| `الداني` | أبي عمرو الداني |
| `الأشموني` | الاشموني |
| `الأخفش` | الأخفش الأوسط |
| `الكسائي` | — |
| `مكي` | مكي بن أبي طالب |
| `العكبري` | أبي البقاء العكبري |
| `الأنصاري` | زكريا الأنصاري |
| `الطبري` | ابن جرير |
| `ابن عطية` | القاضي ابن عطية |
| `unknown` | No confident match to the list |

**Prompt rule (v4):** 1) normalize to the canonical name when it's the same person (exact spelling); 2) otherwise write the name as printed, short form, no honorifics (e.g. أبو حيان); 3) `unknown` only when the note gives no name at all. The list is now a normalization list, not a closed enum.

## `opinions[]` other fields

| Field | Meaning |
|-------|---------|
| `verdict` | Final word as stated: `حسن`, `كاف`, `تام`, … (**not** letters) |
| `comment` | Optional short note; else `null` |
| `book` | Work name; else `null` |
| `book_ref` | Locus; else `null` |

## `apparatus[]` item

`margin_ref`, `text_page`, optional `raw_text`, optional `symbol_witness`, `opinions[]`.

## margin_ref + text rules
- margin_ref = number touching closing ﴾; else the FIRST number met inside the waqf's own reasoning clause; else null.
- text = this waqf's bracket + its own reasoning clause only (not neighbouring waqfs).

## Continuation (note ends with =)
A margin note ending with = continues in the next page's margin (a block starting with =).
continuation = null (complete) | {status: read|missing, page}. When read, raw_text includes the merged continuation.

## Pass 3 — suggested (separate run)
pparatus[].suggested = null | {basis: ai_inferred, waqf: [{target_word, trigger, reason, scholars}], ibtida: [{start_word, trigger, reason, scholars}]}.
trigger = scholars_disagree | meaning_change. Written only by pass 3 into a sidecar and merged by merge_apparatus_pass3.py, which proves pass 1/2 data is unchanged.
