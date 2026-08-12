# Project: Ratatoskr-mcp

## What this is
An MCP (Model Context Protocol) server that retrieves Wikipedia articles from local multistream dump files. No database, no ingest step, no internet required at query time. Named after Ratatoskr, the squirrel of Norse mythology who runs up and down Yggdrasil carrying messages.

## Objective
Sub-3-second response time for article retrieval. Currently hitting 0.3–0.6s.

## Architecture (4 files, flat — no subpackages)
- `server.py` — MCP server entry point using `fastmcp` with SSE transport. Exposes one tool: `get_wikipedia_article(topic)`.
- `index.py` — Flat-file index lookup. `find_page(title) -> (byte_offset, stream_id, title)`. Uses ripgrepy for 0.2s case-insensitive search of the 1.2GB multistream index, rapidfuzz for fuzzy fallback.
- `retrieval.py` — Orchestrates: find_page → seek bz2 block → decompress → parse → follow redirects → assemble Markdown output.
- `parser.py` — XML parsing (lxml) + wikitext parsing (mwparserfromhell). Extracts title, lead section, infobox. Detects `<redirect>` elements.

## Data flow
1. **Index lookup** (`index.py`): ripgrepy searches the plaintext index file (`byte_offset:stream_id:title` format) for the query. Exact case-sensitive match → exact case-insensitive match → fuzzy match (cluster hits by byte_offset, score each cluster with rapidfuzz word-boundary scoring).
2. **Block fetch** (`retrieval.py`): seek to byte_offset in the bz2 dump, read 32MB chunk, decompress single bz2 block.
3. **XML parse** (`parser.py`): find the matching `<page>` element (two-pass: case-sensitive then case-insensitive, to avoid grabbing redirect pages with different casing).
4. **Redirect** (`parser.py`/`retrieval.py`): if `<redirect title="X" />` present, recurse with `X` (max depth 5, loop detection via visited-title set).
5. **Extract** (`parser.py`): parse wikitext with mwparserfromhell. Extract infobox template, then lead section via `get_sections(include_lead=True, flat=True)`.
6. **Output**: `# Title\n\n{body}\n\n---\n\n{infobox}` — body first (lead section only), infobox after as reference.

## Configuration
All paths and settings via environment variables:
- `INDEX_PATH` — multistream index text file (default: `dumps/enwiki-*-index.txt`)
- `DUMP_PATH` — multistream bz2 dump file (default: `dumps/enwiki-*-multistream.xml.bz2`)
- `MCP_HOST` — bind address (default: `0.0.0.0`)
- `MCP_PORT` — port (default: `8000`)

## Dependencies
- Python 3.12+, `ripgrep` system binary (used by ripgrepy)
- See `requirements.txt`: fastmcp, lxml, mwparserfromhell, markdown, httpx, ripgrepy, rapidfuzz
- Alpine: `pip install --break-system-packages -r requirements.txt`

## Key design decisions
- **No database**: replaced SQLite FTS5 with flat-file ripgrep search. Eliminated 30-minute ingest step and 3GB DB. Tradeoff: ~0.15s slower per query (0.2s ripgrep subprocess vs 1ms SQLite) — negligible since decompression + parsing dominate.
- **Lead section only**: extracts only the text before the first `==` heading. Shorter output, no mid-section truncation.
- **Two-pass page matching** in parser: case-sensitive first, case-insensitive fallback. Prevents redirect loops where "Quantum Mechanics" (redirect page) shadows "Quantum mechanics" (article).
- **Word-boundary fuzzy scoring**: query tokens must appear as whole words in title (via set intersection), with fuzz.ratio as tiebreaker. Prevents "einstein" matching "Weinstein".

## Known limitations
- Short ambiguous queries ("Tesla", "Newton", "Voyager") resolve to disambiguation pages, not the famous article. This is fundamental — the dump has no article-importance metadata. Resolving "Einstein" and "Hubble" works via automatic redirect following.
- Non-English dumps: untested but should work if paths and index formats match.

## Testing
No test suite. Manual benchmark: `python /tmp/opencode/bench.py` runs 15 topics through the MCP client. Direct test: `python retrieval.py` fetches "Albert Einstein" and "Artificial languages".

## Environment context
- `/workspace/dumps/`: 1.2GB index text file + 24.6GB bz2 dump (bind-mounted into Docker as `/data/`)
- `/workspace/fastmcp-src/`: framework source (not vendored into the app)
- `/workspace/mwparserfromhell/`: wikitext parser library source
- `/workspace/Dockerfile` + `docker-compose.yaml`: containerized deployment with bind mount for dumps
