"""AI Function Calling 工具的公开契约。"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_game_data",
            "description": "搜索星露谷物语本地游戏数据。根据 category 指定搜索范围：crop=作物, fish=鱼, villager=村民, cooking=食谱, item=其他所有物品（矿物/武器/戒指/古物/采集品等）。需要同时查多个类别时，在一次回复中并行调用多个 search_game_data。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，必须用英文，如'Parsnip'、'Sturgeon'、'Abigail'、'Chocolate Cake'、'Diamond'"},
                    "category": {
                        "type": "string",
                        "enum": ["crop", "fish", "villager", "cooking", "item"],
                        "description": "搜索类别。crop/作物, fish/鱼, villager/村民, cooking/食谱, item/其他物品",
                    },
                },
                "required": ["query", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_wiki",
            "description": "搜索星露谷物语中文Wiki（wiki.biligame.com）。返回Wiki页面的完整信息。当本地数据查不到、结果不完整、或用户问的是游戏机制/攻略/隐藏内容等本地数据无法覆盖的问题时，直接调用此工具。务必用中文关键词搜索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "要搜索的关键词，如'熔炉'、'祝尼魔'、'姜岛'"},
                },
                "required": ["query"],
            },
        },
    },
]
