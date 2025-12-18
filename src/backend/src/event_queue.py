"""
事件队列管理器

用于在工具执行过程中实时发送 AG-UI 事件
"""
import asyncio
from typing import Dict, Any, Optional
from ag_ui.core import StateSnapshotEvent, EventType
from dataclasses import dataclass
import json


@dataclass
class EventQueueManager:
    """管理每个 run_id 的事件队列"""
    queues: Dict[str, asyncio.Queue] = None
    
    def __post_init__(self):
        if self.queues is None:
            self.queues = {}
    
    def get_queue(self, run_id: str) -> asyncio.Queue:
        """获取或创建指定 run_id 的事件队列"""
        if run_id not in self.queues:
            self.queues[run_id] = asyncio.Queue()
        return self.queues[run_id]
    
    async def push_event(self, run_id: str, event: Any):
        """向指定 run_id 的队列推送事件"""
        queue = self.get_queue(run_id)
        await queue.put(event)
    
    async def push_state_snapshot(self, run_id: str, state: Any):
        """推送状态快照事件"""
        event = StateSnapshotEvent(
            type=EventType.STATE_SNAPSHOT,
            snapshot=state.model_dump() if hasattr(state, 'model_dump') else state
        )
        await self.push_event(run_id, event)
    
    def remove_queue(self, run_id: str):
        """移除指定 run_id 的队列"""
        if run_id in self.queues:
            del self.queues[run_id]


# 全局事件队列管理器
event_manager = EventQueueManager()



