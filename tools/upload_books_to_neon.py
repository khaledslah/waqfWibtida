#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compress and upload all 5 Waqf & Ibtida classical books' scanned pages, Shamela text,
and Al-Nahhas (surah, ayah) -> page anchors into Neon Serverless Postgres.

All 5 editions match jamharah citations 1-to-1 (pdf_page == printed_page):
1. sajavandi / علل الوقوف (ت. العيدي 1-3): 1,218 PNGs + Shamela 30007
2. anbari    / إيضاح الوقف والابتداء (ت. رمضان 1-2): 1,199 pages + Shamela 14255
3. dani      / المكتفى (ت. المرعشلي): 704 pages
4. ashmuni   / منار الهدى (ط. الحلبي 1973): 448 pages
5. nahhas    / القطع والائتناف (ت. المطرودي): 836 pages + Shamela 20966 + ayah anchors
"""

from __future__ import annotations

import argparse
import base64
import glob
import html
import http.client
import io
import json
import re
import socket
import ssl
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

import fitz
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"d:\AI_Projects\waqfWibtida2")
ENV_PATH = ROOT / ".env"
SAJAWANDI_PNG_DIR = Path(
    r"C:\Users\Khaled\AndroidStudioProjects\WaqfWIbtida\waqf-ibtida-web\public\data\pdf_pages\sajawandi"
)
RAW_SHAMELA_DIR = Path(
    r"C:\Users\Khaled\AndroidStudioProjects\WaqfWIbtida\waqf-ibtida-web\public\data\raw_inputs"
)
PDF_SCRATCH_DIR = Path(
    r"C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch\books_pdf"
)
QAT_DIR = Path(r"D:\AI_Projects\jamharah_waqf_scraper\data\qat_itinaf\fixed_by_surah")
CATALOG_PATH = ROOT / "WaqfReader_Grok" / "assets" / "app_feed" / "catalog.json"

DEFAULT_HTTP_SQL_URL = "https://ep-twilight-rain-beikjmw9-pooler.c-9.us-east-2.aws.neon.tech/sql"


def load_neon_credentials() -> tuple[str, str]:
    conn_str = ""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k == "DATABASE_URL_POOLED":
                conn_str = v.replace("&channel_binding=require", "")
            elif k == "DATABASE_URL" and not conn_str:
                conn_str = v.replace("&channel_binding=require", "")
    if not conn_str:
        raise RuntimeError("Missing DATABASE_URL_POOLED / DATABASE_URL in .env")
    # Derive HTTP /sql URL from host in conn_str
    m = re.search(r"@([^/?:]+)", conn_str)
    http_url = f"https://{m.group(1)}/sql" if m else DEFAULT_HTTP_SQL_URL
    return http_url, conn_str


class NeonClient:
    def __init__(self, http_url: str, conn_str: str) -> None:
        self.http_url = http_url
        self.conn_str = conn_str
        parsed = urllib.parse.urlparse(http_url)
        self.host = parsed.hostname or ""
        self.port = parsed.port or 443
        self.path = parsed.path or "/sql"
        self._ssl_ctx = ssl.create_default_context()
        self._conn: http.client.HTTPSConnection | None = None
        self._ipv4_addr: str | None = None

    def _connect(self, timeout: int) -> http.client.HTTPSConnection:
        if self._ipv4_addr is None:
            infos = socket.getaddrinfo(self.host, self.port, socket.AF_INET, socket.SOCK_STREAM)
            self._ipv4_addr = infos[0][4][0]
        sock = socket.create_connection((self._ipv4_addr, self.port), timeout=timeout)
        ssock = self._ssl_ctx.wrap_socket(sock, server_hostname=self.host)
        conn = http.client.HTTPSConnection(self.host, self.port, timeout=timeout)
        conn.sock = ssock
        self._conn = conn
        return conn

    def _close_conn(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def query(self, sql: str, params: list[Any] | None = None, timeout: int = 60) -> dict[str, Any]:
        payload = json.dumps({"query": sql, "params": params or []}, ensure_ascii=False).encode("utf-8")
        headers = {
            "Host": self.host,
            "Neon-Connection-String": self.conn_str,
            "Content-Type": "text/plain; charset=utf-8",
            "User-Agent": "WaqfBookIngestor/1.0",
            "Connection": "keep-alive",
        }
        last_err: Exception | None = None
        for attempt in range(5):
            try:
                conn = self._conn
                if conn is None or conn.sock is None:
                    conn = self._connect(timeout)
                sock = conn.sock
                if sock is not None:
                    sock.settimeout(timeout)
                conn.request("POST", self.path, body=payload, headers=headers)
                resp = conn.getresponse()
                body = resp.read().decode("utf-8", errors="replace")
                if resp.status == 200:
                    return json.loads(body)
                last_err = RuntimeError(f"HTTP {resp.status}: {body[:400]}")
                self._close_conn()
                if resp.status in (429, 500, 502, 503, 504):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise last_err
            except RuntimeError:
                raise
            except Exception as e:
                last_err = e
                self._close_conn()
                time.sleep(1.0 * (attempt + 1))
        raise RuntimeError(f"Neon SQL failed after retries: {last_err}")


SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS books (
      book_key TEXT PRIMARY KEY,
      scholar_ar TEXT NOT NULL,
      title_ar TEXT NOT NULL,
      edition_ar TEXT NOT NULL,
      continuous_pagination BOOLEAN NOT NULL DEFAULT TRUE,
      total_pages INTEGER NOT NULL,
      min_page INTEGER NOT NULL DEFAULT 1,
      max_page INTEGER NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS book_pages (
      book_key TEXT NOT NULL REFERENCES books(book_key) ON DELETE CASCADE,
      vol INTEGER NOT NULL DEFAULT 1,
      page_num INTEGER NOT NULL,
      seq_index INTEGER NOT NULL,
      mime_type TEXT NOT NULL DEFAULT 'image/png',
      width INTEGER,
      height INTEGER,
      image_data BYTEA,
      page_text TEXT,
      PRIMARY KEY (book_key, vol, page_num),
      UNIQUE (book_key, seq_index)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_book_pages_key_page
      ON book_pages (book_key, page_num);
    """,
    """
    CREATE TABLE IF NOT EXISTS book_ayah_anchors (
      book_key TEXT NOT NULL REFERENCES books(book_key) ON DELETE CASCADE,
      surah INTEGER NOT NULL,
      ayah INTEGER NOT NULL,
      vol INTEGER NOT NULL DEFAULT 1,
      page_num INTEGER NOT NULL,
      end_page_num INTEGER,
      PRIMARY KEY (book_key, surah, ayah)
    );
    """,
]


