"""OneBot 事件路由入口。具体功能处理仍由 handlers 模块实现。"""

from bot.handlers import dispatch_group_event

__all__ = ["dispatch_group_event"]
