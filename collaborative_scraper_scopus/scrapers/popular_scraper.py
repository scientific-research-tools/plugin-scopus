from collaborative_scraper_scopus.scrapers.scopus_scraper import ScopusScraper, RequestData
from collaborative_scraper_scopus.parse_html.scopus import ScopusArticle as Article
import logging

logger = logging.getLogger(__name__)

class PopularScraper(ScopusScraper):
    """Work through the unexplored articles, most-cited first, queueing each once.

    The frontier is the base class's flat ``candidate_queue``, ordered by
    ``Article.__gt__`` (citation count), with one difference: an article enters
    it at most once per run. The base class decides on ``article.explored``
    alone, which lets an article that is already queued - or in flight, so not
    yet explored - be queued again by whatever page mentions it next.
    """

    def __init__(self, db, **kwargs):
        super().__init__(db, **kwargs)
        # Everything the database already knows: either explored, or sitting in
        # the candidate_queue the base class just built from it.
        self.queued = {article.id for article in self.known_articles.values()}
        logger.debug("starting from %d known articles, %d unexplored",
                     len(self.queued), len(self.candidate_queue))

    def _update_impl(self, article: Article, request_data: RequestData = None) -> None:
        if article.id in self.queued:
            return
        self.queued.add(article.id)
        if not article.explored:
            logger.debug("adding %s to the queue", article)
            self.candidate_queue.append(article)