def ensure_schema(client: NeonClient) -> None:
    for stmt in SCHEMA_SQL:
        client.query(stmt.strip())


def clean_shamela_text(raw: str | None) -> str | None:
    if not raw:
        return None
    s = re.sub(r"<[^>]+>", "", raw)
    s = html.unescape(s).strip()
    return s or None


def compress_grayscale_to_png4c(im_gray: Image.Image, target_width: int = 960, whiten_above: int = 225) -> tuple[bytes, int, int]:
    if im_gray.mode != "L":
        im_gray = im_gray.convert("L")
    if im_gray.width != target_width and im_gray.width > 0:
        new_h = max(1, round(im_gray.height * target_width / im_gray.width))
        im_gray = im_gray.resize((target_width, new_h), Image.Resampling.LANCZOS)
    if whiten_above < 255:
        im_gray = im_gray.point(lambda x: 255 if x > whiten_above else x)
    q = im_gray.quantize(colors=4, dither=Image.Dither.NONE)
    buf = io.BytesIO()
    q.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), im_gray.width, im_gray.height


def load_shamela_map(filename: str) -> tuple[dict[int, int], dict[int, str]]:
    """Returns (page_num -> vol, page_num -> clean_text)."""
    path = RAW_SHAMELA_DIR / filename
    if not path.exists():
        return {}, {}
    data = json.loads(path.read_text(encoding="utf-8"))
    vol_map: dict[int, int] = {}
    text_map: dict[int, str] = {}
    for entry in data.get("pages", []):
        pnum = entry.get("page")
        if not isinstance(pnum, int):
            continue
        vol = int(entry.get("vol") or 1)
        vol_map[pnum] = vol
        txt = clean_shamela_text(entry.get("text"))
        if txt:
            if pnum in text_map:
                text_map[pnum] = text_map[pnum] + "\n" + txt
            else:
                text_map[pnum] = txt
    return vol_map, text_map


