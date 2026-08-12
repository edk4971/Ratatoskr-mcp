import bz2
import os
from typing import Optional
from index import find_page
from parser import WikipediaParser

# Configuration
FILE_PATH = os.environ.get(
    "DUMP_PATH",
    "dumps/enwiki-20260601-pages-articles-multistream.xml.bz2",
)
WINDOW_SIZE = 32 * 1024 * 1024
MAX_WORDS = 1000
INCLUDE_INFOBOX = True

def fetch_page_content(target_title: str, _depth: int = 0, _visited: Optional[set] = None) -> Optional[str]:
    """
    Retrieves a specific Wikipedia page's content from the multistream bz2 dump.
    Returns the content as Markdown. Follows MediaWiki redirects (via the
    <redirect title="..." /> XML element) up to a small depth limit.
    Tracks visited titles to break redirect loops.
    """
    if _visited is None:
        _visited = set()

    title_key = target_title.lower().strip()
    if title_key in _visited or _depth > 5:
        print(f"DEBUG: Redirect loop or too deep for '{target_title}' (depth={_depth})")
        return None
    _visited.add(title_key)

    # 1. Find the page
    page_info = find_page(target_title)
    if not page_info:
        print(f"DEBUG: Page '{target_title}' not found in index.")
        return None

    # Schema: (byte_offset, stream_id, title)
    byte_offset, stream_id, db_title = page_info
    print(f"DEBUG: Querying title='{target_title}' -> Offset={byte_offset}, DB_title='{db_title}'")

    # 2. Seek exactly to the offset and read a chunk
    with open(FILE_PATH, 'rb') as f:
        f.seek(byte_offset)
        compressed_data = f.read(WINDOW_SIZE)

    # 3. Decompress the single block starting at this offset
    decompressor = bz2.BZ2Decompressor()
    try:
        decompressed_bytes = decompressor.decompress(compressed_data)
        print(f"DEBUG: Decompressed {len(decompressed_bytes)} bytes")
    except Exception as e:
        print(f"Decompression error at offset {byte_offset}: {e}")
        return None

    # 4. Extract ONLY the requested page using the streaming parser
    # We pass the bytes directly to the parser, which now handles wrapping in <data>
    parser = WikipediaParser(max_words=MAX_WORDS, include_infobox=INCLUDE_INFOBOX)
    parsed_title, infobox_md, body_md, redirect_to = parser.parse_page_stream(decompressed_bytes, db_title)

    # 5. Follow redirect if present
    if redirect_to:
        print(f"DEBUG: Redirect '{db_title}' -> '{redirect_to}', following (depth={_depth + 1})")
        return fetch_page_content(redirect_to, _depth=_depth + 1, _visited=_visited)

    if parsed_title:
        return f"# {parsed_title}\n\n{body_md}\n\n---\n\n{infobox_md}"

    print(f"Failed to find exact title '{target_title}' inside the block at offset {byte_offset}")
    return None

if __name__ == "__main__":
    # Test 1: Albert Einstein
    res1 = fetch_page_content("Albert Einstein")
    if res1:
        print(f"SUCCESS: Albert Einstein fetched {len(res1)} bytes.")
        print(f"Preview: {res1[:200]}...\n")
    else:
        print("FAILURE: Albert Einstein.")

    # Test 2: Artificial languages
    res2 = fetch_page_content("Artificial languages")
    if res2:
        print(f"SUCCESS: Artificial languages fetched {len(res2)} bytes.")
        print(f"Preview: {res2[:200]}...\n")
    else:
        print("FAILURE: Artificial languages.")
