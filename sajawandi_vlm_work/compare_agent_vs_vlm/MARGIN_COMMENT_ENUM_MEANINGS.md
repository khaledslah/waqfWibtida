# Margin-comment trial — meanings (lean)

New schema: `raw_waqf_margin_comment.schema.json`  
Does **not** replace grilled `raw_waqf_output.schema.json`.  
No `verdict_status` / `verdict_resolution` / full apparatus kinds.

## Unchanged

- `fix_type`, `fix_basis` — same grilled meanings (text repair only)
- Letter→ruling map — same (`ط→تام` …)

## Changed

### `verdict_label` / `verdict`
May be **`null`** together when the stop is visible but the letter is unresolved  
(e.g. `﴿ تعلمون - ١٥١ ﴾` with no letter in matn).  
If label is set, `verdict` must match the map. Never invent a letter without page prose (`missing_symbol` + `page_prose`).

### `margin_comments[]` (only addition)
Footnote/margin notes that **comment on this waqf bracket**. Not a scholar dump of the whole page.

| Field | Meaning |
|-------|---------|
| `text` | Literal margin note about this bracket |
| `text_page` | Page where that note appears |
| `scholar_or_work` | Optional cited name/work/witness (`النحاس`, `نسخة أ`, …); else `null` |

Use `margin_comments: []` when the margin says nothing about this stop.

## Explicitly not in this trial
`verdict_status`, `verdict_resolution`, `apparatus_source_kind`, `apparatus_note_kind`, etc.
