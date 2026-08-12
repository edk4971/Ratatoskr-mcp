"""
Flat-file index lookup using ripgrepy + rapidfuzz.
Replaces the SQLite FTS5 approach — no ingest step, no database to manage.

The Wikipedia multistream index file (1.2GB plaintext) has the format:
    byte_offset:stream_id:title

Lookup strategy (tiered):
    1. Exact match (case-insensitive) — ripgrep fixed-string search, then
       Python-side exact comparison on the title field.
    2. Fuzzy match — cluster hits by byte_offset, score each cluster's titles
       with rapidfuzz using word-boundary-aware scoring, return the best.

Redirects are NOT handled here — they are detected at XML parse time in
parser.py and followed by retrieval.py.
"""
import os
from collections import defaultdict
from typing import Optional, Tuple

from ripgrepy import Ripgrepy
from rapidfuzz import fuzz

INDEX_PATH = os.environ.get(
    "INDEX_PATH",
    "dumps/enwiki-20260601-pages-articles-multistream-index.txt",
)


def _search_index(query: str) -> list[Tuple[int, str, str]]:
    """
    Runs a case-insensitive fixed-string ripgrep search on the index file.
    Returns a list of (byte_offset, stream_id, title) tuples.
    """
    rg = Ripgrepy(query, INDEX_PATH).i().F()
    raw = rg.run().as_string

    hits = []
    for line in raw.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        try:
            offset = int(parts[0])
        except ValueError:
            continue
        stream_id = parts[1]
        title = parts[2]
        hits.append((offset, stream_id, title))

    return hits


def find_page(title: str) -> Optional[Tuple[int, int, str]]:
    """
    Finds a page in the multistream index using tiered matching:
    1. Exact match (case-insensitive)
    2. Fuzzy match via offset-clustering + rapidfuzz

    Returns (byte_offset, stream_id, title) or None if not found.
    """
    if not title or not title.strip():
        return None

    title = title.strip()
    hits = _search_index(title)

    if not hits:
        return None

    # 1. Exact match — pass 1: case-sensitive (prevents redirect loops
    #    where "Tesla" matches "TESLA" which redirects back to "Tesla")
    for offset, stream_id, hit_title in hits:
        if hit_title == title:
            sid = int(stream_id) if stream_id.isdigit() else 0
            return (offset, sid, hit_title)

    # 1. Exact match — pass 2: case-insensitive fallback
    title_lower = title.lower()
    for offset, stream_id, hit_title in hits:
        if hit_title.lower().strip() == title_lower:
            sid = int(stream_id) if stream_id.isdigit() else 0
            return (offset, sid, hit_title)

    # 2. Fuzzy match: cluster by byte_offset, score each cluster
    clusters = defaultdict(list)
    for offset, stream_id, hit_title in hits:
        clusters[offset].append((stream_id, hit_title))

    best = None  # (score, offset, title, stream_id)
    for offset, members in clusters.items():
        cluster_best_score = -1.0
        cluster_best_title = None
        cluster_best_sid = "0"
        for stream_id, hit_title in members:
            # Word-boundary-aware scoring:
            # If all query tokens appear as whole words in the title, give a
            # high base score (0.5–1.0) and use fuzz.ratio as a tiebreaker.
            # Otherwise, cap the score low (0–0.4) so word matches always win.
            q_tokens = set(title_lower.split())
            t_tokens = set(hit_title.lower().split())
            if q_tokens and q_tokens.issubset(t_tokens):
                score = 0.5 + 0.5 * (fuzz.ratio(title, hit_title) / 100.0)
            else:
                score = 0.4 * (fuzz.ratio(title, hit_title) / 100.0)

            if score > cluster_best_score:
                cluster_best_score = score
                cluster_best_title = hit_title
                cluster_best_sid = stream_id

        if best is None or cluster_best_score > best[0]:
            best = (cluster_best_score, offset, cluster_best_title, cluster_best_sid)

    if best:
        _, offset, best_title, best_sid = best
        sid = int(best_sid) if best_sid.isdigit() else 0
        return (offset, sid, best_title)

    return None
