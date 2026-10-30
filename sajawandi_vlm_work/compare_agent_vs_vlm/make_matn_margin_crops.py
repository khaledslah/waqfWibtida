"""
Automatic matn / margin crops for the Sajawandi PDF.

matn   = top of printed text .. last text row above the footnote rule (short horizontal line)
margin = REST OF PAGE from that matn bottom to the page bottom (includes the rule + footnotes + page number)

usage:
  python make_matn_margin_crops.py START END OUT_DIR [--pdf PATH]
Writes page_N_matn.png, page_N_margin.png and CROP_META_{START}_{END}.json (never overwrites existing PNGs).
"""
import argparse
import glob
import json
from pathlib import Path

import fitz
import numpy as np
from PIL import Image

DPI = 200
DARK = 140
PAD_TOP = 14
PAD_BOT = 10
PAD_X = 30


def render(doc, p):
    pix = doc[p - 1].get_pixmap(dpi=DPI)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return img


def longest_run(row):
    best = cur = 0
    best_end = 0
    for i, v in enumerate(row):
        if v:
            cur += 1
            if cur > best:
                best, best_end = cur, i
        else:
            cur = 0
    return best, best_end


def find_rule(ink, W, H):
    """first row (y) of a thin horizontal rule: long contiguous dark run, nearly no other ink in row."""
    min_run = int(0.14 * W)
    cands = []
    for y in range(int(0.03 * H), int(0.97 * H)):
        run, end = longest_run(ink[y])
        if run >= min_run and ink[y].sum() <= run * 1.25:
            cands.append((y, run, end))
    if not cands:
        return None
    # group consecutive rows -> first row of each group
    groups = []
    for c in cands:
        if groups and c[0] - groups[-1][-1][0] <= 2:
            groups[-1].append(c)
        else:
            groups.append([c])
    return [(g[0][0], g[-1][0], max(x[1] for x in g), g[0][2]) for g in groups]


def crop_page(img):
    gray = np.array(img.convert("L"))
    H, W = gray.shape
    ink = gray < DARK
    rules = find_rule(ink, W, H)
    row_ink = ink.sum(axis=1)
    meta = {"W": W, "H": H, "rules": rules or []}
    flags = []
    if not rules:
        flags.append("no_rule")
        rule_y = None
        # fallback: first big blank gap (>=60px) between text rows, above the bottom 12% (page number)
        ys = np.where(row_ink > 3)[0]
        for a_, b_ in zip(ys[:-1], ys[1:]):
            if b_ - a_ >= 60 and b_ < int(0.88 * H):
                rule_y = int(b_) - 1
                flags.append("gap_fallback")
                break
    else:
        # footnote rule = LAST qualifying rule that sits in the upper 85% (footnote rule is the only one normally)
        rule_y = rules[0][0]
        if len(rules) > 1:
            flags.append("multi_rule")
    # y0 = first text row
    rows = np.where(row_ink > 3)[0]
    y0 = max(0, int(rows[0]) - PAD_TOP) if len(rows) else 0
    if rule_y is None:
        meta.update(y0=y0, matn_bottom=None, flags=flags)
        return None, None, meta
    above = np.where(row_ink[:rule_y - 3] > 3)[0]
    if len(above) == 0:
        flags.append("empty_matn")
        meta.update(y0=y0, matn_bottom=None, flags=flags)
        return None, None, meta
    text_bottom = int(above[-1])
    matn_bottom = min(H, text_bottom + PAD_BOT)
    y0 = max(0, int(above[0]) - PAD_TOP)
    if matn_bottom - y0 < 45:
        # stray ink / header only: no real matn on this page -> margin = full page
        flags.append("tiny_matn")
        meta.update(y0=y0, matn_bottom=matn_bottom, rule_y=rule_y, flags=flags)
        return None, None, meta
    cols = np.where(ink[y0:matn_bottom].sum(axis=0) > 0)[0]
    x0 = max(0, int(cols[0]) - PAD_X) if len(cols) else 0
    x1 = min(W, int(cols[-1]) + PAD_X) if len(cols) else W
    matn = img.crop((x0, y0, x1, matn_bottom))
    margin = img.crop((0, matn_bottom, W, H))
    meta.update(y0=y0, matn_bottom=matn_bottom, rule_y=rule_y, x0=x0, x1=x1, flags=flags,
                matn_h=matn_bottom - y0, margin_h=H - matn_bottom)
    return matn, margin, meta


def save_new(img, path):
    if path.exists():
        return False
    tmp = path.with_suffix(".tmp.png")
    img.save(tmp)
    tmp.replace(path)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start", type=int)
    ap.add_argument("end", type=int)
    ap.add_argument("out", type=str)
    ap.add_argument("--pdf", type=str, default=None)
    a = ap.parse_args()
    pdf = a.pdf or glob.glob(str(Path(__file__).resolve().parents[2] / "*.pdf"))[0]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)
    metas = []
    for p in range(a.start, a.end + 1):
        img = render(doc, p)
        matn, margin, meta = crop_page(img)
        meta["page"] = p
        if matn is not None:
            save_new(matn, out / f"page_{p}_matn.png")
            save_new(margin, out / f"page_{p}_margin.png")
        else:
            # no matn found: margin = full page so the agent can still read notes
            save_new(img, out / f"page_{p}_margin.png")
        metas.append(meta)
    mp = out / f"CROP_META_{a.start}_{a.end}.json"
    if not mp.exists():
        mp.write_text(json.dumps(metas, ensure_ascii=False, indent=1, default=int), encoding="utf-8")
    flagged = [(m["page"], m["flags"]) for m in metas if m["flags"]]
    print(f"pages={len(metas)} flagged={len(flagged)}")
    for f in flagged:
        print("  ", f)


if __name__ == "__main__":
    main()
