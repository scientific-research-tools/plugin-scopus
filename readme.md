# Scopus plugin

> **⚠ Currently broken.** Scopus changed its site, and search parameters are no longer passed
> as a GET request. The parser in this plugin relied on that GET encoding.

A plugin for the [Collaborative Scraper](https://github.com/Angelo942/collaborative_scraper_server)
that crawls **scientific literature** and reconstructs the **citation graph** between papers.

Requires server **2.0 or later**.

---

## What it collects

For every paper it stores the basic metadata (id, title, year, link) plus both directions
of the citation relationship:

- **citing** — the papers that *cite* this one,
- **cited** — the papers this one *references*.

Following these links outward from a starting point grows a connected graph of related
literature which can be explored through a web interface with our [graph explorer](https://github.com/scientific-research-tools/paper_explorer)

---

## Installation

The plugin is a pip-installable distribution: it

```bash
pip install /path/to/plugin-scopus
```

Check that it was picked up:

```bash
python3 -m collaborative_scraper.server --list-plugins
python3 -m collaborative_scraper.server --list-targets
```

If `scopus:*` targets are missing, the plugin failed to load. Raise an issue if it happens.

---

## Modes

Each target is a different strategy for choosing what to explore next. Pick one when starting
the server.

| Target | Strategy |
|--------|----------|
| `scopus:popular_scraper` | Expands an existing database. Loads every unexplored paper, works through them most-cited first, fetches each paper's *citing* then *cited* papers, and queues whatever is newly discovered. |
| `scopus:seed_scraper` | Grows a focused graph around a few selected key papers. Starts from hand-picked seed ids and expands **breadth-first, layer by layer**, following only the papers that *cite* a paper and keeping for the next layer only those with at least 5 citations of their own. |
| `scopus:keyword_scraper` | Bootstraps from a topic instead of paper ids. Runs a Scopus title/abstract/keyword search per keyword, then hands the matching papers to the seed strategy. Searches are cached in the database. |

---

## Configuration

The plugin is configured through the file, `config.toml`, under the server's config directory
(`~/.config/collaborative_scraper/config.toml` on Linux). `--info` prints its exact path.

`seed_scraper` and `keyword_scraper` take their input from the `[targets.*]` table:

```toml
[targets."scopus:seed_scraper"]
seeds = [85018894393, 84879913764, 84879038379]

[targets."scopus:keyword_scraper"]
keywords = [
    "shared control teleoperation",
    "assisted teleoperation",
]
```

---

## Running

```bash
python3 -m collaborative_scraper.server scopus:seed_scraper
```

Then go visit an article on Scopus, and start the [browser extension](https://github.com/Angelo942/collaborative_scraper_extension) to send the pages to the server.

---

## The database

`ArticleDatabase` is a single SQLite file with three tables:

| Table | Purpose |
|-------|---------|
| `pages` | One row per paper: `id`, `title`, `year`, `pdf`, `num_citing`, `num_cited`, `citing` (JSON list of ids), `cited` (JSON list of ids), `explored`. This is the citation graph. |
| `queries` | Cache of keyword searches: `query`, `response` (JSON list of paper ids), `site`, keyed on `(query, site)`. Lets the keyword mode skip searches it already ran. |
| `fetch_requests` | A small queue of specific paper ids to fetch on demand, out of the normal crawling order. |

The file is created on first run.

### Where the data goes

By default:

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

Print the resolved path for a specific target without starting a crawl:

```bash
python3 -m collaborative_scraper.server scopus:popular_scraper --info
```
