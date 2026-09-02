import base64
import logging
import os
from html import unescape
from html.parser import HTMLParser
from urllib.parse import quote, urljoin

import requests

from config import section, state_path
from modules.chrome_utils import screenshot_element

logger = logging.getLogger("basic-bot.sve_wiki_search")


_wiki_config = section("wiki")
_site_config = section("wiki.sve")
SEARCH_URL = str(_site_config["search_url"])
WIKI_BASE_URL = str(_site_config["base_url"])
WIKI_PAGE_BASE_URL = str(_site_config["page_base_url"])
USER_AGENT = str(_wiki_config["user_agent"])
SCREENSHOT_DIR = str(state_path(str(_site_config["screenshot_dir"])))
REQUEST_TIMEOUT_SECONDS = float(_wiki_config["request_timeout_seconds"])
HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": WIKI_PAGE_BASE_URL,
}


class WikiRequestError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f"Wiki request failed with status code {status_code}")


def check_response(response):
    if response.status_code == 567 or response.status_code >= 400:
        raise WikiRequestError(response.status_code)


def _request_get(*args, **kwargs):
    try:
        return requests.get(*args, **kwargs)
    except requests.RequestException as exc:
        status_code = getattr(exc.response, "status_code", 0) or 0
        raise WikiRequestError(status_code) from exc


class InfoboxParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_infobox = False
        self.in_row = False
        self.in_cell = False
        self.in_skip = 0
        self.cell_class = ""
        self.current_cell = []
        self.current_row = []
        self.headers = []
        self.fields = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        class_names = attrs.get("class", "").split()

        if tag in ("style", "script"):
            self.in_skip += 1
            return

        if tag == "table" and "infoboxtable" in class_names:
            self.in_infobox = True
            return

        if not self.in_infobox:
            return

        if tag == "tr":
            self.in_row = True
            self.current_row = []
            return

        if self.in_row and tag == "td":
            self.in_cell = True
            self.cell_class = attrs.get("class", "")
            self.current_cell = []
            return

        if self.in_cell and tag == "br":
            self.current_cell.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.in_skip = max(0, self.in_skip - 1)
            return

        if not self.in_infobox:
            return

        if self.in_cell and tag == "td":
            value = "".join(self.current_cell).strip()
            value = "\n".join(line.strip() for line in value.splitlines() if line.strip())
            self.current_row.append((self.cell_class, value))
            self.in_cell = False
            self.cell_class = ""
            self.current_cell = []
            return

        if self.in_row and tag == "tr":
            self._finish_row()
            self.in_row = False
            self.current_row = []
            return

        if tag == "table":
            self.in_infobox = False

    def handle_data(self, data):
        if self.in_skip:
            return
        if self.in_cell:
            self.current_cell.append(data)

    def _finish_row(self):
        if len(self.current_row) == 1:
            class_name, value = self.current_row[0]
            if "infoboxheader" in class_name and value:
                self.headers.append(value)
            return

        if len(self.current_row) >= 2:
            key_class, key = self.current_row[0]
            _, value = self.current_row[1]
            if "infoboxsection" in key_class and key and value:
                self.fields.append((key, value))


class SearchResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.in_heading = False
        self.in_link = False
        self.current_text = []
        self.current_url = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        class_names = attrs.get("class", "").split()

        if tag == "div" and "mw-search-result-heading" in class_names:
            self.in_heading = True
            return

        if self.in_heading and tag == "a" and "data-serp-pos" in attrs:
            self.in_link = True
            self.current_text = []
            self.current_url = urljoin(WIKI_BASE_URL, attrs.get("href", ""))

    def handle_endtag(self, tag):
        if self.in_link and tag == "a":
            title = "".join(self.current_text).strip()
            if title:
                self.results.append({"title": title, "url": self.current_url})
            self.in_link = False
            self.current_text = []
            self.current_url = None
            return

        if self.in_heading and tag == "div":
            self.in_heading = False

    def handle_data(self, data):
        if self.in_link:
            self.current_text.append(data)


