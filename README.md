# Ratatoskr-mcp

A high-performance MCP (Model Context Protocol) server that retrieves Wikipedia articles from local multistream dump files — no database, no ingest step, no internet required at query time.

Named after [Ratatoskr](https://en.wikipedia.org/wiki/Ratatoskr), the squirrel of Norse mythology who runs up and down the world tree Yggdrasil carrying messages between realms. Fast, persistent, and always delivering knowledge.

## What it does

Exposes a single MCP tool — `get_wikipedia_article(topic)` — that takes a Wikipedia article title and returns its content as Markdown: title, lead-section body, and infobox.

A typical request completes in **0.3–0.6 seconds**. The tool follows MediaWiki redirects automatically (e.g., "Einstein" resolves to "Albert Einstein"), and uses fuzzy matching as a fallback when exact title matching fails.

## How it works

```
topic ──▶ ripgrepy (case-insensitive fixed-string search of 1.2GB index)
      ──▶ exact match? ──▶ yes ──▶ fetch page from bz2 dump
                         ──▶ no  ──▶ cluster hits by byte_offset
                                   ──▶ rapidfuzz word-boundary scoring
                                   ──▶ best fuzzy match ──▶ fetch page
      ──▶ decompress bz2 block (bz2 module)
      ──▶ parse XML (lxml) ──▶ redirect? ──▶ follow chain (max depth 5)
                             ──▶ parse wikitext (mwparserfromhell)
                             ──▶ extract lead section + infobox
      ──▶ Markdown output
```

No database to build. No ingest step. The server searches Wikipedia's multistream index text file directly using ripgrep, and decompresses only the relevant bz2 block on demand.

## Quick start

### Prerequisites

- Docker and Docker Compose
- ~26 GB disk space for the Wikipedia dump files

### 1. Clone

```bash
git clone https://github.com/edk4971/Ratatoskr-mcp.git
cd Ratatoskr-mcp
```

### 2. Download the dump files

Download the latest English Wikipedia multistream dump into the `dumps/` directory:

```bash
mkdir -p dumps
cd dumps

# Get the two files from the latest dump date (e.g., 20260601)
# Source: https://dumps.wikimedia.org/other/mediawiki_content_current/enwiki/
wget https://dumps.wikimedia.org/other/mediawiki_content_current/enwiki/enwiki-<DATE>-pages-articles-multistream-index.txt
wget https://dumps.wikimedia.org/other/mediawiki_content_current/enwiki/enwiki-<DATE>-pages-articles-multistream.xml.bz2
```

Replace `<DATE>` with the latest dump date available on the [dump index page](https://dumps.wikimedia.org/other/mediawiki_content_current/enwiki/).

Then rename (or symlink) the files to the names the compose file expects:

```bash
ln -s enwiki-<DATE>-pages-articles-multistream-index.txt multistream-index.txt
ln -s enwiki-<DATE>-pages-articles-multistream.xml.bz2 multistream.xml.bz2
```

### 3. Run

```bash
docker compose up -d
```

The server will be available at `http://localhost:8000`.

## Configuration

All settings are controlled via environment variables (set in `docker-compose.yaml`):

| Variable | Default | Description |
|---|---|---|
| `MCP_HOST` | `0.0.0.0` | Host address to bind |
| `MCP_PORT` | `8000` | Port to listen on |
| `INDEX_PATH` | `/data/multistream-index.txt` | Path to the multistream index text file |
| `DUMP_PATH` | `/data/multistream.xml.bz2` | Path to the multistream bz2 dump file |

## Performance

Benchmarked with 15 diverse Wikipedia articles through the MCP server (SSE transport):

| Article | Time | Size |
|---|---|---|
| Burj Khalifa | 0.37s | 3,938 chars |
| Nikola Tesla | 0.51s | 4,021 chars |
| Hubble Space Telescope | 0.51s | 5,640 chars |
| Isaac Newton | 0.60s | 7,527 chars |
| Leonardo da Vinci | 0.53s | 4,177 chars |
| Kyoto | 0.40s | 7,622 chars |

All requests completed in **under 1 second**, well within the sub-3-second target. Times include index lookup, bz2 decompression, XML parsing, wikitext extraction, and redirect resolution.

## Using with an MCP client

The server speaks the MCP protocol over SSE. Point any MCP-compatible client at:

```
http://localhost:8000/sse
```

The single exposed tool is:

- **`get_wikipedia_article(topic: str) -> str`** — Returns the article as Markdown, or an error message if not found.

## Project structure

```
├── server.py          — MCP server entry point (fastmcp, SSE transport)
├── index.py           — Flat-file index search (ripgrepy + rapidfuzz)
├── retrieval.py       — bz2 block fetching + output assembly + redirect following
├── parser.py          — Wikipedia XML/wikitext parsing (lxml + mwparserfromhell)
├── Dockerfile
├── docker-compose.yaml
└── requirements.txt
```

## Running without Docker

Requires Python 3.12+ and `ripgrep` installed on the system.

```bash
pip install -r requirements.txt

# Set paths to your dump files
export INDEX_PATH=./dumps/enwiki-20260601-pages-articles-multistream-index.txt
export DUMP_PATH=./dumps/enwiki-20260601-pages-articles-multistream.xml.bz2

python server.py
```

## License

MIT
