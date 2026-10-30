"""
Build the full-book run (pages 171..1182, batches of 4) without overwriting anything.

writes under _full_run/:
  _prompts/pass12_S_E.txt, _prompts/pass3_S_E.txt
  MANIFEST.json   (one entry per batch: start,end,prompts,outputs,status helpers)
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
    t12 = (BASE / "BLIND_APPARATUS_EXTRACT.prompt.md").read_text(encoding="utf-8")
    t3 = (BASE / "APPARATUS_SUGGEST_PASS3.prompt.md").read_text(encoding="utf-8")
    manifest = []
    for s in range(START, END + 1, BATCH):
        e = min(s + BATCH - 1, END)
        tag = f"{s}_{e}"
        notes = []
        for p in range(s, e + 1):
            m = meta[p]
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
        out12 = OUT / f"batch_{tag}.apparatus_v4.raw.json"
        out3 = OUT / f"batch_{tag}.suggest_v4.raw.json"
        p12 = (t12.replace("{{PAGE_START}}", str(s)).replace("{{PAGE_END}}", str(e))
               .replace("{{SCHEMA_PATH}}", str(BASE / "raw_waqf_apparatus.schema.json"))
               .replace("{{ENUMS_PATH}}", str(BASE / "raw_waqf_apparatus.enums.json"))
               .replace("{{MEANINGS_PATH}}", str(BASE / "APPARATUS_ENUM_MEANINGS.md"))
               .replace("{{IMAGE_DIR}}", str(CROPS))
               .replace("{{NEXT_PAGE_NOTE}}", nn)
               .replace("{{PAGE_NOTES}}", "\n".join(notes))
               .replace("{{OUTPUT_PATH}}", str(out12))
               .replace("{{SOURCE}}", f"apparatus_v4_{tag}"))
        p12 += (
            "\nEXTRA:\n"
            f"- Images only under {CROPS}.\n"
            f"- Write ONLY {out12.name}; never touch other files. Do NOT read any other JSON in this repo except the schema/enums/meanings above.\n"
            "- Strict order: Phase 1 on all matn images before any margin Read.\n"
            "- If the target output file already exists, STOP and report (never overwrite).\n"
        )
        p3 = (t3.replace("{{PAGE_START}}", str(s)).replace("{{PAGE_END}}", str(e))
              .replace("{{INPUT_PATH}}", str(out12))
              .replace("{{SCHEMA_PATH}}", str(BASE / "raw_waqf_apparatus.schema.json"))
              .replace("{{OUTPUT_PATH}}", str(out3))
              .replace("{{SOURCE}}", f"apparatus_pass3_v4_{tag}"))
        (PROMPTS / f"pass12_{tag}.txt").write_text(p12, encoding="utf-8")
        (PROMPTS / f"pass3_{tag}.txt").write_text(p3, encoding="utf-8")
        manifest.append({"start": s, "end": e, "tag": tag,
                         "pass12_prompt": str(PROMPTS / f"pass12_{tag}.txt"), "pass12_out": str(out12),
                         "pass3_prompt": str(PROMPTS / f"pass3_{tag}.txt"), "pass3_out": str(out3)})
    (RUN / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"batches={len(manifest)}")


if __name__ == "__main__":
    main()
