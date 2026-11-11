#!/usr/bin/env python3
"""Sync user-submitted 1-tap Waqf reports from Neon Serverless Postgres into data/flagged_waqfs.json."""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
FLAGGED_JSON_PATH = ROOT / "data" / "flagged_waqfs.json"
ENV_PATH = ROOT / ".env"

DEFAULT_NEON_CONN = (
    "postgresql://neondb_owner:npg_jdiUHBFP40bT@"
    "ep-twilight-rain-beikjmw9-pooler.c-9.us-east-2.aws.neon.tech/"
    "neondb?sslmode=require"
)


def _load_env() -> dict[str, str]:
    env = dict(os.environ)
    if ENV_PATH.is_file():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def _neon_sql(conn_str: str, query: str, params: list | None = None) -> list[dict]:
    # Strip channel_binding=require for HTTP SQL proxy compatibility
    clean_conn = conn_str.replace("&channel_binding=require", "").replace(
        "?channel_binding=require&", "?"
    )
    parsed = urllib.parse.urlparse(clean_conn)
    host = parsed.hostname
    if not host:
        raise ValueError(f"Invalid Neon connection string: {conn_str}")
    endpoint = f"https://{host}/sql"
    req = urllib.request.Request(
        endpoint,
        data=json.dumps({"query": query, "params": params or []}).encode("utf-8"),
        headers={
            "Neon-Connection-String": clean_conn,
            "Content-Type": "text/plain; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("rows") or []


def main() -> None:
    env = _load_env()
    conn_str = (
        env.get("DATABASE_URL_POOLED")
        or env.get("DATABASE_URL")
        or DEFAULT_NEON_CONN
    ).strip()

    existing: dict = {
        "sentToReview": [],
        "favorites": [],
        "verified": [],
        "flaggedDetails": {},
        "updatedAt": None,
    }
    if FLAGGED_JSON_PATH.is_file():
        try:
            existing = json.loads(FLAGGED_JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Ensure table exists
    _neon_sql(
        conn_str,
        """
        CREATE TABLE IF NOT EXISTS waqf_reports (
          id SERIAL PRIMARY KEY,
          stop_id TEXT NOT NULL,
          surah INTEGER NOT NULL,
          surah_name TEXT NOT NULL,
          ayah INTEGER NOT NULL,
          word_index INTEGER NOT NULL DEFAULT 1,
          word TEXT NOT NULL,
          flagged BOOLEAN NOT NULL DEFAULT TRUE,
          scholar_filter TEXT,
          opinions_summary TEXT,
          client_id TEXT NOT NULL DEFAULT 'anon',
          platform TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE (stop_id, client_id)
        );
        """,
    )

    # Push any local flaggedDetails that aren't in Neon yet
    local_details = existing.get("flaggedDetails") or {}
    for stop_id, info in local_details.items():
        if not isinstance(info, dict):
            continue
        _neon_sql(
            conn_str,
            """
            INSERT INTO waqf_reports (
              stop_id, surah, surah_name, ayah, word_index, word,
              flagged, client_id, platform, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            ON CONFLICT (stop_id, client_id) DO NOTHING;
            """,
            [
                stop_id,
                int(info.get("surah") or 0),
                str(info.get("surahName") or ""),
                int(info.get("ayah") or 0),
                int(info.get("wordIndex") or 1),
                str(info.get("word") or ""),
                bool(info.get("flagged", True)),
                str(info.get("clientId") or "local-dev"),
                str(info.get("platform") or "local"),
            ],
        )

    rows = _neon_sql(
        conn_str,
        "SELECT * FROM waqf_reports ORDER BY updated_at ASC, id ASC",
    )

    sent_set: set[str] = set()
    details: dict[str, dict] = dict(local_details)

    for r in rows:
        stop_id = r.get("stop_id")
        if not stop_id:
            continue
        flagged = bool(r.get("flagged", True))
        if flagged:
            sent_set.add(stop_id)
            details[stop_id] = {
                "id": stop_id,
                "surah": r.get("surah"),
                "surahName": r.get("surah_name"),
                "ayah": r.get("ayah"),
                "wordIndex": r.get("word_index", 1),
                "word": r.get("word"),
                "flagged": True,
                "scholarFilter": r.get("scholar_filter"),
                "opinionsSummary": r.get("opinions_summary"),
                "clientId": r.get("client_id"),
                "platform": r.get("platform"),
                "reportedAt": r.get("updated_at") or r.get("created_at"),
            }
        else:
            sent_set.discard(stop_id)
            if stop_id in details:
                details[stop_id]["flagged"] = False

    existing["sentToReview"] = sorted(sent_set)
    existing["flaggedDetails"] = {
        k: v
        for k, v in details.items()
        if k in sent_set
        or k in set(existing.get("favorites") or [])
        or k in set(existing.get("verified") or [])
    }
    existing["updatedAt"] = datetime.now(timezone.utc).isoformat()

    FLAGGED_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    FLAGGED_JSON_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Synced {len(rows)} Neon DB row(s) -> {len(sent_set)} active flagged stop(s) in {FLAGGED_JSON_PATH}"
    )
    for stop_id in sorted(sent_set):
        d = existing["flaggedDetails"].get(stop_id, {})
        print(
            f"  - [{stop_id}] {d.get('surahName')} ({d.get('surah')}:{d.get('ayah')}) "
            f"word='{d.get('word')}' client='{d.get('clientId')}' platform='{d.get('platform')}'"
        )


if __name__ == "__main__":
    main()
