"""星露谷物语数据中英翻译映射表"""

# ═══════════════════════════════════════════════════════════════
# 枚举值
# ═══════════════════════════════════════════════════════════════

SEASONS = {
    "spring": "春季",
    "summer": "夏季",
    "fall": "秋季",
    "winter": "冬季",
    "ginger island": "姜岛",
}

WEATHER = {
    "sunny": "晴天",
    "rainy": "雨天",
    "both": "任意天气",
    "rain": "雨天",
    "snow": "雪天",
    "storm": "暴风雨",
    "green rain": "绿雨",
    "festival": "节日",
    "windy": "刮风天",
    "any": "任意天气",
}

CATEGORY = {
    "fruit": "水果",
    "vegetable": "蔬菜",
    "flower": "花",
    "forage": "采集品",
    "seed": "种子",
    "resource": "资源",
    "special": "特殊",
    "regular": "普通鱼",
    "legendary": "传说鱼",
    "legendary-2": "二代传说鱼",
    "crab-pot": "蟹笼",
    "night-market": "夜市鱼",
    "other": "其他",
    "mineral": "矿物",
    "gem": "宝石",
    "artifact": "古物",
    "ring": "戒指",
    "weapon": "武器",
    "tool": "工具",
    "hat": "帽子",
    "footwear": "鞋子",
    "building": "建筑",
    "animal": "动物",
    "tree": "树",
    "artisan-good": "工匠制品",
    "bait": "鱼饵",
    "tackle": "渔具",
    "trinket": "饰品",
}

SKILLS = {
    "Farming": "耕种",
    "Fishing": "钓鱼",
    "Foraging": "采集",
    "Mining": "采矿",
    "Combat": "战斗",
}

MONTHS = {
    "spring": "春季",
    "summer": "夏季",
    "fall": "秋季",
    "winter": "冬季",
}

# ═══════════════════════════════════════════════════════════════
# 作物 (47)
# ═══════════════════════════════════════════════════════════════

CROPS = {
    "Parsnip": "防风草",
    "Green Bean": "绿豆",
    "Cauliflower": "花椰菜",
    "Potato": "土豆",
    "Garlic": "大蒜",
    "Kale": "甘蓝",
    "Rhubarb": "大黄",
    "Strawberry": "草莓",
    "Unmilled Rice": "未碾米",
    "Tulip": "郁金香",
    "Blue Jazz": "蓝爵",
    "Coffee Bean": "咖啡豆",
    "Poppy": "罂粟",
    "Summer Spangle": "夏季亮片",
    "Sunflower": "向日葵",
    "Blueberry": "蓝莓",
    "Corn": "玉米",
    "Hops": "啤酒花",
    "Hot Pepper": "辣椒",
    "Melon": "甜瓜",
    "Radish": "萝卜",
    "Red Cabbage": "红甘蓝",
    "Starfruit": "杨桃",
    "Tomato": "番茄",
    "Wheat": "小麦",
    "Amaranth": "苋菜",
    "Artichoke": "洋蓟",
    "Beet": "甜菜",
    "Bok Choy": "小白菜",
    "Cranberries": "蔓越莓",
    "Eggplant": "茄子",
    "Fairy Rose": "仙女玫瑰",
    "Grape": "葡萄",
    "Pumpkin": "南瓜",
    "Yam": "山药",
    "Ancient Fruit": "上古水果",
    "Cactus Fruit": "仙人掌果",
    "Fiber": "纤维",
    "Pineapple": "菠萝",
    "Taro Root": "芋头",
    "Tea Leaves": "茶叶",
    "Carrot": "胡萝卜",
    "Powdermelon": "霜瓜",
    "Broccoli": "西兰花",
    "Summer Squash": "夏南瓜",
    "Moss": "苔藓",
    "Qi Fruit": "齐瓜",
}

# ═══════════════════════════════════════════════════════════════
# 鱼 (77)
# ═══════════════════════════════════════════════════════════════