def fetch_search_html(search):
    response = _request_get(
        SEARCH_URL,
        params={
            "title": "特殊:搜索",
            "profile": "default",
            "fulltext": "1",
            "search": str(search),
        },
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    check_response(response)
    response.raise_for_status()
    return response.text


def fetch_direct_page_html(title):
    url = WIKI_PAGE_BASE_URL + quote(str(title), safe="/")
    response = _request_get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code == 404 or "noarticletext" in response.text:
        return None
    check_response(response)
    response.raise_for_status()
    return response.text, response.url


def fetch_page_html_by_url(url):
    response = _request_get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code == 404 or "noarticletext" in response.text:
        return None
    check_response(response)
    response.raise_for_status()
    return response.text, response.url


def has_infobox(html):
    if "infoboxtable" in html:
        return True
    parser = InfoboxParser()
    parser.feed(html)
    return bool(parser.headers or parser.fields)


def save_infobox_screenshot(html: str, url: str) -> str | None:
    """截取 SVE Wiki 页面的信息框（infobox）并保存为 PNG。

    Args:
        html: 页面 HTML 内容（用于快速检查 + 避免无谓的浏览器启动）
        url: Wiki 页面 URL

    Returns:
        截图 PNG 文件的绝对路径，或 None
    """
    if "infoboxtable" not in html:
        return None

    return screenshot_element(
        url=url,
        selector=".infoboxborder, .infoboxtable",
        output_dir=SCREENSHOT_DIR,
    )


def extract_description(html, max_chars=120):
    """Extract the introductory description paragraph(s) from the wiki page.

    Only takes the first meaningful paragraph(s), capped at max_chars.
    """
    import re

    infobox_end = 0
    infobox_class_pos = html.find('class="infoboxborder"')
    if infobox_class_pos != -1:
        div_start = html.rfind('<div', 0, infobox_class_pos)
        depth = 1
        pos = div_start
        while pos != -1 and pos < len(html):
            next_open = html.find('<div', pos + 1)
            next_close = html.find('</div>', pos + 1)
            if next_open != -1 and next_open < next_close:
                depth += 1
                pos = next_open
            elif next_close != -1:
                depth -= 1
                if depth == 0:
                    infobox_end = next_close + 6
                    break
                pos = next_close
            else:
                break

    # Stop at the first heading (h2/h3) or TOC to avoid grabbing unrelated sections
    search_start = infobox_end if infobox_end > 0 else 0
    toc_pos = html.find('id="toc"', search_start)
    if toc_pos == -1:
        toc_pos = html.find('class="mw-headline', search_start)
    if toc_pos == -1:
        # Find first <h2> or <h3> as a fallback section boundary
        m = re.search(r'<h[23]\b', html[search_start:])
        toc_pos = search_start + m.start() if m else len(html)

    segment = html[search_start:toc_pos]
    paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", segment, re.DOTALL)
    if not paragraphs:
        return ""

    parts = []
    total = 0
    for p in paragraphs:
        text = re.sub(r"<[^>]+>", "", p).strip()
        text = unescape(text)
        text = re.sub(r"\s+", "", text)
        if not text:
            continue
        if total + len(text) > max_chars:
            remaining = max_chars - total
            if remaining > 20:
                parts.append(text[:remaining] + "…")
            break
        parts.append(text)
        total += len(text)

    return "\n".join(parts)


def format_page_summary(html, url, max_fields=8):
    parser = InfoboxParser()
    parser.feed(html)
    if not parser.headers and not parser.fields:
        return f"Wiki链接：{url}"

    description = extract_description(html)

    lines = []
    if len(parser.headers) >= 2:
        lines.append(f"{parser.headers[0]}（{parser.headers[1]}）")
    else:
        lines.extend(parser.headers[:1])

    if description:
        lines.append(description)
        lines.append("")

    shown = 0
    for key, value in parser.fields:
        if shown >= max_fields:
            break
        # 把换行压缩成空格，避免多行列表撑爆消息
        compact = " ".join(line.strip() for line in value.split("\n") if line.strip())
        lines.append(f"{key}：{compact}")
        shown += 1
    if shown < len(parser.fields):
        lines.append(f"（还有 {len(parser.fields) - shown} 个字段）")
    lines.append(f"\nWiki链接：{url}")
    return "\n".join(lines)


def get_direct_page_url(title):
    page = fetch_direct_page_html(title)
    if not page:
        return None
    _, url = page
    return url


def get_page_summary(url):
    page = fetch_page_html_by_url(url)
    if not page:
        return f"Wiki链接：{url}"
    html, final_url = page
    return format_page_summary(html, final_url)


def get_direct_page_summary(title):
    page = fetch_direct_page_html(title)
    if not page:
        return None
    html, url = page
    return format_page_summary(html, url)


def get_page_summary_data(url):
    """获取 SVE 页面摘要数据，返回 (summary, html, page_url, has_image)。"""
    page = fetch_page_html_by_url(url)
    if not page:
        return f"Wiki链接：{url}", None, None, False
    html, final_url = page
    return format_page_summary(html, final_url), html, final_url, has_infobox(html)


def get_direct_page_summary_data(title):
    """获取 SVE 直接页面摘要数据，返回 (summary, html, page_url, has_image)。"""
    page = fetch_direct_page_html(title)
    if not page:
        return None, None, None, False
    html, url = page
    return format_page_summary(html, url), html, url, has_infobox(html)


def get_page_summary_with_image(url):
    page = fetch_page_html_by_url(url)
    if not page:
        return f"Wiki链接：{url}", None
    html, final_url = page
    summary = format_page_summary(html, final_url)
    image_path = save_infobox_screenshot(html, final_url) if has_infobox(html) else None
    return summary, image_path


def get_direct_page_summary_with_image(title):
    page = fetch_direct_page_html(title)
    if not page:
        return None, None
    html, url = page
    summary = format_page_summary(html, url)
    image_path = save_infobox_screenshot(html, url) if has_infobox(html) else None
    return summary, image_path


def get_search_results(search, limit=10):
    parser = SearchResultParser()
    parser.feed(fetch_search_html(search))
    return parser.results[:limit]


def format_search_results(search, limit=10):
    results = get_search_results(search, limit)
    if not results:
        return "没有搜索结果"
    return "\n".join(
        f"{index}.{result['title']}" for index, result in enumerate(results, 1)
    )
