# scraper.py

"""
High-level wrapper around trafilatura for web page scraping and Markdown sectioning.

Steps:
1. Download the web page HTML.
2. Extract readable article content as Markdown.
3. Split content into sections based on Markdown headings (H1–H6).

Returns a structure compatible with legacy Anki add-on chunk-processing logic.
"""

from __future__ import annotations
import re
from typing import List, Dict, Any

from trafilatura import fetch_url, extract
from trafilatura.settings import use_config
from utils.logger import logger

__all__ = ["process_url"]

# Regex to match Markdown headings of level 1 to 6: captures hashes and title text
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


def _split_markdown(markdown_text: str) -> List[Dict[str, str]]:
    """
    Split Markdown text into sections delimited by headings.

    Each section is a dict with 'title' from the heading text and
    'content' containing all following lines until the next heading.
    """
    sections: List[Dict[str, str]] = []
    current_title: str | None = None
    current_content: List[str] = []

    # Iterate line by line to detect headings
    for line in markdown_text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            # If already accumulating a section, finalize it
            if current_title is not None:
                sections.append({
                    "title": current_title.strip(),
                    "content": "\n".join(current_content).strip()
                })

            # Start a new section with the text after the hashes
            current_title = match.group(2)
            current_content = []
        else:
            # Collect content lines under the current section
            current_content.append(line)

    # After loop, append the last section if present
    if current_title is not None:
        sections.append({
            "title": current_title.strip(),
            "content": "\n".join(current_content).strip()
        })

    return sections


def _filter_headers(
    sections: List[Dict[str, str]], ignore: List[str] | None
) -> List[Dict[str, str]]:
    """
    Remove sections whose titles match any in the ignore list (case-insensitive).

    Parameters:
        sections: list of section dicts with 'title' and 'content'.
        ignore: optional list of titles to drop.

    Returns:
        Filtered list of sections.
    """
    if not ignore:
        return sections
    
    # Normalize ignore list entries to lowercase
    ignore_set = {title.lower() for title in ignore}

    # Keep only sections whose title is not in ignore_set
    return [sec for sec in sections if sec["title"].lower() not in ignore_set]


def process_url(
    url: str,
    ignore_list: List[str] | None = None
) -> Dict[str, Any]:
    """
    Fetch and process a web page into Markdown sections.

    Parameters
    ----------
    url : str
        Web page URL to scrape.
    ignore_list : list[str] | None
        Optional list of section titles to exclude from results.

    Returns
    -------
    dict
        {
          "url": <url>,
          "sections": [ {"title": ..., "content": ...}, ... ]
        }
        or an empty dict on any failure.
    """
    logger.info("Scraping %s", url)

    # Download the page HTML content
    html = fetch_url(url)
    if not html:
        logger.error("Download failed: %s", url)
        return {}

    # Configure trafilatura parser with default settings
    cfg = use_config()
    # Extract Markdown-formatted text; exclude comments and tables
    markdown_text = extract(
        html,
        config=cfg,
        output_format="markdown",
        include_comments=False,
        include_tables=False,
        with_metadata=False
    )
    if not markdown_text:
        logger.warning("trafilatura returned no content for %s", url)
        return {}

    # Split extracted Markdown into heading-based sections
    sections = _split_markdown(markdown_text)

    # Filter out any unwanted headers
    sections = _filter_headers(sections, ignore_list)

    if not sections:
        logger.warning("No usable sections extracted from %s", url)
        return {}

    # Return final structured result
    return {"url": url, "sections": sections}
