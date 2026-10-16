from typing import Dict, List
import asyncio
from app.models.events import ExecutionEvent

class EventHub:
    def __init__(self):
        self.subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, workflow_id: str, queue: asyncio.Queue):
        if workflow_id not in self.subscribers:
            self.subscribers[workflow_id] = []
        self.subscribers[workflow_id].append(queue)

    def unsubscribe(self, workflow_id: str, queue: asyncio.Queue):
        if workflow_id in self.subscribers:
            if queue in self.subscribers[workflow_id]:
                self.subscribers[workflow_id].remove(queue)
            if not self.subscribers[workflow_id]:
                del self.subscribers[workflow_id]

    async def publish(self, event: ExecutionEvent):
        if event.workflow_id in self.subscribers:
            for queue in self.subscribers[event.workflow_id]:
                await queue.put(event)

hub = EventHub()
