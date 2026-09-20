"""Number parsing for the citation sites this plugin reads.

The sites write counts and years as display text ("1,234", "12.345"), so every
parser here needs the same three conversions. They used to live in the core's
utils.py, which made a site-agnostic framework carry scraping details; a plugin
owns its own parsing helpers.
"""
import logging

logger = logging.getLogger(__name__)

def guarded_int(value: str, description: str = "") -> int:
    """ int() that logs a critical message identifying the offending value before re-raising. """
    try:
        return int(value)
    except ValueError as e:
        logger.critical("can't convert %r to int%s", value, f" ({description})" if description else "")
        raise e

def safe_int(value: str) -> int:
    try:
        return formatted_int(value)
    except ValueError:
        return 0

def formatted_int(value: str) -> int:
    return int(value.replace(",", "").replace(".", "").replace("_", ""))
