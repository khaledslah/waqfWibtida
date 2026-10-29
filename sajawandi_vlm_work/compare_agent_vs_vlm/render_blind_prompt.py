#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fill BLIND_MATN_EXTRACT.prompt.md for one batch or a JOBS.json list."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE / "BLIND_MATN_EXTRACT.prompt.md"
DEFAULT_SCHEMA = HERE / "raw_waqf_output.schema.json"
DEFAULT_SCRIPT = HERE.parent.parent / "extract_sajawandi_local_vlm.py"


def render(
    *,
    page_start: int,
    page_end: int,
    image_dir: Path,
    output_path: Path,
    source: str,
    template: Path = DEFAULT_TEMPLATE,
    schema_path: Path = DEFAULT_SCHEMA,
    script_path: Path = DEFAULT_SCRIPT,
) -> str:
    text = template.read_text(encoding="utf-8")
    reps = {
        "{{PAGE_START}}": str(page_start),
        "{{PAGE_END}}": str(page_end),
        "{{SCHEMA_PATH}}": str(schema_path),
        "{{SCRIPT_PATH}}": str(script_path),
        "{{IMAGE_DIR}}": str(image_dir),
        "{{OUTPUT_PATH}}": str(output_path),
        "{{SOURCE}}": source,
    }
    for k, v in reps.items():
        text = text.replace(k, v)
    return text


def job_images(image_dir: Path, start: int, end: int) -> list[str]:
    return [str(image_dir / f"page_{p}_matn.png") for p in range(start, end + 1)]


def main() -> None:
    p = argparse.ArgumentParser(description="Render blind matn extract prompts")
    p.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    p.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    p.add_argument("--script", type=Path, default=DEFAULT_SCRIPT)
    p.add_argument("--image-dir", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, default=None, help="Write prompt_*.txt here")
    p.add_argument("--jobs", type=Path, default=None, help="JOBS.json list")
    p.add_argument("--start", type=int, default=None)
    p.add_argument("--end", type=int, default=None)
    p.add_argument("--output", type=Path, default=None, help="Raw JSON path (single job)")
    p.add_argument("--source", type=str, default="parallel8")
    p.add_argument("--control-start", type=int, default=None, help="Mark this start as *_control")
    p.add_argument("--print", action="store_true", help="Print single prompt to stdout")
    args = p.parse_args()

    jobs: list[dict] = []
    if args.jobs:
        jobs = json.loads(args.jobs.read_text(encoding="utf-8"))
    elif args.start is not None and args.end is not None:
        out = args.output or (
            args.image_dir / f"batch_{args.start}_{args.end}.parallel.raw.json"
        )
        jobs = [
            {
                "start": args.start,
                "end": args.end,
                "pages": list(range(args.start, args.end + 1)),
                "images": job_images(args.image_dir, args.start, args.end),
                "output": str(out),
            }
        ]
    else:
        p.error("Provide --jobs or both --start and --end")

    out_dir = args.out_dir or args.image_dir / "_prompts"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []

    for job in jobs:
        start, end = int(job["start"]), int(job["end"])
        output = Path(job.get("output") or (args.image_dir / f"batch_{start}_{end}.parallel.raw.json"))
        images = job.get("images") or job_images(args.image_dir, start, end)
        source = args.source
        if args.control_start is not None and start == args.control_start:
            source = f"{args.source}_control"
        prompt = render(
            page_start=start,
            page_end=end,
            image_dir=args.image_dir,
            output_path=output,
            source=source,
            template=args.template,
            schema_path=args.schema,
            script_path=args.script,
        )
        prompt_path = out_dir / f"prompt_{start}_{end}.txt"
        prompt_path.write_text(prompt, encoding="utf-8", newline="\n")
        entry = {
            "start": start,
            "end": end,
            "pages": job.get("pages") or list(range(start, end + 1)),
            "images": images,
            "output": str(output),
            "source": source,
            "prompt_file": str(prompt_path),
            "description": f"Parallel {start}-{end}",
        }
        manifest.append(entry)
        if args.print and len(jobs) == 1:
            print(prompt)

    man_path = out_dir / "PROMPT_MANIFEST.json"
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(manifest)} prompts → {out_dir}")
    print(f"Manifest → {man_path}")


if __name__ == "__main__":
    main()
