"""AI Function Calling 工具的公开契约。"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_stardew",
            "description": "统一搜索星露谷物语资料。source 可选 auto、local、vanilla_wiki、sve_wiki；结构化数据用 local，原版机制攻略用 vanilla_wiki，SVE 或模组专属内容用 sve_wiki。",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["auto", "local", "vanilla_wiki", "sve_wiki"],
                        "description": "搜索来源；不确定时使用 auto",
                    },
                    "query": {"type": "string", "description": "搜索关键词；local 用英文，其余来源用中文"},
                    "category": {
                        "type": "string",
                        "enum": ["crop", "fish", "villager", "cooking", "item"],
                        "description": "source=local 时可选：crop、fish、villager、cooking、item",
                    },
                },
                "required": ["query"],
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