FISH = {
    "Pufferfish": "河豚",
    "Anchovy": "鳀鱼",
    "Tuna": "金枪鱼",
    "Sardine": "沙丁鱼",
    "Bream": "鳊鱼",
    "Largemouth Bass": "大口黑鲈",
    "Smallmouth Bass": "小口黑鲈",
    "Rainbow Trout": "虹鳟鱼",
    "Salmon": "鲑鱼",
    "Walleye": "大眼鱼",
    "Perch": "鲈鱼",
    "Carp": "鲤鱼",
    "Catfish": "鲶鱼",
    "Pike": "狗鱼",
    "Sunfish": "太阳鱼",
    "Red Mullet": "红鲻鱼",
    "Herring": "鲱鱼",
    "Eel": "鳗鱼",
    "Octopus": "章鱼",
    "Red Snapper": "红鲷鱼",
    "Squid": "鱿鱼",
    "Sea Cucumber": "海参",
    "Super Cucumber": "超级海参",
    "Ghostfish": "鬼鱼",
    "Stonefish": "石头鱼",
    "Ice Pip": "冰管鱼",
    "Lava Eel": "熔岩鳗鱼",
    "Sandfish": "沙鱼",
    "Scorpion Carp": "蝎子鲤",
    "Flounder": "比目鱼",
    "Midnight Carp": "午夜鲤",
    "Sturgeon": "鲟鱼",
    "Tiger Trout": "虎纹鳟鱼",
    "Bullhead": "大头鱼",
    "Tilapia": "罗非鱼",
    "Chub": "鲦鱼",
    "Dorado": "多宝鱼",
    "Lingcod": "蛇齿单线鱼",
    "Halibut": "大比目鱼",
    "Woodskip": "木跃鱼",
    "Void Salmon": "虚空鲑鱼",
    "Slimejack": "史莱姆鱼",
    "Midnight Squid": "午夜鱿鱼",
    "Spook Fish": "幽灵鱼",
    "Blobfish": "水滴鱼",
    "Albacore": "长鳍金枪鱼",
    "Shad": "美洲西鲱",
    "Crimsonfish": "绯红鱼",
    "Angler": "安康鱼",
    "Legend": "传说之鱼",
    "Glacierfish": "冰河鱼",
    "Mutant Carp": "变异鲤",
    "Crayfish": "小龙虾",
    "Snail": "蜗牛",
    "Periwinkle": "海螺",
    "Mussel": "贻贝",
    "Cockle": "鸟蛤",
    "Clam": "蛤蜊",
    "Lobster": "龙虾",
    "Crab": "螃蟹",
    "Shrimp": "虾",
    "Oyster": "牡蛎",
    "Lionfish": "狮子鱼",
    "Blue Discus": "蓝铁饼鱼",
    "Stingray": "黄貂鱼",
    "Goby": "虾虎鱼",
    "Discus": "铁饼鱼",
    "Void Carp": "虚空鲤",
    "Sea Jelly": "海蜇",
    "River Jelly": "河蜇",
    "Cave Jelly": "洞穴蜇",
    "Mussel Crab": "贻贝蟹",
    "Midge Carp": "蚊鲤",
    "Goldenfish": "金鱼",
    "King Eel": "鳗鱼王",
}

# ═══════════════════════════════════════════════════════════════
# 村民 (34)
# ═══════════════════════════════════════════════════════════════

VILLAGERS = {
    "Abigail": "阿比盖尔",
    "Alex": "亚历克斯",
    "Caroline": "卡洛琳",
    "Clint": "克林特",
    "Demetrius": "德米特里厄斯",
    "Dwarf": "矮人",
    "Elliott": "艾利欧特",
    "Emily": "艾米丽",
    "Evelyn": "艾芙琳",
    "George": "乔治",
    "Gus": "格斯",
    "Haley": "海莉",
    "Harvey": "哈维",
    "Jas": "贾斯",
    "Jodi": "乔迪",
    "Kent": "肯特",
    "Krobus": "科罗布斯",
    "Leah": "莉亚",
    "Leo": "雷欧",
    "Lewis": "刘易斯",
    "Linus": "莱纳斯",
    "Marnie": "玛妮",
    "Maru": "玛鲁",
    "Pam": "潘姆",
    "Penny": "潘妮",
    "Pierre": "皮埃尔",
    "Robin": "罗宾",
    "Sam": "山姆",
    "Sandy": "桑迪",
    "Sebastian": "塞巴斯蒂安",
    "Shane": "谢恩",
    "Vincent": "文森特",
    "Willy": "威利",
    "Wizard": "法师",
}

