# Scopus plugin

> **⚠ Currently broken.** Scopus changed its site, and search parameters are no longer passed
> as a GET request. The parser in this plugin relied on that GET encoding.

A plugin for the [Collaborative Scraper server](https://github.com/Angelo942/collaborative_scraper_server)
that crawls **scientific literature** and reconstructs the **citation graph** between papers.

It provides the three extension points the server asks of a plugin:

- a **parser** for [Scopus](https://www.scopus.com) result and article pages,
- four **scrapers** (crawling strategies) that decide which paper to follow next,
- a **database** storing the papers and the citation links between them.

The server is generic: it speaks the protocol with the browser extension and holds the crawl
state. This plugin is what makes it collect citation networks. Volunteers simply browse
Scopus with the extension, and the server tells them which page to open next.

Requires server **2.0 or later**.

---

## What it collects

For every paper it stores the basic metadata (id, title, year, PDF/link) plus both directions
of the citation relationship:

- **citing** — the papers that *cite* this one,
- **cited** — the papers this one *references*.

Following these links outward from a starting point grows a connected graph of related
literature.

---

## Installation

The plugin is an ordinary pip-installable distribution. Nothing in the server is edited: it
declares a `collaborative_scraper.plugins` entry point, and the server discovers it at
startup.

```bash
pip install -e /path/to/plugin-scopus
```

Check that it was picked up:

```bash
python3 -m collaborative_scraper.server --list-plugins
python3 -m collaborative_scraper.server --list-targets
```

If `scopus:*` targets are missing, the plugin failed to load. Failures are logged and
skipped, never raised — run with `LOG_LEVEL=DEBUG` and read the traceback.

### Without installing

For quick prototyping the package only has to be importable:

```bash
COLLABORATIVE_SCRAPER_PLUGINS=collaborative_scraper_scopus python3 -m collaborative_scraper.server scopus:seed_scraper
```

or, permanently, in the server's `config.toml`:

```toml
[core]
plugins = ["collaborative_scraper_scopus"]
```

---

## Modes

Each target is a different strategy for choosing what to explore next. Pick one when starting
the server.

| Target | Strategy |
|--------|----------|
| `scopus:normal_scraper` | Expands an existing database. Loads every unexplored paper, works through them most-cited first, fetches each paper's *citing* then *cited* papers, and queues whatever is newly discovered. |
| `scopus:seed_scraper` | Grows a focused graph around a few known key papers. Starts from hand-picked seed ids and expands **breadth-first, layer by layer**, following only the papers that *cite* a paper and keeping for the next layer only those with at least 5 citations of their own. |
| `scopus:keyword_scraper` | Bootstraps from a topic instead of paper ids. Runs a Scopus title/abstract/keyword search per keyword, then hands the matching papers to the seed strategy. Searches are cached in the database, so re-running a known keyword is instant. |
| `scopus:popular_scraper` | Same frontier as `normal_scraper` — unexplored papers, most-cited first — but a paper is queued at most once per run, so one already in flight is never picked up again by a later page that mentions it. |
| `scopus:debug` | `normal_scraper` again, as a separate target so `[targets."scopus:debug"]` can point it at a scratch database (`db_name = "debug.db"`) without touching the real one. |

---

## Configuration

There is one config file, `config.toml`, under the server's config directory
(`~/.config/collaborative_scraper/config.toml` on Linux). `--info` prints its exact path.

`seed_scraper` and `keyword_scraper` take their input from the `[targets.*]` table — nothing
is hard-coded in the plugin:

```toml
[targets."scopus:seed_scraper"]
seeds = [85018894393, 84879913764, 84879038379]

[targets."scopus:keyword_scraper"]
keywords = [
    "shared control teleoperation",
    "assisted teleoperation",
]
```

Starting `scopus:seed_scraper` with no `seeds` key is an error, and so is starting
`scopus:keyword_scraper` with no `keywords` key.

### Where the data goes

The plugin never names a path: the server resolves the file per target and hands it over as
`cfg["db_file"]`, which is what the factory opens. By default:

```
~/.local/share/collaborative_scraper/scopus/scopus.db
```

Override it per project or per target:

```toml
[projects.scopus]
folder = "/mnt/data/scopus"      # everything the project writes (database + snapshots)
db_folder = "/mnt/fast/scopus"   # just the databases, if different

[targets."scopus:keyword_scraper"]
db_name = "keywords.db"          # only the file name
# db_file = "/tmp/scratch.db"    # or the whole path, ignoring folder and name
```

Precedence: `db_file` > `db_folder` + `db_name` > the project's data directory + `db_name`,
which defaults to `<project>.db` when the config file does not name one.

Print the resolved paths without starting a crawl:

```bash
python3 -m collaborative_scraper.server scopus:normal_scraper --info
```

---

## Running

```bash
python3 -m collaborative_scraper.server scopus:seed_scraper
```

The target can also be given as `--project scopus:seed_scraper`. There is no default target.
Useful flags: `--host` / `--port` (defaults `127.0.0.1:5000`), `--debug`, `--list-targets`,
`--list-plugins`, `--info`.

Then point the browser extension at the server, open Scopus, and start the extension — the
server drives the crawl and fills the database.

---

## The database

`ArticleDatabase` is a single SQLite file with three tables:

| Table | Purpose |
|-------|---------|
| `pages` | One row per paper: `id`, `title`, `year`, `pdf`, `num_citing`, `num_cited`, `citing` (JSON list of ids), `cited` (JSON list of ids), `explored`. This is the citation graph. |
| `queries` | Cache of keyword searches: `query`, `response` (JSON list of paper ids), `site`, keyed on `(query, site)`. Lets the keyword mode skip searches it already ran. |
| `fetch_requests` | A small queue of specific paper ids to fetch on demand, out of the normal crawling order. |

The file is created on first run.

---

## Layout

```
collaborative_scraper_scopus/
  __init__.py                    # register(reg): the whole wiring into the server
  utils.py                       # int parsing helpers the parsers share
  parse_html/
    science_article.py           # Article - the ScrapedElement subclass
    scopus.py                    # the registered parser + Scopus URL builders
    webofscience.py              # parsers kept from 1.0, not registered
    sciencedirect.py
  scrapers/
    scopus_scraper.py            # ScopusScraper - the base citation crawler
    seed_scraper.py              # breadth-first from seed ids
    keyword_scraper.py           # search by keyword, then seed
    popular_scraper.py           # most-cited first, each paper queued once
  databases/
    article_database.py          # ArticleDatabase
```

Only the package root has an `__init__.py`; the subfolders are implicit namespace packages,
like the server's own.

Everything the server needs is declared in `register()`:

```python
def register(reg):
    reg.project("scopus")                      # owns the "scopus:" namespace
    reg.parser("www.scopus.com", extract_elements)
    reg.scraper("seed_scraper", _seed)         # -> target "scopus:seed_scraper"
```

Variants are declared **bare** (`"seed_scraper"`); the `scopus:` prefix is added by the
server. Each scraper factory is called as `factory(cfg)` — that target's merged config table,
and nothing else.

The database is not declared at all: the server has no database registry, so `ArticleDatabase`
is ours to construct, and the factory opens it at the path the server resolved:

```python
def _seed(cfg):
    return SeedScraper(ArticleDatabase(cfg["db_file"]), cfg["seeds"], skip=_skip_from(cfg))
```

Every other key in `cfg` is the plugin's own — `seeds`, `keywords`, `blacklist` — which is how
a variant takes a new setting without anything in the server changing. The plugin imports from
`collaborative_scraper.api` only.
