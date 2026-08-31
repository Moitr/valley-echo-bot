"""星露谷物语本地数据查询模块 — 为 function calling 提供数据支持"""

import json
import os

from bot.config import section
from modules.game.translate import (
    tr_category,
    tr_cooking,
    tr_crop,
    tr_fish,
    tr_item,
    tr_mineral,
    tr_month,
    tr_season,
    tr_villager,
    tr_weather,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "stardew")

_cache: dict[str, list[dict]] = {}

# 需要加载的数据文件及其中文说明
_MODULES = {
    "crops": "作物",
    "fish": "鱼",
    "villagers": "村民",
    "cooking": "烹饪食谱",
    "crafting": "制造配方",
    "minerals": "矿物",
    "artifacts": "古物",
    "forageables": "采集品",
    "weapons": "武器",
    "tools": "工具",
    "rings": "戒指",
    "hats": "帽子",
    "footwear": "鞋子",
    "monsters": "怪物",
    "bundles": "社区中心收集包",
    "animals": "动物",
    "trees": "果树",
    "artisan-goods": "工匠制品",
    "achievements": "成就",
    "events": "事件",
    "quests": "任务",
    "seasons": "季节",
    "weather": "天气",
    "locations": "地点",
    "buildings": "建筑",
    "skills": "技能",
    "professions": "职业",
    "bait": "鱼饵",
    "tackle": "渔具",
    "trinkets": "饰品",
    "special-items": "特殊物品",
}