# ═══════════════════════════════════════════════════════════════
# 食谱 (81)
# ═══════════════════════════════════════════════════════════════

COOKING = {
    "Fried Egg": "煎蛋",
    "Omelet": "煎蛋卷",
    "Salad": "沙拉",
    "Cheese Cauliflower": "芝士花椰菜",
    "Baked Fish": "烤鱼",
    "Parsnip Soup": "防风草汤",
    "Vegetable Medley": "蔬菜杂烩",
    "Complete Breakfast": "完美早餐",
    "Fried Calamari": "炸鱿鱼",
    "Strange Bun": "奇怪的面包",
    "Lucky Lunch": "幸运午餐",
    "Fried Mushroom": "炒蘑菇",
    "Pizza": "披萨",
    "Bean Hotpot": "豆类火锅",
    "Glazed Yams": "糖渍山药",
    "Carp Surprise": "鲤鱼惊喜",
    "Hashbrowns": "薯饼",
    "Pancakes": "煎饼",
    "Salmon Dinner": "鲑鱼晚餐",
    "Fish Taco": "鱼肉卷",
    "Crispy Bass": "香酥鲈鱼",
    "Pepper Poppers": "辣椒爆炒",
    "Bread": "面包",
    "Tom Kha Soup": "冬阴功汤",
    "Trout Soup": "鳟鱼汤",
    "Chocolate Cake": "巧克力蛋糕",
    "Pink Cake": "粉色蛋糕",
    "Rhubarb Pie": "大黄派",
    "Cookie": "饼干",
    "Spaghetti": "意大利面",
    "Fried Eel": "炒鳗鱼",
    "Spicy Eel": "香辣鳗鱼",
    "Sashimi": "生鱼片",
    "Maki Roll": "寿司卷",
    "Tortilla": "墨西哥薄饼",
    "Red Plate": "红色拼盘",
    "Eggplant Parmesan": "茄子帕尔玛",
    "Rice Pudding": "米饭布丁",
    "Ice Cream": "冰淇淋",
    "Blueberry Tart": "蓝莓馅饼",
    "Autumn's Bounty": "秋日恩赐",
    "Pumpkin Soup": "南瓜汤",
    "Super Meal": "超级大餐",
    "Cranberry Sauce": "蔓越莓酱",
    "Stuffing": "填馅",
    "Farmer's Lunch": "农夫午餐",
    "Survival Burger": "生存汉堡",
    "Dish O' the Sea": "海之风味",
    "Miner's Treat": "矿工特供",
    "Roots Platter": "根茎拼盘",
    "Triple Shot Espresso": "三倍浓缩咖啡",
    "Seafoam Pudding": "海泡布丁",
    "Algae Soup": "海藻汤",
    "Pale Broth": "清汤",
    "Plum Pudding": "李子布丁",
    "Bruschetta": "意式烤面包",
    "Coleslaw": "卷心菜沙拉",
    "Fiddlehead Risotto": "蕨菜烩饭",
    "Poi": "芋泥",
    "Fish Stew": "炖鱼",
    "Lobster Bisque": "龙虾浓汤",
    "Maple Bar": "枫糖棒",
    "Crab Cakes": "蟹饼",
    "Shrimp Cocktail": "虾仁鸡尾酒",
    "Ginger Ale": "姜汁汽水",
    "Banana Pudding": "香蕉布丁",
    "Mango Sticky Rice": "芒果糯米饭",
    "Tropical Curry": "热带咖喱",
    "Squid Ink Ravioli": "墨汁意饺",
    "Escargot": "法式蜗牛",
    "Artichoke Dip": "洋蓟蘸酱",
    "Cheese": "奶酪",
    "Mead": "蜂蜜酒",
    "Pale Ale": "淡色艾尔",
    "Wine": "果酒",
    "Juice": "果汁",
    "Coffee": "咖啡",
    "Green Tea": "绿茶",
    "Truffle Oil": "松露油",
    "Oil": "油",
    "Garlic Oil": "大蒜油",
}

