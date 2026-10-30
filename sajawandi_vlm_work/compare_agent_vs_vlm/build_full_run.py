"""
Build the full-book run (pages 171..1182, batches of 4) without overwriting anything.

One agent per batch does Phase 1 (matn) → Phase 2 (margin) → Phase 3 (suggested) and writes
one apparatus JSON. Optional pass3_* prompts remain only for backfilling batches already
extracted without Phase 3.

writes under _full_run/:
  _prompts/extract_S_E.txt   (primary)
  _prompts/pass3_S_E.txt     (backfill only)
  MANIFEST.json
"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
RUN = BASE / "_full_run"
CROPS = RUN / "crops"
OUT = RUN / "out"
PROMPTS = RUN / "_prompts"
START, END, BATCH = 171, 1182, 4


def main():
    OUT.mkdir(exist_ok=True)
    PROMPTS.mkdir(exist_ok=True)
    meta = {m["page"]: m for m in json.load(open(CROPS / f"CROP_META_{START}_{END}.json", encoding="utf-8"))}
    t_extract = (BASE / "BLIND_APPARATUS_EXTRACT.prompt.md").read_text(encoding="utf-8")
    t3 = (BASE / "APPARATUS_SUGGEST_PASS3.prompt.md").read_text(encoding="utf-8")
    manifest = []
    for s in range(START, END + 1, BATCH):
        e = min(s + BATCH - 1, END)
        tag = f"{s}_{e}"
        notes = []
        for p in range(s, e + 1):
            if not (CROPS / f"page_{p}_matn.png").exists():
                notes.append(
                    f"- page {p}: NO matn crop exists (no catalog block detected). The full page is page_{p}_margin.png. "
                    f"If the top of that page shows waqf brackets (﴿word - ayah - letter﴾) treat them as this page's matn "
                    f"(Phase 1); otherwise this page has zero waqfs and its notes still join via continuation."
                )
        nxt = e + 1
        if nxt <= END and (CROPS / f"page_{nxt}_margin.png").exists():
            nn = (f"- page_{nxt}_margin.png — ONLY for '=' continuations of notes on page {e} "
                  f"(do NOT extract any waqf from page {nxt}).")
        else:
            nn = f"- (no page {nxt} margin available: notes ending with = on page {e} get continuation.status=missing)"
        out = OUT / f"batch_{tag}.apparatus_v4.raw.json"
        out3 = OUT / f"batch_{tag}.suggest_v4.raw.json"
        p_extract = (t_extract.replace("{{PAGE_START}}", str(s)).replace("{{PAGE_END}}", str(e))
                     .replace("{{SCHEMA_PATH}}", str(BASE / "raw_waqf_apparatus.schema.json"))
                     .replace("{{ENUMS_PATH}}", str(BASE / "raw_waqf_apparatus.enums.json"))
                     .replace("{{MEANINGS_PATH}}", str(BASE / "APPARATUS_ENUM_MEANINGS.md"))
                     .replace("{{IMAGE_DIR}}", str(CROPS))
                     .replace("{{NEXT_PAGE_NOTE}}", nn)
                     .replace("{{PAGE_NOTES}}", "\n".join(notes))
                     .replace("{{OUTPUT_PATH}}", str(out))
                     .replace("{{SOURCE}}", f"apparatus_v4_{tag}"))
        p_extract += (
            "\nEXTRA:\n"
            f"- Images only under {CROPS}.\n"
            f"- Write ONLY {out.name}; never touch other files. Do NOT read any other JSON in this repo except the schema/enums/meanings above.\n"
            "- Strict order: Phase 1 (all matn) → Phase 2 (margins) → Phase 3 (suggested only).\n"
            "- If the target output file already exists, STOP and report (never overwrite).\n"
        )
        nm = CROPS / f"page_{nxt}_matn.png"
        if nxt <= END and nm.exists():
            p_extract += (
                "\nBOUNDARY RULE (important):\n"
                f"- A waqf bracket that OPENS on page {e} but whose closing letter/clause continues on page {nxt} BELONGS TO THIS BATCH: "
                f"include it (text_page={e}, add a page_split fix). Read {nm} ONLY to complete that one waqf "
                f"(matn text of page {nxt} only up to the end of that clause); extract nothing else from page {nxt}.\n"
                f"- Conversely, a fragment at the very top of page {s} that is the tail of a bracket opened on page {s - 1} "
                f"belongs to the previous batch: skip it.\n"
            )
        # backfill-only prompt (for batches already extracted without Phase 3)
        p3 = (t3.replace("{{PAGE_START}}", str(s)).replace("{{PAGE_END}}", str(e))
              .replace("{{INPUT_PATH}}", str(out))
              .replace("{{SCHEMA_PATH}}", str(BASE / "raw_waqf_apparatus.schema.json"))
              .replace("{{OUTPUT_PATH}}", str(out3))
              .replace("{{SOURCE}}", f"apparatus_pass3_v4_{tag}"))
        # keep old pass12_* name as alias so already-launched jobs still find a path; primary is extract_*
        (PROMPTS / f"extract_{tag}.txt").write_text(p_extract, encoding="utf-8")
        (PROMPTS / f"pass12_{tag}.txt").write_text(p_extract, encoding="utf-8")
        (PROMPTS / f"pass3_{tag}.txt").write_text(p3, encoding="utf-8")
        manifest.append({
            "start": s, "end": e, "tag": tag,
            "extract_prompt": str(PROMPTS / f"extract_{tag}.txt"),
            "pass12_prompt": str(PROMPTS / f"pass12_{tag}.txt"),
            "pass12_out": str(out),
            "pass3_prompt": str(PROMPTS / f"pass3_{tag}.txt"),
            "pass3_out": str(out3),
            "note": "one agent: phases 1+2+3 → pass12_out; pass3_* is backfill only",
        })
    (RUN / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"batches={len(manifest)}")


if __name__ == "__main__":
    main()
