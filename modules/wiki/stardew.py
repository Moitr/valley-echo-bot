import base64
import logging
import os
from html import unescape
from html.parser import HTMLParser
from urllib.parse import quote, urljoin

import requests

from bot.config import CONFIG_PATH, section
from modules.chrome_utils import screenshot_element

logger = logging.getLogger("basic-bot.wiki_search")


_wiki_config = section("wiki")
_site_config = section("wiki.stardew")
SEARCH_URL = str(_site_config["search_url"])
WIKI_BASE_URL = str(_site_config["base_url"])
WIKI_PAGE_BASE_URL = str(_site_config["page_base_url"])
USER_AGENT = str(_wiki_config["user_agent"])
SCREENSHOT_DIR = str(CONFIG_PATH.parent / str(_site_config["screenshot_dir"]))
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
    """截取 Wiki 页面的信息框（infobox）并保存为 PNG。

    先通过 HTML 快速检查是否存在 infobox，避免无谓启动浏览器。

    Args:
        html: 页面 HTML 内容（用于快速检查 + 避免无谓的浏览器启动）
        url: Wiki 页面 URL

    Returns:
        截图 PNG 文件的绝对路径，或 None
    """
    # 快速检查：HTML 中没有 infobox 就直接跳过
    if "infoboxtable" not in html:
        return None

    return screenshot_element(
        url=url,
        selector=".infoboxborder, .infoboxtable",
        output_dir=SCREENSHOT_DIR,
    )


def _strip_html(text: str) -> str:
    """Remove HTML tags, unescape entities, collapse whitespace."""
    import re
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _find_element_end(html: str, tag: str, start: int) -> int:
    """Find the end position of an HTML element by tracking open/close depth."""
    import re
    open_pat = re.compile(rf"<{tag}\b", re.I)
    close_pat = re.compile(rf"</{tag}>", re.I)
    depth = 1
    pos = start
    while pos < len(html):
        next_open = open_pat.search(html, pos)
        next_close = close_pat.search(html, pos)
        open_pos = next_open.start() if next_open else float('inf')
        close_pos = next_close.start() if next_close else float('inf')
        if open_pos == float('inf') and close_pos == float('inf'):
            break
        if open_pos < close_pos:
            depth += 1
            pos = open_pos + 1
        else:
            depth -= 1
            if depth == 0:
                return close_pos + len(tag) + 3  # </tag>
            pos = close_pos + 1
    return len(html)