# ═══════════════════════════════════════════════════════════════
# 矿物 (精选常见)
# ═══════════════════════════════════════════════════════════════

MINERALS = {
    "Amethyst": "紫水晶",
    "Aquamarine": "海蓝宝石",
    "Diamond": "钻石",
    "Emerald": "绿宝石",
    "Ruby": "红宝石",
    "Topaz": "黄宝石",
    "Jade": "翡翠",
    "Fire Quartz": "火石英",
    "Frozen Tear": "冰封之泪",
    "Earth Crystal": "地晶",
    "Quartz": "石英",
    "Tigerseye": "虎眼石",
    "Opal": "蛋白石",
    "Fire Opal": "火蛋白石",
    "Obsidian": "黑曜石",
    "Prismatic Shard": "五彩碎片",
    "Iridium Ore": "铱矿石",
    "Gold Ore": "金矿石",
    "Iron Ore": "铁矿石",
    "Copper Ore": "铜矿石",
    "Coal": "煤炭",
    "Helvite": "日光榴石",
    "Neptunite": "柱星叶石",
    "Bixite": "方铋矿",
    "Baryte": "重晶石",
    "Aerinite": "气晶石",
    "Alamite": "钠沸石",
    "Calcite": "方解石",
    "Celestine": "天青石",
    "Esperite": "硅锌钙石",
    "Fairy Stone": "仙女石",
    "Fluorapatite": "氟磷灰石",
    "Geminite": "锗钙石",
    "Ghost Crystal": "幽灵水晶",
    "Granite": "花岗岩",
    "Hematite": "赤铁矿",
    "Jagoite": "硅钙铁石",
    "Jamborite": "水硅镍矿",
    "Jasper": "碧玉",
    "Kyanite": "蓝晶石",
    "Lemon Stone": "柠檬石",
    "Limestone": "石灰岩",
    "Lunarite": "月球石",
    "Malachite": "孔雀石",
    "Marble": "大理石",
    "Mudstone": "泥岩",
    "Nekoite": "硅钙石",
    "Ocean Stone": "海洋石",
    "Orpiment": "雌黄",
    "Petrified Slime": "石化史莱姆",
    "Pyrite": "黄铁矿",
    "Sandstone": "砂岩",
    "Slate": "板岩",
    "Soapstone": "皂石",
    "Star Shards": "星之碎片",
    "Thunder Egg": "雷蛋",
    "Marble Brazier": "大理石火炬",
}

# ═══════════════════════════════════════════════════════════════
# 通用物品 (常见搜索频率高的)
# ═══════════════════════════════════════════════════════════════

