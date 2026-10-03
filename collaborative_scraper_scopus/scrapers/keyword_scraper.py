from collaborative_scraper_scopus.scrapers.scopus_scraper import RequestData, Phase
from collaborative_scraper.api import Request
from collaborative_scraper_scopus.scrapers.seed_scraper import SeedScraper
from collaborative_scraper_scopus.parse_html.scopus import ScopusArticle as Article, get_papers_from_keyword
import logging

logger = logging.getLogger(__name__)

RESULTS_PER_PAGE = 200  # the limit= in the search URLs built by parse_html/scopus.py

class Query:
    """One keyword search in flight: what was asked, and what has come back.

    It stands in for an Article as a request's ``requested_element`` during the
    search phase - the server hands the same object back to ``update`` /
    ``next_state`` / ``success``, so the pagination state lives here rather than
    on the scraper, and nothing breaks if two searches are ever in flight at
    once.
    """

    def __init__(self, keyword: str):
        self.keyword = keyword
        self.results = []    # article ids, in the order the search returned them
        self.page_start = 0  # len(results) when the page now in flight was asked for

    def __repr__(self):
        return f"Query({self.keyword!r})[{len(self.results)}]"

class KeywordScraper(SeedScraper):
    """Bootstrap the seed strategy from a topic instead of from paper ids.

    Runs one Scopus search per keyword, 200 results at a time, and drops every
    hit into the first layer. Once the keywords are exhausted the crawl *is* a
    SeedScraper crawl - breadth-first, layer by layer - which is why this is a
    subclass and not a scraper driving a second one.

    Searches are cached in the ``queries`` table, so a keyword that has already
    been run is replayed from the database at startup and never fetched again.
    """

    def __init__(self, db, keywords: list[str], **kwargs):
        """
        Args:
            db: The store to crawl into.
            keywords: Search terms to bootstrap from, read from the target's
                config by the plugin's factory.
        """
        # No seeds: the first layer is whatever the searches turn up, or what a
        # cached search replays below.
        super().__init__(db, [], **kwargs)
        # SeedScraper starts current_layer as a list and swaps in a set on the
        # first layer change; we add to it from update(), so normalise it now.
        self.current_layer = set(self.current_layer)

        known_queries = self.db.get_queries()
        self.pending = []
        for keyword in keywords:
            if keyword in known_queries:
                logger.info("cached query, not fetching again: %s", keyword)
                for id in self.db.get_query_results(keyword):
                    self._seed(self.known_articles.get(id))
                continue
            if keyword not in self.pending:
                self.pending.append(keyword)

    def _seed(self, article: Article | None) -> None:
        """Put a search hit into the layer the seed strategy expands next."""
        if article is None:
            logger.warning("a cached query names an article missing from the database")
            return
        if article.id not in self.explored:
            self.explored.add(article.id)
            self.current_layer.add(article)

    def _request_generator(self):
        """Every keyword first, then the ordinary seed frontier.

        The body only runs on the first next() - ScopusScraper.__init__ just
        builds the generator object - so ``self.pending`` is already filled by
        the time the server asks for a page.
        """
        while self.pending:
            yield Query(self.pending.pop(0))
        yield from super()._request_generator()

    def generate_request(self, request_data: RequestData = None) -> tuple[Request, RequestData]:
        if request_data is None or request_data.fetch_phase == Phase.DONE:
            next_element = next(self.request_stream)
            if next_element is None:
                return None, None
            phase = Phase.SEARCH if isinstance(next_element, Query) else Phase.CITING
            request_data = RequestData(next_element, phase)

        if request_data.fetch_phase == Phase.SEARCH:
            query = request_data.requested_element
            query.page_start = len(query.results)
            logger.info("searching %r from %d", query.keyword, query.page_start)
            return get_papers_from_keyword(query.keyword, query.page_start), request_data

        return super().generate_request(request_data)

    def _update_impl(self, article: Article, request_data: RequestData) -> None:
        if request_data is not None and request_data.fetch_phase == Phase.SEARCH:
            request_data.requested_element.results.append(article.id)
            self._seed(article)
            return
        super()._update_impl(article, request_data)

    def next_state(self, request_data: RequestData) -> Phase:
        if request_data.fetch_phase != Phase.SEARCH:
            return super().next_state(request_data)
        query = request_data.requested_element
        # A full page means there is probably another one behind it; a short one
        # (or an empty one) is the last.
        if len(query.results) - query.page_start == RESULTS_PER_PAGE:
            return Phase.SEARCH
        return Phase.DONE

    def success(self, request_data: RequestData) -> None:
        # The server sets fetch_phase to DONE before calling us, so the phase no
        # longer says what kind of request this was - the element does.
        query = request_data.requested_element
        if isinstance(query, Query):
            logger.info("%r returned %d articles", query.keyword, len(query.results))
            self.db.save_query(query.keyword, query.results, "scopus")
            return
        super().success(request_data)
