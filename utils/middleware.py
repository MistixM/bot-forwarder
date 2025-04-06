import asyncio
import configparser

from typing import Any, Awaitable, Callable, Dict, List, Union
from aiogram import BaseMiddleware

from aiogram.types import (
    Message,
    TelegramObject,
)


config = configparser.ConfigParser()
config.read('config.ini')

class MediaGroupMiddleware(BaseMiddleware):
    """Middleware album handler."""
    ALBUM_DATA: Dict[str, List[Message]] = {}

    def __init__(self, delay: Union[int, float] = float(config['Main']['DEFAULT_DELAY'])):
        self.delay = delay

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if not event.media_group_id:
            return await handler(event, data)

        try:
            self.ALBUM_DATA[event.media_group_id].append(event)
            return
        except KeyError:
            self.ALBUM_DATA[event.media_group_id] = [event]
            await asyncio.sleep(self.delay)
            data["album"] = self.ALBUM_DATA.pop(event.media_group_id)

        return await handler(event, data)