ITEMS = {
    "Battery Pack": "电池组",
    "Clay": "黏土",
    "Fiber": "纤维",
    "Hardwood": "硬木",
    "Wood": "木材",
    "Stone": "石头",
    "Iridium Bar": "铱锭",
    "Gold Bar": "金锭",
    "Iron Bar": "铁锭",
    "Copper Bar": "铜锭",
    "Refined Quartz": "精炼石英",
    "Bomb": "炸弹",
    "Cherry Bomb": "樱桃炸弹",
    "Mega Bomb": "超级炸弹",
    "Sprinkler": "洒水器",
    "Quality Sprinkler": "优质洒水器",
    "Iridium Sprinkler": "铱洒水器",
    "Scarecrow": "稻草人",
    "Keg": "小桶",
    "Preserves Jar": "罐头瓶",
    "Cask": "木桶",
    "Bee House": "蜂房",
    "Cheese Press": "压酪机",
    "Mayonnaise Machine": "蛋黄酱机",
    "Oil Maker": "产油机",
    "Loom": "织布机",
    "Furnace": "熔炉",
    "Charcoal Kiln": "煤炭窑",
    "Crystalarium": "宝石复制机",
    "Seed Maker": "种子制造机",
    "Recycling Machine": "回收机",
    "Worm Bin": "虫饵盒",
    "Slime Incubator": "史莱姆孵化器",
    "Slime Egg-Press": "史莱姆压蛋器",
    "Bone Mill": "碎骨机",
    "Geode Crusher": "晶洞破碎机",
    "Heavy Tapper": "重型树液采集器",
    "Tapper": "树液采集器",
    "Lightning Rod": "避雷针",
    "Solar Panel": "太阳能板",
    "Deconstructor": "分解机",
    "Hopper": "漏斗",
    "Farm Computer": "农场电脑",
    "Ancient Seeds": "上古种子",
    "Mixed Seeds": "混合种子",
    "Tea Sapling": "茶树苗",
    "Maple Seed": "枫树种子",
    "Acorn": "橡子",
    "Pine Cone": "松果",
    "Mahogany Seed": "桃花心木种子",
    "Fairy Dust": "仙女之尘",
    "Magic Rock Candy": "魔法冰糖",
    "Treasure Chest": "宝箱",
    "Golden Pumpkin": "黄金南瓜",
    "Pearl": "珍珠",
    "Dinosaur Egg": "恐龙蛋",
    "Dinosaur Mayonnaise": "恐龙蛋黄酱",
    "Void Egg": "虚空蛋",
    "Void Mayonnaise": "虚空蛋黄酱",
    "Ostrich Egg": "鸵鸟蛋",
    "Golden Egg": "金蛋",
    "Duck Egg": "鸭蛋",
    "Duck Feather": "鸭毛",
    "Rabbit's Foot": "兔子的脚",
    "Truffle": "松露",
    "Truffle Oil": "松露油",
    "Goat Cheese": "山羊奶酪",
    "Large Egg": "大鸡蛋",
    "Large Milk": "大壶牛奶",
    "Maple Syrup": "枫糖浆",
    "Oak Resin": "橡树树脂",
    "Pine Tar": "松焦油",
    "Honey": "蜂蜜",
    "Wild Honey": "野蜂蜜",
    "Mead": "蜂蜜酒",
    "Beer": "啤酒",
    "Pale Ale": "淡色艾尔",
    "Wine": "果酒",
    "Juice": "果汁",
    "Jelly": "果酱",
    "Pickles": "泡菜",
    "Caviar": "鱼子酱",
    "Aged Roe": "陈年鱼籽",
    "Roe": "鱼籽",
    "Cloth": "布料",
    "Bug Meat": "虫肉",
    "Slime": "史莱姆泥",
    "Bat Wing": "蝙蝠翅膀",
    "Solar Essence": "太阳精华",
    "Void Essence": "虚空精华",
    "Dragon Tooth": "龙牙",
    "Cinder Shard": "火山碎片",
    "Radioactive Ore": "放射性矿石",
    "Radioactive Bar": "放射性锭",
    "Moss": "苔藓",
    "Mystic Syrup": "神秘糖浆",
}


# ═══════════════════════════════════════════════════════════════
# 翻译函数
# ═══════════════════════════════════════════════════════════════

def tr_crop(name: str) -> str:
    """翻译作物名"""
    return CROPS.get(name, name)

def tr_fish(name: str) -> str:
    """翻译鱼名"""
    return FISH.get(name, name)

def tr_villager(name: str) -> str:
    """翻译村民名"""
    return VILLAGERS.get(name, name)

def tr_cooking(name: str) -> str:
    """翻译食谱名"""
    return COOKING.get(name, name)

def tr_mineral(name: str) -> str:
    """翻译矿物名"""
    return MINERALS.get(name, name)

def tr_item(name: str) -> str:
    """通用物品翻译"""
    if name in CROPS: return CROPS[name]
    if name in FISH: return FISH[name]
    if name in COOKING: return COOKING[name]
    if name in MINERALS: return MINERALS[name]
    if name in VILLAGERS: return VILLAGERS[name]
    if name in ITEMS: return ITEMS[name]
    return name

def tr_season(season: str) -> str:
    return SEASONS.get(season.lower(), season)

def tr_weather(w: str) -> str:
    return WEATHER.get(w.lower(), w)

def tr_category(cat: str) -> str:
    return CATEGORY.get(cat.lower(), cat)

def tr_skill(skill: str) -> str:
    return SKILLS.get(skill, skill)

def tr_month(month: str) -> str:
    return MONTHS.get(month.lower(), month)
