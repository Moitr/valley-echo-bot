"""星露谷各 Wiki 的统一搜索适配层。"""


def search_wiki_source(query: str, source: str) -> str:
    query = str(query or "").strip()
    if source == "sve_wiki":
        from modules.knowledge.stardew_valley.wiki import sve as wiki
        label = "SVE Wiki"
    else:
        from modules.knowledge.stardew_valley.wiki import vanilla as wiki
        label = "原版 Wiki"
    if not query:
        return f"{label}搜索需要提供关键词。"
    try:
        summary = wiki.get_direct_page_summary(query)
        if summary:
            return summary
        results = wiki.get_search_results(query, limit=5)
        if not results:
            return f"{label}上没有找到关于「{query}」的内容。建议换个关键词试试。"
        first = results[0]
        summary = wiki.get_page_summary(first["url"])
        if summary:
            return summary
        return f"{label}搜索结果：" + "、".join(item.get("title", "?") for item in results)
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        if status:
            return f"{label}查询失败（状态码 {status}），请稍后再试。"
        return f"{label}查询出错：{exc}"