BOOK_CONFIGS = [
    {
        "book_key": "sajawandi",
        "scholar_ar": "السجاوندي",
        "title_ar": "علل الوقوف",
        "edition_ar": "تحقيق د. محمد العيدي · مكتبة الرشد (٣ مجلدات)",
        "type": "png_dir",
        "path": SAJAWANDI_PNG_DIR,
        "shamela": "Al-Sajawandi-Ilal-30007.json",
        "total_pages": 1218,
    },
    {
        "book_key": "anbari",
        "scholar_ar": "ابن الأنباري",
        "title_ar": "إيضاح الوقف والابتداء",
        "edition_ar": "تحقيق د. محيي الدين رمضان · مجمع اللغة العربية بدمشق (جزءان)",
        "type": "pdf",
        "path": PDF_SCRATCH_DIR / "anbari_v2.pdf",
        "shamela": "Al-Anbari-Idah-14255.json",
        "vol_split": 561,  # 1..560 -> vol 1, 561+ -> vol 2
        "zoom": 1.6,
    },
    {
        "book_key": "dani",
        "scholar_ar": "الداني",
        "title_ar": "المكتفى في الوقف والابتدا",
        "edition_ar": "تحقيق د. يوسف المرعشلي · مؤسسة الرسالة",
        "type": "pdf",
        "path": PDF_SCRATCH_DIR / "dani_marashli.pdf",
        "shamela": None,
        "zoom": 2.1,
    },
    {
        "book_key": "ashmuni",
        "scholar_ar": "الأشموني",
        "title_ar": "منار الهدى في بيان الوقف والابتدا",
        "edition_ar": "مطبعة مصطفى البابي الحلبي · القاهرة ١٣٩٣هـ / ١٩٧٣م",
        "type": "pdf",
        "path": PDF_SCRATCH_DIR / "ashmuni_16mb.pdf",
        "shamela": None,
        "zoom": 1.85,
    },
    {
        "book_key": "nahhas",
        "scholar_ar": "النحاس",
        "title_ar": "القطع والائتناف",
        "edition_ar": "تحقيق د. عبد الرحمن المطرودي · دار عالم الكتب",
        "type": "pdf",
        "path": PDF_SCRATCH_DIR / "nahhas_matrudi.pdf",
        "shamela": "Al-Nahhas-Qatc-20966.json",
        "zoom": 2.1,
    },
]


def _vol_for_book_page(cfg: dict[str, Any], page_num: int, shamela_vols: dict[int, int]) -> int:
    key = cfg["book_key"]
    if key == "sajawandi":
        if page_num <= 444:
            return 1
        if page_num <= 811:
            return 2
        return 3
    if key == "anbari":
        return 1 if page_num < cfg["vol_split"] else 2
    return shamela_vols.get(page_num, 1)


def upsert_book_metadata(client: NeonClient, cfg: dict[str, Any], total_pages: int) -> None:
    sql = """
    INSERT INTO books (book_key, scholar_ar, title_ar, edition_ar, continuous_pagination, total_pages, min_page, max_page)
    VALUES ($1, $2, $3, $4, TRUE, $5, 1, $5)
    ON CONFLICT (book_key) DO UPDATE SET
      scholar_ar = EXCLUDED.scholar_ar,
      title_ar = EXCLUDED.title_ar,
      edition_ar = EXCLUDED.edition_ar,
      total_pages = EXCLUDED.total_pages,
      max_page = EXCLUDED.max_page;
    """
    client.query(sql, [cfg["book_key"], cfg["scholar_ar"], cfg["title_ar"], cfg["edition_ar"], total_pages])


def upload_batch_rows(client: NeonClient, rows: list[tuple[str, int, int, int, str, int, int, str, str | None]]) -> None:
    if not rows:
        return
    placeholders = []
    params: list[Any] = []
    idx = 1
    for book_key, vol, page_num, seq_index, mime_type, width, height, b64_png, page_text in rows:
        placeholders.append(
            f"(${idx}, ${idx+1}, ${idx+2}, ${idx+3}, ${idx+4}, ${idx+5}, ${idx+6}, decode(${idx+7}, 'base64'), ${idx+8})"
        )
        params.extend([book_key, vol, page_num, seq_index, mime_type, width, height, b64_png, page_text])
        idx += 9
    sql = f"""
    INSERT INTO book_pages (book_key, vol, page_num, seq_index, mime_type, width, height, image_data, page_text)
    VALUES {", ".join(placeholders)}
    ON CONFLICT (book_key, vol, page_num) DO UPDATE SET
      seq_index = EXCLUDED.seq_index,
      mime_type = EXCLUDED.mime_type,
      width = EXCLUDED.width,
      height = EXCLUDED.height,
      image_data = EXCLUDED.image_data,
      page_text = COALESCE(EXCLUDED.page_text, book_pages.page_text);
    """
    client.query(sql, params, timeout=90)


