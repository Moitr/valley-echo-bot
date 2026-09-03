"""AI 卡片动作注册表。模型只能选择注册的 card_id，不能构造 QQ 卡片内容。"""

import json
import os

from config import PROJECT_ROOT, section

_storage = section("storage")
_cards_file = str(PROJECT_ROOT / str(_storage["feed_cards_file"]))

CARD_REGISTRY = {
    "mod_tutorial": {"type": "json"},
    "mine_distribution": {"type": "json"},
    "calendar": {"type": "json"},
    "fishing_guide": {"type": "image", "path": str(PROJECT_ROOT / str(_storage["fishing_image_path"]))},
}


def validate_card_action(card_id, params=None):
    card_id = str(card_id or "").strip()
    params = params if isinstance(params, dict) else {}
    spec = CARD_REGISTRY.get(card_id)
    if not spec:
        return None, f"未知卡片：{card_id}"
    if params:
        return None, f"卡片 {card_id} 暂不接受这些参数"
    return {"card_id": card_id, "params": params}, None


def load_json_card(card_id):
    spec = CARD_REGISTRY.get(card_id)
    if not spec or spec.get("type") != "json":
        return None
    try:
        with open(_cards_file, encoding="utf-8") as f:
            cards = json.load(f)
        return cards.get(card_id) if isinstance(cards, dict) else None
    except (OSError, ValueError):
        return None


def fishing_image_path():
    spec = CARD_REGISTRY.get("fishing_guide")
    path = spec.get("path") if spec else None
    return path if path and os.path.exists(path) else None