def _load(name: str) -> list[dict]:
    """加载 JSON 数据文件，带缓存"""
    if name not in _cache:
        path = os.path.join(DATA_DIR, f"{name}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                _cache[name] = json.load(f)
        else:
            _cache[name] = []
    return _cache[name]


def _fuzzy_match(items: list[dict], query: str, fields=("name",)) -> list[dict]:
    """模糊匹配：名称包含关键词（不区分大小写）"""
    q = str(query or "").strip().lower()
    if not q:
        return []
    results = []
    for item in items:
        for field in fields:
            val = item.get(field, "")
            if isinstance(val, str) and q in val.lower():
                results.append(item)
                break
    return results


# ═══════════════════════════════════════════════════════════════
# 格式化辅助函数
# ═══════════════════════════════════════════════════════════════

def _fmt_minutes(seconds: int | None) -> str:
    """将秒数转为分钟表示（用于 buff 持续时间和加工时间）"""
    if seconds is None:
        return "?"
    m = seconds / 60
    if m == int(m):
        return f"{int(m)}分钟"
    return f"{m:.1f}分钟"


def _fmt_artisan_uses(artisan: dict | None) -> str:
    """格式化 artisanUses 为可用的加工设备列表"""
    if not artisan:
        return ""
    mapping = {
        "wine": "小桶(酒)",
        "juice": "小桶(果汁)",
        "pickles": "罐头瓶(泡菜)",
        "jelly": "罐头瓶(果酱)",
        "driedMushrooms": "烘干机(蘑菇)",
        "driedFruit": "烘干机(果干)",
    }
    uses = [label for key, label in mapping.items() if artisan.get(key)]
    return "、".join(uses) if uses else ""


def _fmt_harvest_quantity(hq: dict | None) -> str:
    """格式化收获数量范围"""
    if not hq:
        return ""
    lo, hi = hq.get("min", 1), hq.get("max", 1)
    return f"{lo}" if lo == hi else f"{lo}~{hi}"


def _fmt_recipe_sources(sources: list[dict] | None) -> str:
    """格式化食谱获取来源"""
    if not sources:
        return ""
    parts = []
    for s in sources:
        t = s.get("type", "")
        if t == "default":
            parts.append("初始拥有")
        elif t == "queen-of-sauce":
            parts.append(f"酱料女皇 {tr_season(s.get('season','?'))} D{s.get('day','?')} Y{s.get('year','?')}")
        elif t == "friendship":
            parts.append(f"{tr_item(s.get('villager', '?'))} {s.get('hearts','?')}心")
        elif t == "skill":
            parts.append(f"{s.get('skill','?')} Lv{s.get('level','?')}")
        elif t == "shop":
            parts.append(f"购买: {s.get('shop','?')} {s.get('price','?')}g")
        elif t == "island-trade":
            parts.append("姜岛商人兑换")
        else:
            parts.append(str(t))
    return "、".join(parts)


# ═══════════════════════════════════════════════════════════════
# 格式化函数 — 把数据转成 AI 可读的文本
# ═══════════════════════════════════════════════════════════════

def format_crop(c: dict) -> str:
    seasons = "、".join(tr_season(s) for s in c.get("seasons", []))
    seeds = c.get("seedBuyPrices", [])
    seed_str = " / ".join(f"{s['place']}:{s['price']}g" for s in seeds) if seeds else "?"
    regrow = f"，之后每{c['regrowDays']}天可再收获" if c.get("regrowDays") else ""
    hq = _fmt_harvest_quantity(c.get("harvestQuantity"))
    hq_str = f" | 每次收获：{hq}个" if hq else ""
    artisan = _fmt_artisan_uses(c.get("artisanUses"))
    artisan_str = f"\n加工：{artisan}" if artisan else ""
    trellis = "\n【需要架子】" if c.get("trellis") else ""
    giant = "\n【可长成巨型作物】" if c.get("giant") else ""
    xp = c.get("farmingXP", 0)
    xp_str = f" | 经验：+{xp}XP" if xp else ""
    eh = c.get("energyHealth", {})
    return (
        f"[作物] {tr_crop(c['name'])}（{tr_category(c.get('category', ''))}）\n"
        f"季节：{seasons} | 生长：{c['growDays']}天成熟{regrow}{hq_str}{xp_str}\n"
        f"售价：{c['cropSellPrice']}g | 种子：{tr_item(c.get('seedName', '?'))}（{seed_str}）\n"
        f"食用：+{eh.get('energy', '?')}体力 +{eh.get('health', '?')}生命"
        f"{artisan_str}{trellis}{giant}\n"
        f"[注意] 此作物只在 {seasons} 生长。换季时（如进入冬季）会枯萎死亡，需重新种植。温室和姜岛可全年种植。\n"
        f"{c.get('description', '')}"
    )


def format_fish(f: dict) -> str:
    seasons = "、".join(tr_season(s) for s in f.get("seasons", []))
    eh = f.get("energyHealth", {})
    pond = f.get("fishPond")
    pond_str = ""
    if pond:
        produces = [tr_item(p["product"]) for p in pond.get("produce", [])[:5]]
        pond_str = f"\n鱼塘产出：{'、'.join(produces)}"
    used_in = f.get("usedIn", [])
    used_str = ""
    if used_in:
        used_str = f"\n用途：{'、'.join(tr_item(u) for u in used_in[:6])}"
    smoke_str = " | 可熏制" if f.get("canSmoke") else ""
    return (
        f"[鱼] {tr_fish(f['name'])}（{tr_category(f.get('category', ''))}）{smoke_str}\n"
        f"季节：{seasons} | 天气：{tr_weather(f.get('weather', '?'))} | 时间：{f.get('time', '?')}\n"
        f"地点：{f.get('location', '?')} | 难度：{f.get('difficulty', '?')} | 售价：{f.get('sellPrice', '?')}g\n"
        f"{'[注意] 有毒！' if eh.get('poison') else f'食用：+{eh.get('energy', '?')}体力 +{eh.get('health', '?')}生命'}"
        f"{used_str}{pond_str}\n"
        f"{f.get('description', '')}"
    )


def format_villager(v: dict) -> str:
    bday = v.get("birthday", {})
    bday_str = f"{tr_month(bday.get('season', '?'))} {bday.get('day', '?')}日" if bday else "?"
    loves = "、".join(tr_item(item) for item in v.get("loves", [])[:8])
    likes = "、".join(tr_item(item) for item in v.get("likes", [])[:8])
    dislikes = "、".join(tr_item(item) for item in v.get("dislikes", [])[:8])
    hates = "、".join(tr_item(item) for item in v.get("hates", [])[:8])
    lines = [
        f"[村民] {tr_villager(v['name'])}",
        f"生日：{bday_str} | 住址：{v.get('address', '?')} | 职业：{v.get('occupation', '?')}",
    ]
    if v.get("marriageable"):
        lines.append("[可结婚]")
    if loves:
        lines.append(f"[最爱] {loves}")
    if likes:
        lines.append(f"[喜欢] {likes}")
    if dislikes:
        lines.append(f"[不喜欢] {dislikes}")
    if hates:
        lines.append(f"[讨厌] {hates}")
    lines.append(v.get("description", ""))
    return "\n".join(lines)


def format_cooking(recipe: dict) -> str:
    ingredients = "、".join(
        f"{tr_item(ing['name'])} x{ing['quantity']}" for ing in recipe.get("ingredients", [])
    )
    buffs = recipe.get("buffs", [])
    buff_str = ""
    if buffs:
        dur = _fmt_minutes(recipe.get("buffDuration"))
        buff_str = "\n增益：" + "、".join(
            f"{b.get('stat', b.get('name', '?'))}+{b.get('value', b.get('amount', '?'))}" for b in buffs
        ) + f"（持续{dur}）"
    recipe_src = _fmt_recipe_sources(recipe.get("recipeSources"))
    src_str = f"\n获取：{recipe_src}" if recipe_src else ""
    eh = recipe.get("energyHealth", {})
    return (
        f"[食谱] {tr_cooking(recipe['name'])}\n"
        f"食材：{ingredients}\n"
        f"售价：{recipe.get('sellPrice', '?')}g | "
        f"食用：+{eh.get('energy', '?')}体力 +{eh.get('health', '?')}生命"
        f"{buff_str}{src_str}\n"
        f"{recipe.get('description', '')}"
    )


def format_mineral(m: dict) -> str:
    gem_price = m.get("gemologistPrice")
    price_str = f"售价：{m.get('sellPrice', '?')}g"
    if gem_price:
        price_str += f"（宝石专家：{gem_price}g）"
    return (
        f"[矿物] {tr_mineral(m['name'])}（{m.get('kind', '')}）\n"
        f"{price_str}\n"
        f"出处：{', '.join(m.get('locations', ['未知']))}\n"
        f"{m.get('description', '')}"
    )


def format_weapon(w: dict) -> str:
    return (
        f"[武器] {tr_item(w['name'])}（{w.get('type', '?')}）\n"
        f"伤害：{w.get('damageMin','?')}-{w.get('damageMax','?')} | "
        f"速度：{w.get('speed','?')} | 暴击率：{w.get('critChance', 0)*100:.0f}% | "
        f"防御：{w.get('defense','?')} | 击退：{w.get('knockback','?')}\n"
        f"等级：Lv{w.get('level','?')} | 售价：{w.get('sellPrice','?')}g | "
        f"可附魔：{'是' if w.get('canEnchant') else '否'}\n"
        f"获取：{w.get('obtain', '?')}\n"
        f"{w.get('description', '')}"
    )


def format_ring(r: dict) -> str:
    parts = [f"[戒指] {tr_item(r['name'])}"]
    if r.get("sellPrice"):
        parts.append(f"售价：{r['sellPrice']}g")
    if r.get("purchasePrice"):
        parts.append(f"购买价：{r['purchasePrice']}g")
    ingredients = r.get("ingredients", [])
    if ingredients:
        ing_str = "、".join(f"{tr_item(i['name'])} x{i['quantity']}" for i in ingredients)
        parts.append(f"配方：{ing_str}")
    sources = r.get("sources", [])
    if sources:
        parts.append(f"来源：{'、'.join(sources)}")
    if r.get("description"):
        parts.append(r["description"])
    return "\n".join(parts)


def format_footwear(fw: dict) -> str:
    return (
        f"[鞋子] {tr_item(fw['name'])}\n"
        f"防御：{fw.get('defense', '?')} | 免疫：{fw.get('immunity', '?')} | 售价：{fw.get('sellPrice', '?')}g\n"
        f"获取：{fw.get('obtain', '?')}\n"
        f"{fw.get('description', '')}"
    )


def format_artifact(a: dict) -> str:
    return (
        f"[古物] {tr_item(a['name'])}\n"
        f"售价：{a.get('sellPrice', '?')}g\n"
        f"出处：{', '.join(a.get('locations', ['未知']))}\n"
        f"捐赠：{a.get('donationNotes', a.get('description', ''))}"
    )


def format_forageable(fg: dict) -> str:
    seasons = "、".join(tr_season(s) for s in fg.get("seasons", []))
    eh = fg.get("energyHealth", {})
    artisan = _fmt_artisan_uses(fg.get("artisanUses"))
    artisan_str = f"\n加工：{artisan}" if artisan else ""
    return (
        f"[采集] {tr_item(fg['name'])}\n"
        f"季节：{seasons} | 地点：{fg.get('locations', '?')} | 售价：{fg.get('sellPrice', '?')}g\n"
        f"食用：+{eh.get('energy', '?')}体力 +{eh.get('health', '?')}生命"
        f"{artisan_str}\n"
        f"{fg.get('description', '')}"
    )


def format_artisan_good(ag: dict) -> str:
    parts = [f"[工匠品] {tr_item(ag['name'])}"]
    if ag.get("equipment"):
        parts.append(f"设备：{ag['equipment']}")
    ingredients = ag.get("ingredients", [])
    if ingredients:
        ing_str = "、".join(i.get("name", "?") for i in ingredients)
        parts.append(f"原料：{ing_str}")
    if ag.get("processingDays"):
        parts.append(f"耗时：{ag['processingDays']}天")
    price = ag.get("sellPrice")
    formula = ag.get("sellPriceFormula")
    if price:
        parts.append(f"售价：{price}g")
    elif formula:
        parts.append(f"售价公式：{formula}")
    if ag.get("cask"):
        c = ag["cask"]
        parts.append(f"陈酿：银{c.get('silverDays','?')}天/金{c.get('goldDays','?')}天/铱{c.get('iridiumDays','?')}天")
    eh = ag.get("energyHealth", {})
    if eh:
        parts.append(f"食用：+{eh.get('energy','?')}体力 +{eh.get('health','?')}生命")
    if ag.get("description"):
        parts.append(ag["description"])
    return "\n".join(parts)


def format_trinket(t: dict) -> str:
    return (
        f"[饰品] {tr_item(t['name'])}\n"
        f"效果：{t.get('effect', '?')}\n"
        f"来源：{t.get('source', '?')} | 售价：{t.get('sellPrice', '?')}g\n"
        f"{'可锻造' if t.get('forgeable') else '不可锻造'}"
    )


def format_monster(m: dict) -> str:
    loot_names = []
    if m.get("lootIds"):
        loot_names = [tr_item(lid) for lid in m["lootIds"][:5]]
    loot_str = f"\n掉落：{'、'.join(loot_names)}" if loot_names else ""
    dangerous = "【危险版】" if m.get("dangerous") else ""
    return (
        f"[怪物] {tr_item(m['name'])}{dangerous}\n"
        f"HP：{m.get('hp','?')} | 伤害：{m.get('damage','?')} | 速度：{m.get('speed','?')} | 经验：{m.get('xp','?')}XP\n"
        f"出没：{'、'.join(m.get('locations', ['未知']))}{loot_str}\n"
        f"{m.get('description', '')}"
    )


def format_building(b: dict) -> str:
    materials = "、".join(
        f"{tr_item(m['item'])} x{m['quantity']}" for m in b.get("materials", [])
    )
    return (
        f"[建筑] {tr_item(b['name'])}\n"
        f"建造：{b.get('buildCost','?')}g | 耗时：{b.get('buildDays','?')}天 | 建造者：{b.get('builder','?')}\n"
        f"材料：{materials}\n"
        f"{'魔法建筑' if b.get('magical') else ''}\n"
        f"{b.get('description', '')}"
    )


def format_tree(t: dict) -> str:
    tree_type = t.get("type", "")
    if tree_type == "fruit-tree":
        sapling_prices = " / ".join(
            f"{s['place']}:{s['price']}g" for s in t.get("saplingBuyPrices", [])
        ) or "?"
        seasons = "、".join(tr_season(s) for s in t.get("seasons", []))
        produce = t.get("produce", {})
        produce_str = f"\n果实：{tr_item(produce.get('name', '?'))} 售价{produce.get('sellPrice', '?')}g" if produce else ""
        return (
            f"[果树] {tr_item(t['name'])}（果树）\n"
            f"结果季节：{seasons} | 成熟：{t.get('daysToMature','?')}天\n"
            f"树苗：{tr_item(t.get('saplingName', '?'))}（{sapling_prices}）"
            f"{produce_str}\n"
            f"{t.get('description', '')}"
        )
    else:
        # wild tree
        tapper = t.get("tapper", {})
        tapper_str = f"\n树液采集器产出：{tr_item(tapper.get('name','?'))}（{tapper.get('sellPrice','?')}g）" if tapper else ""
        chopped = "、".join(tr_item(c.get("name", "?")) for c in t.get("choppedProduce", [])[:4])
        return (
            f"[野树] {tr_item(t['name'])}（野树）\n"
            f"种子：{tr_item(t.get('seedName', '?'))}"
            f"{tapper_str}\n"
            f"砍伐掉落：{chopped}\n"
            f"{t.get('description', '')}"
        )


def format_item(item: dict, kind: str) -> str:
    """通用 item 格式化，根据 kind 分发"""
    formatters = {
        "crops": format_crop,
        "fish": format_fish,
        "villagers": format_villager,
        "cooking": format_cooking,
        "minerals": format_mineral,
        "weapons": format_weapon,
        "rings": format_ring,
        "footwear": format_footwear,
        "artifacts": format_artifact,
        "forageables": format_forageable,
        "artisan-goods": format_artisan_good,
        "trinkets": format_trinket,
        "monsters": format_monster,
        "buildings": format_building,
        "trees": format_tree,
    }
    fmt = formatters.get(kind)
    if fmt:
        return fmt(item)

    # 通用格式 — 尽量展示所有非图片、非 ID 的关键字段
    name = tr_item(item.get("name", "?"))
    desc = item.get("description", "")
    parts = [f"[物品] {name}"]

    # 尝试提取常见字段
    for key, label in [
        ("sellPrice", "售价"),
        ("purchasePrice", "购买价"),
        ("effect", "效果"),
        ("obtain", "获取"),
        ("source", "来源"),
        ("obtainedFrom", "获取"),
    ]:
        val = item.get(key)
        if val:
            parts.append(f"{label}：{val}")

    if desc:
        parts.append(desc)
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# 搜索 API — 供 function calling 调用
# ═══════════════════════════════════════════════════════════════

def search_crop(query: str) -> str:
    """搜索作物信息"""
    results = _fuzzy_match(_load("crops"), query, ("name", "seedName"))
    if not results:
        return f"没找到关于「{query}」的作物信息。试试其他关键词？"
    return "\n\n".join(format_crop(c) for c in results[:3])


def search_fish(query: str) -> str:
    """搜索鱼类信息"""
    results = _fuzzy_match(_load("fish"), query)
    if not results:
        return f"没找到关于「{query}」的鱼。试试其他关键词？"
    return "\n\n".join(format_fish(f) for f in results[:3])


def search_villager(query: str) -> str:
    """搜索村民信息"""
    results = _fuzzy_match(_load("villagers"), query)
    if not results:
        return f"没找到关于「{query}」的村民。试试其他关键词？"
    return "\n\n".join(format_villager(v) for v in results[:3])


def search_cooking(query: str) -> str:
    """搜索烹饪食谱"""
    results = _fuzzy_match(_load("cooking"), query)
    if not results:
        return f"没找到关于「{query}」的食谱。试试其他关键词？"
    return "\n\n".join(format_cooking(r) for r in results[:3])


def search_item(query: str) -> str:
    """通用物品搜索：在所有数据模块中查找"""
    found = []
    for module_name in _MODULES:
        items = _load(module_name)
        matches = _fuzzy_match(items, query)
        for m in matches[:2]:  # 每个模块最多 2 条
            found.append((m, module_name))

    if not found:
        return f"在所有数据中都没找到关于「{query}」的信息。"

    lines = []
    for item, kind in found[:5]:  # 总共最多 5 条
        lines.append(format_item(item, kind))
    return "\n\n".join(lines)


def list_module_items(module: str) -> str:
    """列出某个模块的所有条目名称（用于浏览）"""
    if module not in _MODULES:
        available = "、".join(_MODULES.keys())
        return f"未知模块「{module}」。可用模块：{available}"

    items = _load(module)
    names = [item.get("name", "?") for item in items]
    return f"【{_MODULES[module]}】共 {len(names)} 条：\n" + "、".join(names)


# ═══════════════════════════════════════════════════════════════
# Wiki 搜索（懒加载，避免启动时就引入 Chrome 等依赖）
# ═══════════════════════════════════════════════════════════════

def _wiki_search(query: str) -> str:
    """搜索星露谷中文 Wiki 并返回文本摘要"""
    from urllib.parse import quote

    query = str(query or "").strip()
    if not query:
        return "Wiki 鎼滅储闇€瑕佹彁渚涘叧閿瘝銆?"

    try:
        from modules.wiki.stardew import (
            WikiRequestError,
            get_direct_page_summary,
            get_page_full_text,
            get_page_summary,
            get_search_results,
        )
    except ImportError as e:
        return f"Wiki 搜索模块加载失败: {e}"

    WIKI_PAGE_BASE = str(section("wiki.stardew")["page_base_url"])

    # URLs of utility/special pages that are never relevant game content
    _UTILITY_PAGE_PATTERNS = [
        "特殊:",
        "Special:",
        "帮助:",
        "Help:",
        "星露谷物语中文百科:",
        "分类:",
        "Category:",
        "模板:",
        "Template:",
        "物品编号",
        "测试页面",
    ]

    def _is_relevant_result(result: dict) -> bool:
        """Filter out utility/special pages from search results."""
        title = result.get("title", "")
        url = result.get("url", "")
        for pat in _UTILITY_PAGE_PATTERNS:
            if pat in title or pat in url:
                return False
        return True

    def _maybe_fetch_full(summary: str, url: str) -> str:
        """If the summary is just a bare URL (no infobox), use AI summarizer or fall back to full page text."""
        if summary and not summary.startswith("Wiki链接："):
            return summary

        # 优先用 AI 摘要（deepseek-v4-flash + 两步法 prompt），失败再回落原始全文
        try:
            from modules.wiki.summarize import summarize_wiki_page
            ai_summary = summarize_wiki_page(url)
            if ai_summary:
                return f"{ai_summary}\n\nWiki链接：{url}"
        except Exception:
            pass

        full = get_page_full_text(url)
        return full if full else summary

    def _try_search_results(query_str: str) -> str | None:
        """Search with a query, filtering irrelevant results. Returns summary or None."""
        results = get_search_results(query_str, limit=8)
        if not results:
            return None
        for r in results:
            if not _is_relevant_result(r):
                continue
            summary = get_page_summary(r["url"])
            if summary:
                return _maybe_fetch_full(summary, r["url"])
        return None

    try:
        # 1. Direct page lookup
        summary = get_direct_page_summary(query)
        if summary:
            url = WIKI_PAGE_BASE + quote(query, safe="/")
            return _maybe_fetch_full(summary, url)

        # 2. Search with full query, filtering irrelevant results
        result = _try_search_results(query)
        if result:
            return result

        # 3. Fallback: try individual words from the query
        words = query.replace("，", " ").replace(",", " ").split()
        if len(words) > 1:
            for word in words:
                if len(word) <= 1:
                    continue
                # First try direct page match
                summary = get_direct_page_summary(word)
                if summary:
                    url = WIKI_PAGE_BASE + quote(word, safe="/")
                    return _maybe_fetch_full(summary, url)
                # Then try search
                result = _try_search_results(word)
                if result:
                    return result

        return f"Wiki 上没有找到关于「{query}」的内容。建议换个关键词试试。"

    except WikiRequestError as e:
        return f"Wiki 查询失败（状态码 {e.status_code}），请稍后再试。"
    except Exception as e:
        return f"Wiki 查询出错: {e}"


# ═══════════════════════════════════════════════════════════════
# Tool 执行分发
# ═══════════════════════════════════════════════════════════════

def search_game_data(query: str, category: str) -> str:
    """统一游戏数据搜索入口，根据 category 分发到对应的搜索函数"""
    handlers = {
        "crop": search_crop,
        "fish": search_fish,
        "villager": search_villager,
        "cooking": search_cooking,
        "item": search_item,
    }
    handler = handlers.get(category)
    if handler:
        return handler(query)
    return f"未知类别「{category}」。可用类别：crop, fish, villager, cooking, item"


TOOL_HANDLERS = {
    "search_game_data": lambda args: search_game_data(
        args.get("query", ""), args.get("category", "")
    ),
    "search_crop": lambda args: search_crop(args.get("query", "")),
    "search_fish": lambda args: search_fish(args.get("query", "")),
    "search_villager": lambda args: search_villager(args.get("query", "")),
    "search_cooking": lambda args: search_cooking(args.get("query", "")),
    "search_item": lambda args: search_item(args.get("query", "")),
    "list_module": lambda args: list_module_items(args.get("module", "")),
    "search_wiki": lambda args: _wiki_search(args.get("query", "")),
}


def execute_tool(name: str, arguments: dict) -> str:
    """执行工具调用，返回结果文本"""
    handler = TOOL_HANDLERS.get(name)
    if handler:
        return str(handler(arguments if isinstance(arguments, dict) else {}))
    return f"未知工具：{name}"
