# collaborative_scraper_scopus/__init__.py
from .parse_html.scopus import extract_elements
from .databases.article_database import ArticleDatabase
from .scrapers.scopus_scraper import ScopusScraper
from .scrapers.seed_scraper import SeedScraper
from .scrapers.keyword_scraper import KeywordScraper
from .scrapers.popular_scraper import PopularScraper

def register(reg):
    reg.project("scopus")                           # owns the "scopus:" namespace

    reg.parser("www.scopus.com", extract_elements)

    reg.scraper("normal_scraper", _normal)
    reg.scraper("seed_scraper", _seed)
    reg.scraper("keyword_scraper", _keyword)
    reg.scraper("popular_scraper", _popular)
    reg.scraper("debug", _normal)

# ---- what the factories read out of config.toml ----
#
# A factory is called with the target's config table and nothing else. The core
# resolves where the database goes and leaves it in cfg["db_file"]; the store
# itself is ours, so ArticleDatabase is imported here like any other module.
# Every other key is ours too - a new setting is a new read below, never a
# change to the core:
#
#     [projects.scopus]
#     db_name = "articles.db"                   # default is <project>.db
#     blacklist = ["metaverse", "blockchain"]   # applies to every variant
#
#     [targets."scopus:seed_scraper"]
#     seeds = [85018894393, 84879913764]        # this variant only
#
#     [targets."scopus:debug"]
#     db_name = "debug.db"                      # scratch file, same schema

def _open(cfg):
    """Our store, at the path the core resolved from the config file."""
    return ArticleDatabase(cfg["db_file"])

def _skip_from(cfg):
    """Turn the ``blacklist`` config key into the predicate the scraper calls.

    A list of substrings matched against the title, case-insensitively; an
    article matching any of them is never explored. Absent or empty means
    explore everything.
    """
    words = [str(word).lower() for word in cfg.get("blacklist", [])]
    if not words:
        return lambda article: False

    def skip(article):
        title = (article.title or "").lower()
        return any(word in title for word in words)
    return skip

def _missing(target, key, example):
    return SystemExit(
        f"{target} needs {key!r}. Add to config.toml:\n"
        f'[targets."{target}"]\n{key} = {example}')

def _normal(cfg):
    return ScopusScraper(_open(cfg), skip=_skip_from(cfg))

def _popular(cfg):
    return PopularScraper(_open(cfg), skip=_skip_from(cfg))

def _seed(cfg):
    seeds = cfg.get("seeds")
    if not seeds:
        raise _missing("scopus:seed_scraper", "seeds", "[85018894393, ...]")
    return SeedScraper(_open(cfg), seeds, skip=_skip_from(cfg))

def _keyword(cfg):
    keywords = cfg.get("keywords")
    if not keywords:
        raise _missing("scopus:keyword_scraper", "keywords",
                       '["shared control teleoperation", ...]')
    return KeywordScraper(_open(cfg), keywords, skip=_skip_from(cfg))
