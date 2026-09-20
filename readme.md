# Plugin Scopus crawler

A plugin for the [Collaborative Scraper server](https://github.com/Angelo942/collaborative_scraper_server)
that crawls **scientific literature** and reconstructs the **citation graph** between papers.

---

## What it collects

For every paper it stores the basic metadata (id, title, year, PDF/link) plus the two
directions of the citation relationship:

- **citing** – the papers that *cite* this one.
- **cited** – the papers this one *references*.

This allows to build a connected graph of related literature.

The plugin ships several scrapers. Each one is a different strategy for choosing what to
explore next. (see [Configuration](#configuration)).

## Installation

The plugin is a set of Python modules that must be copied into the corresponding `extra/`
folders of an installed server. The folder layout mirrors the server, so installation is
just copying each folder into place.

### 1. Copy the files

From this plugin, copy into the server as follows:

| From (this plugin) | To (server) |
|--------------------|-------------|
| `databases/article_database.py` | `collaborative_scraper/databases/extra/article_database.py` |
| `parse_html/articles/` | `collaborative_scraper/parse_html/extra/articles/` |
| `scrapers/articles/` | `collaborative_scraper/scrapers/extra/articles/` |

For example, from the plugin directory:

```bash
# adjust SERVER to point at your server checkout
SERVER=/path/to/collaborative_scraper_server/collaborative_scraper

cp databases/article_database.py   "$SERVER/databases/extra/"
cp -r parse_html/articles          "$SERVER/parse_html/extra/"
cp -r scrapers/articles            "$SERVER/scrapers/extra/"
```

The `extra/` folders already exist in the server. After this step the modules are importable
as `collaborative_scraper.parse_html.extra.articles.scopus`, etc.

### 2. Register the parsers

Edit `collaborative_scraper/parse_html/parser.py` and add the three article sites:

```py
from collaborative_scraper.parse_html.extra.articles.scopus import extract_elements as extract_articles_from_scopus
from collaborative_scraper.parse_html.extra.articles.webofscience import extract_elements as extract_articles_from_webofscience
from collaborative_scraper.parse_html.extra.articles.sciencedirect import extract_elements as extract_article_info_from_sciencedirect

supported_domains = {
    "www.scopus.com": extract_articles_from_scopus,
    "www.webofscience.com": extract_articles_from_webofscience,
    "www.sciencedirect.com": extract_article_info_from_sciencedirect,
}
```

### 3. Register the database

Edit `collaborative_scraper/databases/db.py` and map the `scopus` project to the plugin's
database:

```py
from collaborative_scraper.databases.extra.article_database import ArticleDatabase

supported_targets = {
    "scopus": ArticleDatabase,
}
```

### 4. Register the scrapers (modes)

Edit `collaborative_scraper/scrapers/scraper.py`. Import the scrapers, write a small factory
for each mode, and add them to `supported_targets`:

```py
from collaborative_scraper.scrapers.extra.articles.scopus_scraper import ScopusScraper
from collaborative_scraper.scrapers.extra.articles.seed_scraper import SeedScraper
from collaborative_scraper.scrapers.extra.articles.keyword_scraper import KeywordScraper
from collaborative_scraper.databases.db import get_database

def scopus_scraper(db):
    return ScopusScraper(blacklist=lambda element: False, db=db)

def seed_scraper(db):
    # replace with your own seed paper ids
    return SeedScraper(85018894393, 84879913764, 84879038379, db=db)

def keyword_scraper(db):
    return KeywordScraper([
        "shared control teleoperation",
        "assisted teleoperation",
        # ... your keywords
    ], db=db)

supported_targets = {
    "scopus:normal_scraper": scopus_scraper,
    "scopus:seed_scraper": seed_scraper,
    "scopus:keyword_scraper": keyword_scraper,
    "scopus:debug": scopus_scraper,
}

def generate_scraper(target: str):
    project_name = target.split(":")[0]
    db = get_database(project_name)
    return supported_targets[target](db)
```

The target name follows the `project:mode` convention (e.g. `scopus:seed_scraper`). The part
before `:` (`scopus`) selects the database; the whole string selects the mode.

---

## Configuration
