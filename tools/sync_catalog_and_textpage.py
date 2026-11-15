#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Refresh catalog.json counts and backfill `textPage` across all 114 surahs
in WaqfReader_Grok/assets/app_feed and build/flutter_assets/assets/app_feed.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"d:\AI_Projects\waqfWibtida2")
FEED_DIR = ROOT / "WaqfReader_Grok" / "assets" / "app_feed"
BUILD_FEED_DIR = ROOT / "WaqfReader_Grok" / "build" / "flutter_assets" / "assets" / "app_feed"
BASE_FEED_DIR = Path(r"D:\AI_Projects\jamharah_waqf_scraper\app_workspace\data\base_app_feed")


def _write_text_safe(path: Path, content: str) -> None:
    """Write via a sibling temp file with brief retries for transient Windows Errno 22 locks."""
    tmp = path.with_name(f"{path.name}.tmp")
    for attempt in range(1, 6):
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)
            os.replace(tmp, path)
            return
        except OSError as exc:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            if attempt >= 5 or (exc.errno not in (22, 13) and not isinstance(exc, PermissionError)):
                raise
            time.sleep(0.5 * attempt)


def parse_sajawandi_page(raw: str | None) -> int | None:
    if not raw:
        return None
    s = str(raw).strip()
    # Handle leading "vol/page..." (e.g. "1/173", "1/173-179", "3/848") vs "1027-1029/3"
    m_vol = re.match(r"^\s*([1-9])\s*/\s*(\d+)", s)
    if m_vol:
        val = int(m_vol.group(2))
    else:
        m = re.search(r"(\d+)", s)
        if not m:
            return None
        val = int(m.group(1))
    # Printed pages for Ilal al-Wuquf run 1..1218
    if 1 <= val <= 1300:
        return val
    return None


def main() -> None:
    catalog_path = FEED_DIR / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    updated_surahs = 0
    total_stops = 0
    tp_from_saj_op = 0
    tp_from_base = 0
    tp_null = 0
    catalog_changes = 0

    for entry in catalog["surahs"]:
        s = entry["number"]
        surah_path = FEED_DIR / f"surah_{s:03d}.json"
        sd = json.loads(surah_path.read_text(encoding="utf-8"))

        base_path = BASE_FEED_DIR / f"surah_{s:03d}.json"
        base_tp: dict[tuple[int, int], int] = {}
        if base_path.exists():
            bd = json.loads(base_path.read_text(encoding="utf-8"))
            for bst in bd.get("stops", []):
                btp = bst.get("textPage")
                if isinstance(btp, int) and btp > 0:
                    base_tp[(bst["ayah"], bst["wordIndex"])] = btp

        surah_modified = False
        for st in sd.get("stops", []):
            total_stops += 1
            saj_op = next(
                (
                    o
                    for o in st.get("opinions", [])
                    if "السجاوندي" in (o.get("scholar") or "")
                    or "علل الوقوف" in (o.get("book") or "")
                ),
                None,
            )
            parsed_tp = parse_sajawandi_page(saj_op.get("page") if saj_op else None)
            if parsed_tp is not None:
                new_tp: int | None = parsed_tp
                tp_from_saj_op += 1
            else:
                b_val = base_tp.get((st["ayah"], st["wordIndex"]))
                if b_val is not None:
                    new_tp = b_val
                    tp_from_base += 1
                else:
                    new_tp = None
                    tp_null += 1

            if st.get("textPage") != new_tp:
                st["textPage"] = new_tp
                surah_modified = True

        actual_stops = len(sd.get("stops", []))
        actual_uthmani = sum(1 for st in sd.get("stops", []) if st.get("inUthmaniMushaf"))
        if entry["stopCount"] != actual_stops or entry["uthmaniStopCount"] != actual_uthmani:
            print(
                f"Catalog diff Surah {s:3d} ({entry['name']}): "
                f"stops {entry['stopCount']}->{actual_stops}, "
                f"uthmani {entry['uthmaniStopCount']}->{actual_uthmani}"
            )
            entry["stopCount"] = actual_stops
            entry["uthmaniStopCount"] = actual_uthmani
            catalog_changes += 1

        if surah_modified:
            updated_surahs += 1
            text_out = json.dumps(sd, ensure_ascii=False, indent=2)
            _write_text_safe(surah_path, text_out)
            if BUILD_FEED_DIR.exists():
                _write_text_safe(BUILD_FEED_DIR / f"surah_{s:03d}.json", text_out)

    cat_out = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    _write_text_safe(catalog_path, cat_out)
    if BUILD_FEED_DIR.exists():
        _write_text_safe(BUILD_FEED_DIR / "catalog.json", cat_out)

    print(
        f"Done! Updated textPage on {updated_surahs} surah files "
        f"(total stops={total_stops}: {tp_from_saj_op} from Sajawandi opinion, "
        f"{tp_from_base} from base_app_feed, {tp_null} null). "
        f"Catalog entries updated: {catalog_changes}."
    )


if __name__ == "__main__":
    main()
