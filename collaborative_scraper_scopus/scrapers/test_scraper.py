from collaborative_scraper.api import BaseScraper, Request, Result
from collaborative_scraper_scopus.scrapers.scopus_scraper import RequestData, Phase
from collaborative_scraper_scopus.parse_html.scopus import ScopusArticle as Article, get_papers_cited
import logging

logger = logging.getLogger(__name__)

class TestScraper(BaseScraper):
    """Smoke test for the parser and the FETCH -> GET search round trip.

    1. Lists the items and metadata of whatever Scopus page the client sends first.
    2. Asks for the papers cited by ``article_id`` - the ``CITEID(...)`` search,
       which goes through the search store (FETCH) and then the results page (GET).
    3. Lists what that search returned with the page's metadata, checks the
       metadata names the query we asked for, and stops the crawl.

    Nothing is written to the database. Results are printed, so they show at any
    LOG_LEVEL.
    """

    def __init__(self, db, article_id: int):
        super().__init__(db)
        self.target = Article(id=article_id)
        self.searched = False
        self.found = []

    @staticmethod
    def _list(label: str, articles: list[Article], result: Result | None) -> None:
        print(f"[TEST] {label}: {len(articles)} items")
        if result is not None:
            print(f"[TEST]   url:      {result.url}")
            print(f"[TEST]   metadata: {result.metadata!r}")
        for i, article in enumerate(articles, 1):
            print(f"[TEST]   {i:3d}. {article} ({article.year})")

    def _check_metadata(self, metadata: dict | None) -> None:
        expected = {"field": "CITEID", "argument": self.target.id}
        if metadata is None:
            print("[TEST] FAIL: the results page has no metadata (query box not found)")
            return
        got = {key: metadata.get(key) for key in expected}
        if got == expected:
            print(f"[TEST] OK: the results page answers {metadata['query']!r}")
        else:
            print(f"[TEST] FAIL: expected {expected}, the page says {got} (query {metadata.get('query')!r})")

    def unknown_page(self, result: Result) -> None:
        self._list("first page", result.elements, result)

    def update(self, article: Article, request_data: RequestData = None) -> None:
        self.found.append(article)

    def next_state(self, request_data: RequestData) -> Phase:
        return Phase.DONE # one page of up to 200 results is enough for a test

    def success(self, request_data: RequestData) -> None:
        self._list(f"CITEID({self.target.id})", self.found, request_data.result)
        self._check_metadata(request_data.result.metadata)

    def generate_request(self, request_data: RequestData = None) -> tuple[Request, RequestData]:
        if self.searched:
            if request_data is not None and request_data.fetch_phase != Phase.DONE:
                # /fetch_result falls back here when the store call failed or its callback raised
                logger.warning("the CITEID(%d) search never reached the results page", self.target.id)
            return None, None
        self.searched = True
        logger.info("searching CITEID(%d)", self.target.id)
        return get_papers_cited(self.target), RequestData(self.target, Phase.CITED)
