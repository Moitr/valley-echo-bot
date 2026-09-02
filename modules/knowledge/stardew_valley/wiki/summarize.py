"""AI 摘要 — 当 Wiki 页面无 infobox 只返回链接时，用中立 AI 生成摘要"""

import re

import requests

from logger import logger
from config import DEEPSEEK_KEY, DEEPSEEK_SUMMARIZE_MODEL, DEEPSEEK_URL, section
from modules.knowledge.stardew_valley.wiki.vanilla import WikiRequestError, get_page_full_text

_wiki_config = section("wiki")
SUMMARY_REQUEST_TIMEOUT_SECONDS = float(_wiki_config["summary_request_timeout_seconds"])
SUMMARY_TEMPERATURE = float(_wiki_config["summary_temperature"])
SUMMARY_MAX_TOKENS = int(_wiki_config["summary_max_tokens"])
SUMMARY_MAX_SOURCE_CHARACTERS = int(_wiki_config["summary_max_source_characters"])
SUMMARY_HEAD_CHARACTERS = int(_wiki_config["summary_head_characters"])
SUMMARY_TAIL_CHARACTERS = int(_wiki_config["summary_tail_characters"])

# ── 两步法 prompt：先锁定事实，再总结 ──────────────────────────
SYSTEM_PROMPT = (
    "你是星露谷物语Wiki摘要助手。按以下步骤工作：\n"
    "第1步 — 从给定文本中提取所有硬数据：物品/人物名称、具体数值（价格/天数/条件/概率）、\n"
    "        机制描述（解锁条件/触发方式/前置要求）。只提取文本中明确写的，不推测。\n"
    "第2步 — 基于第1步提取的事实，用一句中文（20-80字）总结页面核心内容。\n"
    "        保留最关键的数据，不编造文本中没有的数字。\n"
    "\n"
    "严格规则：\n"
    "- 文本没提到的数据绝不出现\n"
    "- 信息不确定时用「据记载」措辞，不要断言\n"
    "- 只输出最终总结（一句中文），不要前缀、不要换行、不要输出第1步的中间结果"
)

# ── Wiki 文本噪音清理 ────────────────────────────────────────
_WIKI_NOISE = [
    (r"\{\{[^}]*\}\}", ""),                # {{模板}}
    (r"\[\[(?:文件|File|Image):[^\]]+\]\]", ""),  # [[文件:...]]
    (r"\[\[(?:[^\]|]*\|)?([^\]|]*)\]\]", r"\1"),  # [[链接|显示]] → 显示
    (r"'''(.*?)'''", r"\1"),               # '''粗体'''
    (r"''(.*?)''", r"\1"),                 # ''斜体''
    (r"&nbsp;", " "),
    (r"&lt;", "<"),
    (r"&gt;", ">"),
    (r"&amp;", "&"),
    (r"<!--.*?-->", ""),                   # HTML 注释
    (r"<[^>]+>", ""),                      # 残留 HTML 标签
    (r"\n{3,}", "\n\n"),                   # 多个空行合并
]


def _clean_wiki_text(text: str) -> str:
    """清理 Wiki 文本中的模板语法和格式噪音"""
    for pattern, replacement in _WIKI_NOISE:
        text = re.sub(pattern, replacement, text, flags=re.DOTALL)
    # 去掉只有空格的行
    text = re.sub(r"\n[ \t]+\n", "\n", text)
    return text.strip()


def summarize_wiki_page(url: str) -> str | None:
    if not DEEPSEEK_KEY:
        logger.error("[Wiki摘要] DEEPSEEK_KEY 未配置")
        return None
    """拉取 Wiki 页面全文并用 AI 生成中文摘要。返回 None 表示失败。"""
    text = get_page_full_text(url)
    if not text:
        logger.warning(f"[Wiki摘要] 无法获取页面内容: {url}")
        return None

    raw_len = len(text)
    logger.info(f"[Wiki摘要] 原始文本: {raw_len} 字符 — {url}")

    # 先清理噪音，再截断（清理后有效信息密度更高）
    content = _clean_wiki_text(text)
    clean_len = len(content)
    if clean_len != raw_len:
        logger.info(f"[Wiki摘要] 清理后: {clean_len} 字符 (去除 {raw_len - clean_len})")

    # 截断策略改进：优先保留开头（核心描述）和中间关键章节
    truncated = False
    if len(content) > SUMMARY_MAX_SOURCE_CHARACTERS:
        # 保留前 2500 字（核心介绍通常在开头）+ 尾 1500 字（可能有关键数据表）
        content = (
            content[:SUMMARY_HEAD_CHARACTERS]
            + "\n…\n"
            + content[-SUMMARY_TAIL_CHARACTERS:]
        )
        truncated = True
        logger.info(f"[Wiki摘要] 已截断: {clean_len} → {len(content)} 字符")

    final_len = len(content)

    try:
        resp = requests.post(
            DEEPSEEK_URL,
            json={
                "model": DEEPSEEK_SUMMARIZE_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"总结以下Wiki页面内容：\n\n{content}"},
                ],
                "temperature": SUMMARY_TEMPERATURE,
                "max_tokens": SUMMARY_MAX_TOKENS,
            },
            headers={
                "Authorization": f"Bearer {DEEPSEEK_KEY}",
                "Content-Type": "application/json",
            },
            timeout=SUMMARY_REQUEST_TIMEOUT_SECONDS,
        )

        if resp.ok:
            data = resp.json()
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", "?")
            completion_tokens = usage.get("completion_tokens", "?")
            reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
            total_tokens = usage.get("total_tokens", "?")

            choices = data.get("choices", [])
            if choices:
                summary = choices[0]["message"]["content"].strip()
                logger.info(
                    f"[Wiki摘要] 生成成功 | 摘要{len(summary)}字 | "
                    f"输入{raw_len}→清理{clean_len}→{'截断' if truncated else '全文'}{final_len}字 | "
                    f"token: in={prompt_tokens} out={completion_tokens}(推理{reasoning_tokens}) total={total_tokens} | "
                    f"模型={DEEPSEEK_SUMMARIZE_MODEL} temp=0.0 | {url}"
                )
                logger.debug(f"[Wiki摘要] 内容: {summary}")
                return summary

        logger.error(f"[Wiki摘要] API 错误: status={resp.status_code} body={resp.text[:300]}")
    except (requests.RequestException, WikiRequestError) as e:
        logger.error(f"[Wiki摘要] 请求失败: {e}")

    return None
