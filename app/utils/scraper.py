# scraper.py

"""
High‑level wrapper around *trafilatura* that:

1. downloads a web page,
2. extracts the readable article in Markdown,
3. slices it by Markdown headings (H1–H6).

It returns the same data structure used in the legacy Anki add‑on so we can
re‑use the old chunk‑processing logic.
"""

from __future__ import annotations
import re
from typing import List, Dict, Any

from trafilatura import fetch_url, extract
from trafilatura.settings import use_config
from utils.logger import logger

__all__ = ["process_url"]

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)

def _split_markdown(markdown_text: str) -> List[Dict[str, str]]:
    """Break markdown into heading‑delimited sections."""
    sections, current_title, current_content = [], None, []

    for line in markdown_text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            if current_title is not None:
                sections.append(
                    {"title": current_title.strip(),
                     "content": "\n".join(current_content).strip()}
                )
            current_title, current_content = m.group(2), []
        else:
            current_content.append(line)

    if current_title is not None:
        sections.append(
            {"title": current_title.strip(),
             "content": "\n".join(current_content).strip()}
        )
    return sections

def _filter_headers(sections: List[Dict[str, str]], ignore: List[str] | None) -> List[Dict[str, str]]:
    if not ignore:
        return sections
    lowered = {s.lower() for s in ignore}
    return [sec for sec in sections if sec["title"].lower() not in lowered]

def process_url(url: str, ignore_list: List[str] | None = None) -> Dict[str, Any]:
    """
    Parameters
    ----------
    url : str
        Web page to fetch.
    ignore_list : list[str] | None
        Optional list of headings to drop (case‑insensitive).

    Returns
    -------
    dict
        {
          "url": "<url>",
          "sections": [ {"title": ..., "content": ...}, ... ]
        }
        or {} on failure.
    """
    logger.info("Scraping %s", url)
    html = fetch_url(url)
    if not html:
        logger.error("Download failed: %s", url)
        return {}

    cfg = use_config()
    markdown = extract(html,
                       config=cfg,
                       output_format="markdown",
                       include_comments=False,
                       include_tables=False,
                       with_metadata=False)
    if not markdown:
        logger.warning("trafilatura returned no content for %s", url)
        return {}

    sections = _split_markdown(markdown)
    sections = _filter_headers(sections, ignore_list)

    if not sections:
        logger.warning("No usable sections extracted from %s", url)
        return {}

    return {"url": url, "sections": sections}