def ingest_book(client: NeonClient, cfg: dict[str, Any], batch_size: int = 12, skip_existing: bool = True, limit: int | None = None) -> None:
    key = cfg["book_key"]
    shamela_vols, shamela_texts = load_shamela_map(cfg["shamela"]) if cfg["shamela"] else ({}, {})

    if cfg["type"] == "png_dir":
        total_pages = cfg["total_pages"]
        doc = None
    else:
        doc = fitz.open(cfg["path"])
        total_pages = len(doc)

    upsert_book_metadata(client, cfg, total_pages)

    existing_pages: set[int] = set()
    if skip_existing:
        res = client.query("SELECT page_num FROM book_pages WHERE book_key = $1", [key])
        existing_pages = {int(r["page_num"]) for r in res.get("rows", [])}

    print(f"[{key}] Uploading {total_pages} pages (already in Neon: {len(existing_pages)})...")
    batch: list[tuple[str, int, int, int, str, int, int, str, str | None]] = []
    uploaded_bytes = 0
    uploaded_count = 0
    target_end = min(total_pages, limit) if limit else total_pages
    t0 = time.time()

    for pnum in range(1, target_end + 1):
        if skip_existing and pnum in existing_pages:
            continue
        if doc is None:
            png_path = Path(cfg["path"]) / f"page_{pnum}.png"
            im = Image.open(png_path).convert("L")
        else:
            pix = doc[pnum - 1].get_pixmap(
                matrix=fitz.Matrix(cfg["zoom"], cfg["zoom"]), colorspace=fitz.csGRAY
            )
            im = Image.frombytes("L", (pix.width, pix.height), pix.samples)

        png_bytes, w, h = compress_grayscale_to_png4c(im, target_width=960, whiten_above=225)
        b64 = base64.b64encode(png_bytes).decode("ascii")
        vol = _vol_for_book_page(cfg, pnum, shamela_vols)
        ptxt = shamela_texts.get(pnum)
        batch.append((key, vol, pnum, pnum, "image/png", w, h, b64, ptxt))
        uploaded_bytes += len(png_bytes)
        uploaded_count += 1

        if len(batch) >= batch_size:
            upload_batch_rows(client, batch)
            batch.clear()
            if uploaded_count % 120 < batch_size:
                elapsed = time.time() - t0
                print(
                    f"  [{key}] p.{pnum}/{target_end} uploaded={uploaded_count} "
                    f"({uploaded_bytes/1024/1024:.2f} MB) in {elapsed:.1f}s"
                )

    if batch:
        upload_batch_rows(client, batch)
        batch.clear()

    if doc is not None:
        doc.close()

    elapsed = time.time() - t0
    print(f"[{key}] DONE: newly uploaded {uploaded_count} pages ({uploaded_bytes/1024/1024:.2f} MB) in {elapsed:.1f}s")


