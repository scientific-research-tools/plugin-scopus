import sqlite3
import json
from collaborative_scraper.api import ScraperDatabase
from collaborative_scraper_scopus.parse_html.science_article import Article
from collections import Counter

class ArticleDatabase(ScraperDatabase):
    # No db_name: the file is named in config.toml (db_name / db_file), and the
    # factory opens whatever path the core resolved from it.

    def _init_db(self) -> None:
        """Create tables if they don't exist"""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    year INTEGER,
                    pdf TEXT,
                    num_citing INTEGER,
                    num_cited INTEGER,
                    citing TEXT,
                    cited TEXT,
                    explored INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS queries (
                    query TEXT NOT NULL,
                    response TEXT,
                    site TEXT NOT NULL,
                    PRIMARY KEY (query, site)
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fetch_requests (
                    paper_id INTEGER PRIMARY KEY
                )
            """)

    # --- Database helper functions ---
    def save_element(self, article: Article) -> None:
        with self._connect() as conn:
            try:
                conn.execute("""
                    INSERT INTO pages (id, title, year, pdf, num_citing, num_cited, citing, cited, explored)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    article.id,
                    article.title,
                    article.year,
                    article.pdf,
                    article.num_citing,
                    article.num_cited,
                    json.dumps(article.citing),
                    json.dumps(article.cited),
                    int(article.explored)
                ))
            except sqlite3.IntegrityError as e:
                raise RuntimeError(f"[DB] Page with id={article.id!r} already exists") from e

    def update_element(self, article: Article) -> None:
        with self._connect() as conn:
            cur = conn.execute("""
                UPDATE pages
                SET title=?, year=?, pdf=?, num_citing=?, num_cited=?, citing=?, cited=?, explored=?
                WHERE id=?
            """, (
                article.title,
                article.year,
                article.pdf,
                article.num_citing,
                article.num_cited,
                json.dumps(article.citing),
                json.dumps(article.cited),
                int(article.explored),
                article.id
            ))
            if cur.rowcount == 0:
                raise RuntimeError(f"[DB] Page with id={article.id!r} not found for update")

    def get_articles(self) -> list[Article]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, title, year, pdf, num_citing, num_cited, citing, cited, explored FROM pages"
            ).fetchall()
        return [Article(*r) for r in rows]

    def save_query(self, query: str, response: list[int], site: str) -> None:
        with self._connect() as conn:
            try:
                conn.execute("""
                    INSERT INTO queries (query, response, site)
                    VALUES (?, ?, ?)
                """, (
                    query,
                    json.dumps(response),
                    site
                ))
            except sqlite3.IntegrityError as e:
                raise RuntimeError(f"[DB] Query {query} already exists") from e

    def get_queries(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT query FROM queries").fetchall()
        return [row[0] for row in rows]

    def get_query_results(self, query: str) -> list[int]:
        with self._connect() as conn:
            row = conn.execute("SELECT response FROM queries WHERE query = ?", (query,)).fetchone()
        if not row:
            return []
        ids = json.loads(row[0])
        return ids if ids else []

    def get_unexplored(self) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id FROM pages WHERE explored = 0").fetchall()
        return [r[0] for r in rows]

    def get_popular_words(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT title FROM pages").fetchall()
        counter = Counter()
        for r in rows:
            for word in r[0].lower().split():
                counter[word] += 1
        return counter

    def pop_next_fetch_request(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT paper_id FROM fetch_requests ORDER BY rowid ASC LIMIT 1").fetchone()
            if not row:
                return None
            paper_id = int(row[0])
            conn.execute("DELETE FROM fetch_requests WHERE paper_id = ?", (paper_id,))
        return paper_id