def extract_description(html, max_chars=None):
    """Extract the introductory description paragraph(s) from the wiki page.

    These are the <p> and <li> elements between the infobox and the
    table-of-contents.

    If max_chars is set, the output is limited to that many characters
    (truncated at a sentence boundary with a marker).
    """
    import re

    # Find where the infoboxborder ends
    infobox_end = 0
    infobox_class_pos = html.find('class="infoboxborder"')
    if infobox_class_pos != -1:
        # Find the <div tag that contains this class attribute
        div_start = html.rfind('<div', 0, infobox_class_pos)
        if div_start != -1:
            depth = 1  # we are inside infoboxborder's own <div>
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

    # Find where the TOC / next section starts
    search_start = infobox_end if infobox_end > 0 else 0
    toc_pos = html.find('id="toc"', search_start)
    if toc_pos == -1:
        toc_pos = html.find('class="mw-headline', search_start)
    if toc_pos == -1:
        toc_pos = len(html)

    # Extract <p> text between infobox end and TOC
    segment = html[search_start:toc_pos]

    parts = []
    for m in re.finditer(r"<p\b[^>]*>(.*?)</p>", segment, re.DOTALL):
        text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        text = unescape(text)
        text = re.sub(r"\s+", "", text)
        if text:
            parts.append(text)

    for m in re.finditer(r"<li\b[^>]*>(.*?)</li>", segment, re.DOTALL):
        text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        text = unescape(text)
        text = re.sub(r"\s+", "", text)
        if text:
            parts.append("· " + text)

    for m in re.finditer(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", segment, re.DOTALL):
        text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        text = unescape(text)
        text = re.sub(r"\s+", "", text)
        if text:
            parts.append(text)

    result = "\n".join(parts)

    if max_chars and len(result) > max_chars:
        # 优先保留第一段，标记后续内容交给 AI 总结
        first_nl = result.find("\n")
        if first_nl > 0 and first_nl <= max_chars:
            result = result[:first_nl] + "\n…"
        else:
            # 无段落分隔时，在句子边界截断
            truncated = result[:max_chars]
            for sep in ("。", "！", "？", "\n", "；", "，", " "):
                last = truncated.rfind(sep)
                if last > max_chars * 0.5:
                    result = truncated[:last + 1] + "…"
                    break
            else:
                result = truncated + "…"

    return result


def extract_page_text(html: str, max_sections: int = 15) -> str:
    """Extract main content text from a wiki page, preserving section structure.

    Used as fallback when the page has no infobox. Extracts headings and
    their associated paragraphs / list items from mw-parser-output.
    """
    import re

    # Find the main content container
    content_start = html.find('class="mw-parser-output"')
    if content_start == -1:
        content_start = 0

    # Find where content ends — try multiple end markers
    content_end = len(html)
    for end_marker in (
        'class="navbox"',
        'class="catlinks"',
        'id="catlinks"',
        'class="printfooter"',
        'class="mw-data-after-content"',
        'class="page-footer"',
        'class="mw-footer"',
        'class="site-footer"',
    ):
        pos = html.find(end_marker, content_start)
        if pos != -1 and pos < content_end:
            content_end = pos

    segment = html[content_start:content_end]

    # Split by section headings (h2, h3)
    heading_pat = re.compile(
        r'<h([23])\b[^>]*>.*?<span[^>]*class="mw-headline"[^>]*>(.*?)</span>.*?</h\1>',
        re.I | re.DOTALL,
    )

    sections = []
    last_end = 0
    for m in heading_pat.finditer(segment):
        pre_text = segment[last_end:m.start()]
        sections.append(("", pre_text))
        sections.append((_strip_html(m.group(2)), ""))
        last_end = m.end()

    if last_end < len(segment):
        sections.append(("", segment[last_end:]))

    # Noise patterns to filter out from extracted text
    _NOISE_PATTERNS = [
        r"游戏中心\s*\|.*帐号安全",
        r"本网络游戏适合",
        r"抵制不良游戏",
        r"COPYRIGHT\s*©",
        r"皖网文",
        r"皖B2-",
        r"皖ICP证",
        r"沪公网安备",
        r"此页面最后编辑于",
        r"此页面已被访问过",
        r"内部名称：\w+",
        r"开放时间：",
        r"地址：",
        r"-->\s*<!--",
    ]

    def _is_noise(text: str) -> bool:
        for pat in _NOISE_PATTERNS:
            if re.search(pat, text):
                return True
        return False

    lines = []
    section_count = 0
    for heading, body in sections:
        if heading:
            if section_count >= max_sections:
                lines.append("…（还有更多章节）")
                break
            lines.append(f"【{heading}】")
            section_count += 1

        for m in re.finditer(r"<p\b[^>]*>(.*?)</p>", body, re.DOTALL):
            text = _strip_html(m.group(1))
            if text and not _is_noise(text) and len(text) > 3:
                lines.append(text)

        for m in re.finditer(r"<li\b[^>]*>(.*?)</li>", body, re.DOTALL):
            text = _strip_html(m.group(1))
            if text and not _is_noise(text) and len(text) > 1:
                lines.append("· " + text)

        # Table cells — bundle requirements are often in tables
        for m in re.finditer(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", body, re.DOTALL):
            text = _strip_html(m.group(1))
            if text and not _is_noise(text) and len(text) > 1:
                lines.append(text)

    result = "\n".join(lines).strip()
    if len(result) > 6000:
        result = result[:6000] + "\n…（内容过长已截断）"
    return result


def format_page_summary(html, url, max_description_chars=300):
    parser = InfoboxParser()
    parser.feed(html)
    if not parser.headers and not parser.fields:
        return f"Wiki链接：{url}"

    description = extract_description(html, max_chars=max_description_chars)

    lines = []
    if len(parser.headers) >= 2:
        lines.append(f"{parser.headers[0]}（{parser.headers[1]}）")
    else:
        lines.extend(parser.headers[:1])

    if description:
        lines.append(description)
        lines.append("")

    for key, value in parser.fields:
        compact = " ".join(line.strip() for line in value.split("\n") if line.strip())
        lines.append(f"{key}：{compact}")
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
    """获取页面摘要数据，返回 (summary, html, page_url, has_image)。"""
    page = fetch_page_html_by_url(url)
    if not page:
        return f"Wiki链接：{url}", None, None, False
    html, final_url = page
    return format_page_summary(html, final_url), html, final_url, has_infobox(html)


def get_direct_page_summary_data(title):
    """获取直接页面摘要数据，返回 (summary, html, page_url, has_image)。"""
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


def get_page_full_text(url: str) -> str | None:
    """Fetch a wiki page by URL and extract full text content.

    Used as a fallback when a page has no infobox (format_page_summary
    would return just a bare URL).  This is NOT called by the "查询"
    command — only by the AI's search_wiki tool via _wiki_search().
    """
    page = fetch_page_html_by_url(url)
    if not page:
        return None
    html, final_url = page
    text = extract_page_text(html)
    if not text:
        return None
    return f"{text}\n\nWiki链接：{final_url}"
