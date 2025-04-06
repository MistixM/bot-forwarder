from typing import List

from aiogram.types import (
    MessageEntity
)

from aiogram.utils.markdown import link

async def extract_clean_caption(text: str, entities: List[MessageEntity]) -> str:
    if not text:
        return ""

    for entity in reversed(entities):
        entity_offset = entity.offset

        entity_text = text[entity_offset : entity_offset + entity.length]

        if entity.type == "text_link" and ("t.me" in entity.url or "telegram.org" in entity.url):
            text = text[:entity_offset] + text[entity_offset + entity.length:]
        
        elif entity.type == "text_link":
            text = text[:entity_offset] + link(entity_text, entity.url) + text[entity_offset + entity.length:]

        elif entity.type == "custom_emoji":
            text = text[:entity_offset] + text[entity_offset + entity.length:]
        
        elif entity.type == "mention":
            text = text[:entity_offset] + text[entity_offset + entity.length:]

        elif entity.type == "hashtag":
            text = text[:entity_offset] + text[entity_offset + entity.length:]

    return text.strip()