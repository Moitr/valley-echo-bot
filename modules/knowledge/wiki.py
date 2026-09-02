"""星露谷 Wiki 能力门面，统一原版与 SVE 的查询入口。"""

from modules.wiki.stardew import (
    SCREENSHOT_DIR as STARDEW_SCREENSHOT_DIR,
    WikiRequestError,
    get_direct_page_summary_data,
    get_page_summary_data,
    get_search_results,
    save_infobox_screenshot,
)
from modules.wiki.summarize import summarize_wiki_page
from modules.wiki.sve import (
    SCREENSHOT_DIR as SVE_SCREENSHOT_DIR,
    WikiRequestError as SveWikiRequestError,
    get_direct_page_summary_data as sve_get_direct_page_summary_data,
    get_page_summary_data as sve_get_page_summary_data,
    get_search_results as sve_get_search_results,
    save_infobox_screenshot as sve_save_infobox_screenshot,
)

__all__ = [
    "STARDEW_SCREENSHOT_DIR",
    "SVE_SCREENSHOT_DIR",
    "SveWikiRequestError",
    "WikiRequestError",
    "get_direct_page_summary_data",
    "get_page_summary_data",
    "get_search_results",
    "save_infobox_screenshot",
    "summarize_wiki_page",
    "sve_get_direct_page_summary_data",
    "sve_get_page_summary_data",
    "sve_get_search_results",
    "sve_save_infobox_screenshot",
]
