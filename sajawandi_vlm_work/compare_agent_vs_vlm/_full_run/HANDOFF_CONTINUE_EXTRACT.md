# Handoff — continue Sajawandi apparatus extract (Grok method)

Repo: `D:\AI_Projects\waqfWibtida2`  
Remote: `https://github.com/khaledslah/waqfWibtida.git`  
Book PDF pages **171–1182**, 4-page batches, **253** batches total.

## Current progress (as of handoff)

| Item | Value |
|------|--------|
| Done | **129** batches, pages **171–686** continuous (no gaps) |
| Next free tags | start at **`687_690`** |
| Remaining | **124** batches → through **1181_1182** |
| Last surah coverage | 1–18 full; **مريم** partial (book continues) |
| Model used | **`grok-4.7-high-fast`** (Grok 4.7) |
| Concurrency | **8** agents in parallel; when one finishes, open the next |

Outputs live at:

`sajawandi_vlm_work/compare_agent_vs_vlm/_full_run/out/batch_TAG.apparatus_v4.raw.json`

Prompts (already built):

`sajawandi_vlm_work/compare_agent_vs_vlm/_full_run/_prompts/extract_TAG.txt`

Crops:

`sajawandi_vlm_work/compare_agent_vs_vlm/_full_run/crops/page_N_matn.png`  
`sajawandi_vlm_work/compare_agent_vs_vlm/_full_run/crops/page_N_margin.png`

## Non‑negotiable rules

1. **Never overwrite** an existing `batch_TAG.apparatus_v4.raw.json`.
2. **Do not edit** prompts, schema, or enums unless the human asks.
3. One agent = one batch. Read `extract_TAG.txt` **exactly**. Open images with Read in phase order (matn → margin → Phase 3). Write **only** that output file.
4. Phases in one agent: **Phase 1 matn catalog (freeze) → Phase 2 margin → Phase 3 `suggested` only**.
5. Known Grok exception (do **not** “fix” in the prompt): on 211–214 Grok wrongly split **الجنة** (ref 1→null, empty apparatus) and invented a separate **كذلك**. Later real `كذلك` / `الجنة` stops are fine.
6. Null `verdict_label` and null `margin_ref` are often correct — leave them; don’t invent.
7. Commit only when the human asks.

## Status helpers (PowerShell, from compare dir)

```powershell
cd D:\AI_Projects\waqfWibtida2\sajawandi_vlm_work\compare_agent_vs_vlm

# next unmarked tags
python run_status.py next12 8

# mark BEFORE launching
python run_status.py mark12 687_690 691_694 ...

# inflight = marked but file missing
python -c @"
import json
from pathlib import Path
L=json.load(open('_full_run/LAUNCHED.json',encoding='utf-8'))
OUT=Path('_full_run/out')
inflight=[t for t in L['p12'] if not (OUT/f'batch_{t}.apparatus_v4.raw.json').exists()]
print(len(inflight))
print(' '.join(inflight))
"@
```

## Per-batch agent prompt (copy as-is)

```
Read the prompt file below with the Read tool and follow it EXACTLY (it is your full task):
D:\AI_Projects\waqfWibtida2\sajawandi_vlm_work\compare_agent_vs_vlm\_full_run\_prompts\extract_TAG.txt

Open page images yourself with Read in the order the prompt requires (matn first, then margin, then Phase 3).
Write ONLY the output file named in that prompt. If it already exists, STOP and report. Do not touch any other file.
Return only what the prompt asks.
```

Replace `TAG` with e.g. `687_690`.

## After the book is done

- Concatenate batches → assign surah via `sajawandi_surah_page_map.json` → map words via `quran-words.json` → flat entries for the Flutter app `WaqfReader_Grok`.
- Do **not** treat `_grok` compare sidecars as source of truth for 211–214; keep the main Sonnet file there.

---

## TEST FIRST — hardest 8 batches (before continuing 687+)

**Goal:** prove the same method on dense / trap-heavy pages **without overwriting** production files.

Write sidecars only:

`_full_run/out/batch_TAG.apparatus_v4_antigravity.raw.json`

(If your runner cannot rename the output path inside the prompt, **copy** the extract prompt to a temp file that points at the `_antigravity` output name, or stop if the main file exists and ask the human.)

### Recommended hard 8 (already extracted — compare against existing JSON)

These scored highest on density (waqfs + apparatus + opinions + suggestions + page splits):

| # | Tag | Why hard |
|---|-----|----------|
| 1 | `319_322` | dense opinions + page splits |
| 2 | `311_314` | heavy apparatus / opinions |
| 3 | `647_650` | **75** waqfs (إسراء) |
| 4 | `347_350` | dense + continuations |
| 5 | `583_586` | **63** waqfs (هود) |
| 6 | `475_478` | dense + suggestions |
| 7 | `511_514` | many notes + suggestions |
| 8 | `211_214` | **trap batch** — check الجنة/كذلك; must NOT invent split |

Also useful reference: prior Grok compare sidecars already exist for  
`183_186 191_194 195_198 199_202 203_206 207_210 211_214 215_218` as `*.apparatus_v4_grok.raw.json`.

### Test procedure

1. Launch **8 parallel** extract agents on the tags above (model **Grok 4.7** / `grok-4.7-high-fast` if available).
2. **Do not overwrite** `batch_TAG.apparatus_v4.raw.json`.
3. For each tag, diff your sidecar vs the existing main file:
   - waqf count
   - shared targets (normalize Arabic)
   - label deltas, `margin_ref` deltas
   - on **211_214**: fail the test if `الجنة` loses ref/`apparatus` or a fake `كذلك` appears
4. Report a scorecard table. Only if the human accepts quality, continue from **`687_690`** with 8-wide parallel production extracts into the normal `apparatus_v4.raw.json` names.

### Paste this to the other agent

```
You are continuing the Sajawandi علل الوقوف apparatus extract in D:\AI_Projects\waqfWibtida2.

First do a HARDNESS TEST of 8 batches (do NOT continue 687+ until I approve):

Tags: 319_322 311_314 647_650 347_350 583_586 475_478 511_514 211_214

Rules:
- Read each _full_run/_prompts/extract_TAG.txt and follow it EXACTLY (Phase 1 matn → Phase 2 margin → Phase 3 suggested).
- Open crops yourself from _full_run/crops (matn then margin).
- NEVER overwrite batch_TAG.apparatus_v4.raw.json. Write instead:
  batch_TAG.apparatus_v4_antigravity.raw.json
  (adjust only the output path; do not change extract rules).
- Run all 8 in parallel. Model: Grok 4.7 if available.
- Compare each sidecar to the existing apparatus_v4.raw.json. Scorecard: count, shared targets, labelΔ, refΔ, opsΔ.
- Special fail on 211_214: if الجنة is split wrong (ref null / empty apparatus) or a separate كذلك is invented vs the main file — report FAIL.
- Do not edit prompts/schema. Do not commit unless I ask.

After the scorecard, STOP and wait for my OK before launching production from 687_690 with 8 parallel agents (mark12 via run_status.py, never overwrite).
```
