"""AI Function Calling 工具的公开契约。"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web_simple",
            "description": "搜索少量实时网络信息并返回简短文字摘要，不生成或发送图片。用于简单的时效性问题；拿到结果后直接用一到两句话回答，不要追加详细报告。普通闲聊和稳定常识不要调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "网络搜索关键词，尽量简洁，最多 70 个字符",
                    },
                    "recency": {
                        "type": "string",
                        "enum": ["oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"],
                        "description": "时间范围；不限定时使用 noLimit",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "搜索实时网络信息并生成整理报告，同时准备一张简洁的搜索报告图片。用于新闻、最新版本、近期事件、实时价格、对比或其他可能变化的资料。先根据用户问题进行一次精准搜索；收到报告后，如果资料不足、需要核对另一个对象、存在冲突或关键词不匹配，再自行使用不同关键词追加搜索。资料已经足够时不要重复搜索；普通闲聊和稳定常识不要调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "网络搜索关键词，尽量简洁，最多 70 个字符",
                    },
                    "recency": {
                        "type": "string",
                        "enum": ["oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"],
                        "description": "时间范围；不限定时使用 noLimit",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_stardew",
            "description": "统一搜索星露谷物语资料。结构化数据用 local，原版机制攻略用 vanilla_wiki，SVE 或模组专属内容用 sve_wiki。",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["local", "vanilla_wiki", "sve_wiki"],
                        "description": "搜索来源；结构化数据用 local，原版内容用 vanilla_wiki，SVE 内容用 sve_wiki",
                    },
                    "query": {"type": "string", "description": "搜索关键词；local 用英文，其余来源用中文"},
                    "category": {
                        "type": "string",
                        "enum": ["crop", "fish", "villager", "cooking", "item"],
                        "description": "source=local 时可选：crop、fish、villager、cooking、item",
                    },
                },
                "required": ["query", "source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_card",
            "description": "发送一个已注册的星露谷卡片。只有确实有帮助时调用；只能传已知 card_id 和对象参数。",
            "parameters": {
                "type": "object",
                "properties": {
                    "card_id": {
                        "type": "string",
                        "enum": ["mod_tutorial", "mine_distribution", "calendar", "fishing_guide"],
                        "description": "要发送的卡片标识",
                    },
                    "params": {"type": "object", "description": "卡片参数；当前卡片为空对象即可，保留用于以后扩展"},
                },
                "required": ["card_id"],
            },
        },
    },
]