def upload_nahhas_anchors(client: NeonClient) -> None:
    nh_path = RAW_SHAMELA_DIR / "Al-Nahhas-Qatc-20966.json"
    nh = json.loads(nh_path.read_text(encoding="utf-8"))
    nh_pages = [(int(p["page"]), p.get("text") or "") for p in nh["pages"]]
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    def norm_ar(s: str) -> str:
        s = re.sub(r"<[^>]+>", " ", s)
        s = s.replace("ٱ", "ا").replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        s = s.replace("ى", "ي").replace("ة", "ه")
        s = re.sub(r"[\u064B-\u065F\u0670\u06D6-\u06ED\u0640\u0653-\u0655]", "", s)
        s = re.sub(r"[﴿﴾\(\)\[\]«»\.،,:؛\?\!\"'\-\/\\0-9\u0660-\u0669]", " ", s)
        return " ".join(s.split())

    # Classical alternate titles used in Al-Nahhas Shamela text
    name_to_num: dict[str, int] = {}
    for x in catalog["surahs"]:
        nm = norm_ar(x["name"])
        name_to_num[nm] = x["number"]
    alt_names = {
        "فاتحه الكتاب": 1,
        "سوره الشريعه": 45,
        "سوره سال": 70,
        "سوره القران": 50,
        "سوره سبحان": 17,
        "سوره بني اسرائيل": 17,
        "سوره الملائكه": 35,
        "سوره غافر": 40,
        "سوره الطول": 40,
        "سوره فصلت": 41,
        "سوره تنزيل": 32,
        "سوره حم السجده": 41,
        "سوره حم عسق": 42,
        "سوره والذاريات": 51,
        "سوره الذاريات": 51,
        "سوره المنافقين": 63,
        "سوره المرسلات": 77,
        "سوره والنازعات": 79,
        "سوره انفطرت": 82,
        "سوره والفجر": 89,
        "سوره والشمس": 91,
        "سوره والليل": 92,
        "سوره والضحي": 93,
        "سوره الم نشرح": 94,
        "سوره والتين": 95,
        "سوره والعاديات": 100,
        "سوره والعصر": 103,
        "سوره الدين": 107,
        "سوره تبت": 111,
        "سوره الاخلاص": 112,
        "سوره التوحيد": 112,
        "سوره الفلق": 113,
        "سوره الناس": 114,
        "سوره ام القران": 1,
    }

    # Parse TOC headers monotonically in 1..114 order (fixes "سورة القلم" at 68 vs 96!)
    surah_start: dict[int, int] = {1: 28}
    last_surah = 1
    for pnum, raw_txt in nh_pages:
        if pnum < 28:
            continue
        for m in re.finditer(r"<span[^>]*>([^<]+)</span>", raw_txt):
            raw_t = norm_ar(m.group(1))
            # Strip honorific glyphs like ﷺ, ﵇
            raw_t = re.sub(r"[^\u0621-\u064A\s]", "", raw_t).strip()
            s_candidate = name_to_num.get(raw_t) or alt_names.get(raw_t)
            if not s_candidate and "محمد" in raw_t:
                s_candidate = 47
            elif not s_candidate and "نوح" in raw_t:
                s_candidate = 71
            elif not s_candidate and "الرحمن" in raw_t:
                s_candidate = 55
            elif not s_candidate and "انفطرت" in raw_t:
                s_candidate = 82
            elif not s_candidate and "القلم" in raw_t:
                s_candidate = 68 if last_surah < 68 else 96
            if s_candidate and s_candidate >= last_surah and s_candidate not in surah_start:
                surah_start[s_candidate] = pnum
                last_surah = s_candidate

    for s in range(1, 115):
        if s not in surah_start:
            surah_start[s] = max(
                [surah_start[x] for x in range(1, s) if x in surah_start],
                default=28,
            )

    nh_clean = {pnum: norm_ar(txt) for pnum, txt in nh_pages}
    qat_files = sorted(QAT_DIR.glob("surah_*.json"))
    anchors: list[tuple[str, int, int, int, int, int | None]] = []

    exact = 0
    for qf in qat_files:
        qd = json.loads(qf.read_text(encoding="utf-8"))
        s_num = int(qd["surah"])
        win_start = surah_start[s_num]
        win_end = 829
        for nxt in range(s_num + 1, 115):
            if surah_start[nxt] > win_start:
                win_end = surah_start[nxt]
                break

        entries = sorted(qd.get("entries", []), key=lambda x: x["ayah"])
        raw_matches: list[tuple[int, list[int], str]] = []
        for ent in entries:
            ay = int(ent["ayah"])
            words = norm_ar(ent["text"]).split()
            hits: list[int] = []
            for nlen in [8, 5, 3]:
                if len(words) >= nlen:
                    needle = " ".join(words[:nlen])
                    hits = [p for p in range(win_start, min(830, win_end + 1)) if needle in nh_clean.get(p, "")]
                    if hits:
                        break
            if not hits and len(words) >= 8:
                needle = " ".join(words[3:7])
                hits = [p for p in range(win_start, min(830, win_end + 1)) if needle in nh_clean.get(p, "")]
            raw_matches.append((ay, hits, ent["text"]))

        last_p = win_start
        for idx, (ay, hits, txt) in enumerate(raw_matches):
            valid = [p for p in hits if p >= last_p]
            if valid:
                chosen = valid[0]
                later_mins = [
                    min([p for p in h2 if p >= last_p], default=9999)
                    for _, h2, _ in raw_matches[idx + 1 : idx + 6]
                    if h2
                ]
                if later_mins and chosen > min(later_mins):
                    words = norm_ar(txt).split()
                    hi = min(later_mins)
                    found_bound: int | None = None
                    for nlen in [6, 4]:
                        if len(words) >= nlen:
                            needle = " ".join(words[:nlen])
                            for pnum in range(last_p, hi + 1):
                                comb = nh_clean.get(pnum, "") + " " + nh_clean.get(pnum + 1, "")
                                if needle in comb:
                                    found_bound = pnum
                                    break
                        if found_bound is not None:
                            break
                    if found_bound is not None:
                        chosen = found_bound
                        exact += 1
                    else:
                        chosen = last_p
                else:
                    exact += 1
                last_p = chosen
                p_final = chosen
            else:
                words = norm_ar(txt).split()
                found_bound = None
                for nlen in [6, 4]:
                    if len(words) >= nlen:
                        needle = " ".join(words[:nlen])
                        for pnum in range(last_p, min(830, win_end + 1)):
                            comb = nh_clean.get(pnum, "") + " " + nh_clean.get(pnum + 1, "")
                            if needle in comb:
                                found_bound = pnum
                                break
                    if found_bound is not None:
                        break
                if found_bound is not None:
                    exact += 1
                    last_p = found_bound
                    p_final = found_bound
                else:
                    p_final = last_p
            anchors.append(("nahhas", s_num, ay, 1, p_final, None))

    # Add Fatiha ayah 1 anchor fallback if missing
    if not any(a[1] == 1 and a[2] == 1 for a in anchors):
        anchors.insert(0, ("nahhas", 1, 1, 1, 28, None))

    # Batch upsert anchors
    print(f"[nahhas anchors] Upserting {len(anchors)} ayah anchors (exact text matches: {exact}/{len(anchors)})...")
    batch_sz = 200
    for i in range(0, len(anchors), batch_sz):
        chunk = anchors[i : i + batch_sz]
        phs = []
        params: list[Any] = []
        idx = 1
        for bk, s, a, v, pn, epn in chunk:
            phs.append(f"(${idx}, ${idx+1}, ${idx+2}, ${idx+3}, ${idx+4}, ${idx+5})")
            params.extend([bk, s, a, v, pn, epn])
            idx += 6
        sql = f"""
        INSERT INTO book_ayah_anchors (book_key, surah, ayah, vol, page_num, end_page_num)
        VALUES {", ".join(phs)}
        ON CONFLICT (book_key, surah, ayah) DO UPDATE SET
          vol = EXCLUDED.vol,
          page_num = EXCLUDED.page_num,
          end_page_num = EXCLUDED.end_page_num;
        """
        client.query(sql, params)
    print("[nahhas anchors] DONE!")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--books", nargs="+", default=[c["book_key"] for c in BOOK_CONFIGS])
    parser.add_argument("--no-skip", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Limit pages per book (for smoke test)")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--anchors-only", action="store_true")
    args = parser.parse_args()

    http_url, conn_str = load_neon_credentials()
    client = NeonClient(http_url, conn_str)
    ensure_schema(client)

    if args.anchors_only:
        upload_nahhas_anchors(client)
        return

    cfg_map = {c["book_key"]: c for c in BOOK_CONFIGS}
    for bk in args.books:
        if bk not in cfg_map:
            raise SystemExit(f"Unknown book key: {bk}")
        ingest_book(
            client,
            cfg_map[bk],
            batch_size=args.batch_size,
            skip_existing=not args.no_skip,
            limit=args.limit,
        )

    if "nahhas" in args.books:
        upload_nahhas_anchors(client)

    res = client.query(
        "SELECT book_key, COUNT(*) AS pages, pg_size_pretty(SUM(octet_length(image_data))::bigint) AS raw_img_size "
        "FROM book_pages GROUP BY book_key ORDER BY book_key;"
    )
    db_sz = client.query("SELECT pg_size_pretty(pg_database_size(current_database())) AS db_size;")
    print("\n=== NEON STORAGE SUMMARY ===")
    for r in res.get("rows", []):
        print(" ", r)
    print("Total DB size:", db_sz.get("rows"))


if __name__ == "__main__":
    main()
