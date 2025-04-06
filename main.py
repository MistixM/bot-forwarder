import asyncio
import re
import configparser

from typing import List

# For matches
from difflib import get_close_matches

# Aiogram
from aiogram.filters import CommandStart, Command
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    MessageEntity
)

# Utils
from utils.middleware import MediaGroupMiddleware
from utils.clean_caption import extract_clean_caption
from utils.translate import translate_text, detect_lang

# Config
config = configparser.ConfigParser()
config.read('config.ini')

# Bot configuration and initialisation
bot = Bot(token=config['Main']['TOKEN'])
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Receive OWNER_ID
owner_id = config['Main']['OWNER_ID']

@router.message(Command(commands=['help']))
async def handle_help(msg: Message):
    chat_id = msg.chat.id
    if not int(owner_id) == chat_id:
        await msg.answer("Sorry, you are not allowed to chat here.")
        return

    await msg.answer("/start - Start process\n/channels - Available channels to post\n/add_channel {channel_id} - Adds new channel to the list.\n/remove_channel {channel_id} - Removes channel from the list.")

@router.message(CommandStart())
async def handle_start(msg: Message):

    # Restrict "non-admin" users
    chat_id = msg.chat.id
    if not int(owner_id) == chat_id:
        await msg.answer("Sorry, you are not allowed to chat here.")
        return

    # Simple start process
    full_name = msg.from_user.full_name

    await msg.answer(f"Hello, <b>{full_name}</b>! 👋🏻 \n\nI'm here to remove unnecessary words from your text. Feel free to drop the message and I'll filter it!\n\nUse /help command to discover available commands.",
                     parse_mode='HTML')


@router.message(Command(commands=['channels']))
async def handle_command(msg: Message):

    # Restrict "non-admin" users
    chat_id = msg.chat.id
    if not int(owner_id) == chat_id:
        await msg.answer("Sorry, you are not allowed to chat here.")
        return

    # Receive channel IDs from the config
    channels = config['Main']['CHANNELS'].split(',')

    # Notify if they're empty
    if '' in channels:
        await msg.answer("No available channels. Please use /add_channel {channel_ID} to add channel to the list.")
        return

    # Clean up and drop each new ID row by row
    cleaned = '\n'.join(channel.strip() for channel in channels)

    # Push them to the chat
    await msg.answer(text=f"Available channel IDs: \n\n<b>{cleaned}</b>", parse_mode='HTML')


@router.message(Command(commands=['remove_channel']))
async def handle_command(msg: Message):

    # Restrict "non-admin" users
    chat_id = msg.chat.id
    if not int(owner_id) == chat_id:
        await msg.answer("Sorry, you are not allowed to chat here.")
        return

    # Filter arguments
    args = msg.text.split(maxsplit=1)

    if not len(args) == 2:
        await msg.answer("Please provide a channel ID to remove.")
        return

    if args[1].isalpha() or len(args[1]) != 13:
        await msg.answer("Please enter a correct number for a channel ID. It should be 13 long.")
        return

    # Get channel list
    channels = get_channels()

    # Check if chat exist in the list
    if ('-' + args[1]) in channels:
        channels.remove('-' + args[1])
    else:
        await msg.answer("This ID does not exist.")
        return
    
    # Conver them back to string 
    channels_converted = ','.join(channels)

    # Push changes
    config.set('Main', 'CHANNELS', channels_converted)
    with open('config.ini', 'w') as f:
        config.write(f)

    # Notify user about change
    await msg.answer(f"{('-' + args[1])} removed!")
    

@router.message(Command(commands=['add_channel']))
async def handle_command(msg: Message):

    # Restrict "non-admin" users
    chat_id = msg.chat.id
    if not int(owner_id) == chat_id:
        await msg.answer("Sorry, you are not allowed to chat here.")
        return

    # Filter arguments
    args = msg.text.split(maxsplit=1)

    if not len(args) == 2:
        await msg.answer("Please provide a channel ID to add.")
        return

    if args[1].isalpha() or len(args[1]) != 13:
        await msg.answer("Please enter a correct number for a channel ID. It should be 13 long.")
        return

    # Get channels
    channels = get_channels()

    # Generate correct channel ID
    channel_id = '-' + args[1]
    
    # Check if channel exist in the config
    if channel_id not in channels:
        channels.append(channel_id)
    else:
        await msg.answer("This channel already exists.")
        return

    # Convert list back to string
    channels_converted = ','.join(channels)

    # Push changes
    config.set('Main', 'CHANNELS', channels_converted)
    with open('config.ini', 'w') as f:
        config.write(f)
    
    # Notify about change
    await msg.answer("Alright. Channel ID added!")


@router.message(F.media_group_id)
async def handle_albums(msg: Message, album: List[Message]):

    # Restrict "non-admin" users
    chat_id = msg.chat.id
    if not int(owner_id) == chat_id:
        await msg.answer("Sorry, you are not allowed to chat here.")
        return

    # Create a list to use it for media later
    group_elements = []

    # Get channels
    channels = get_channels()

    # And do some basic check
    if not channels:
        await msg.answer("There're no channels to broadcast.")
        return

    if not (msg.forward_from or msg.forward_from_chat):
        await msg.answer("Message should be forwared.")
        return

    # It's important to check the length of the message caption
    if msg.caption and len(msg.caption) > 1024:
        await msg.answer("Caption is too long. I can't process it.")
        return

    # Iterate over each item in the album
    for element in album:

        # Extract caption
        text = element.caption

        # Clean up the caption from the "watermark texts"
        clean_caption = await extract_clean_caption(text, element.caption_entities)
        
        # Just to make it more friendly. Move all the available links to the bottom of the message
        clean_caption = move_links_to_end(clean_caption)

        # Generate new entities
        entities_data = await extract_entities(text, element.caption_entities or [])

        # Important to check language
        lang = await detect_lang(clean_caption)

        # And translate it, if the message does not contain target language
        if lang != config['Main']['LANG_TO_TRANSLATE']:
            translated_text = await translate_text(clean_caption)

        else:
            translated_text = clean_caption
        
        # Remap those entities
        new_entities = []
        if entities_data:
            new_entities = await remap_entities(translated_text, entities_data)

        # And make them friendly for the Telegram 
        telegram_entities = [
            MessageEntity(type=e[0], offset=e[2], length=e[3]) for e in new_entities
        ] if new_entities else None

        # Remove some unnecessary chars from the text (feel free to append some new)
        chars_to_remove = "|@"
        clean_caption = translated_text.translate(str.maketrans("", "", chars_to_remove))
        
        # Check elements type.
        # And put the correct media to the correct method
        # It's recommended to keep parse_mode as 'None' in the Exception block
        # Some of the messages could have invalid or a bit break markdown, so it's better to handle it
        # and mark it as 'None', so the owner of the channel could fix it manually
        if element.photo:
            try:
                input_media = InputMediaPhoto(media=element.photo[-1].file_id, caption=clean_caption, parse_mode="Markdown", caption_entities=telegram_entities)
            except Exception as e:
                await msg.answer(text=str(e))
                input_media = InputMediaPhoto(media=element.photo[-1].file_id, caption=clean_caption, parse_mode=None, caption_entities=telegram_entities)

        elif element.video:
            try:
                input_media = InputMediaVideo(media=element.video.file_id, caption=clean_caption, parse_mode="Markdown", caption_entities=telegram_entities)
            except Exception as e:
                await msg.answer(text=str(e))
                input_media = InputMediaVideo(media=element.video.file_id, caption=clean_caption, parse_mode=None, caption_entities=telegram_entities)
        
        elif element.document:
            try:
                input_media = InputMediaDocument(media=element.document.file_id, caption=clean_caption, parse_mode='Markdown', caption_entities=telegram_entities)
            except Exception as e:
                await msg.answer(text=str(e))
                input_media = InputMediaDocument(media=element.document.file_id, caption=clean_caption, parse_mode=None, caption_entities=telegram_entities)
        
        elif element.audio:
            try:
                input_media = InputMediaAudio(media=element.audio.file_id, caption=clean_caption, parse_mode='Markdown', caption_entities=telegram_entities)
            except Exception as e: 
                await msg.answer(text=str(e))
                input_media = InputMediaAudio(media=element.audio.file_id, caption=clean_caption, parse_mode=None, caption_entities=telegram_entities)
        
        group_elements.append(input_media)

    # Iterate over each ID and post prepared media group
    for id in channels:
        try:
            await bot.send_media_group(chat_id=id,
                                    media=group_elements)

        except Exception as e:
            await msg.answer(text=f"An unknown error occured: {e}\n\nBecause of the formatting issue in the message.")


@router.message()
async def handle_message(msg: Message):

    # Restrict "non-admin" users
    chat_id = msg.chat.id
    if not int(owner_id) == chat_id:
        await msg.answer("Sorry, you are not allowed to chat here.")
        return

    # Get channels
    channels = get_channels()

    # Do some basic check
    if not channels:
        await msg.answer("There're no channels to broadcast.")
        return

    if not (msg.forward_from or msg.forward_from_chat):
        await msg.answer("Message should be forwared.")
        return

    # Extract text or caption from the message 
    text = msg.text or msg.caption

    # Remove some "watermark texts" from the text
    text = await extract_clean_caption(text, msg.entities if msg.text else msg.caption_entities)

    # It's important to check the length of the message
    if len(text) > 1024:
        await msg.answer("Caption is too long. I can't process it")
        return

    # Create entities data list that we'll use later..
    entities_data = []

    # Check if entities exists
    if msg.entities or msg.caption_entities:
        entities_data = await extract_entities(text, msg.entities if msg.text else msg.caption_entities)
    
    # Translate the text
    lang = await detect_lang(text)
    if lang != config["Main"]["LANG_TO_TRANSLATE"]:
        translated_text = await translate_text(text)
        
    else:
        translated_text = text
    
    # Move links to the bottom of the message
    translated_text = move_links_to_end(translated_text)

    # Remap translated entities
    new_entities = []
    if entities_data:
        new_entities = await remap_entities(translated_text, entities_data)

    # Make entities friendly for Telegram
    telegram_entities = [
        MessageEntity(type=e[0], offset=e[2], length=e[3], url=e[4]) for e in new_entities
    ] if new_entities else None

    # Remove some unnecessary chars
    chars_to_remove = "|@"
    clean_caption = translated_text.translate(str.maketrans("", "", chars_to_remove))

    # Iterate over each channel and send the message
    for id in channels:
        if msg.photo:
            try:
                await bot.send_photo(chat_id=id,
                                    photo=msg.photo[-1].file_id,
                                    caption=clean_caption,
                                    parse_mode='Markdown',
                                    caption_entities=telegram_entities)
                
            except Exception as e:
                await bot.send_photo(chat_id=id,
                                    photo=msg.photo[-1].file_id,
                                    caption=clean_caption,
                                    parse_mode='Markdown',
                                    caption_entities=telegram_entities)
                await msg.answer(text=str(e))
            
        elif msg.video:
            try:
                await bot.send_video(chat_id=id,
                                     video=msg.video.file_id,
                                     caption=clean_caption,
                                     parse_mode='Markdown',
                                     caption_entities=telegram_entities)
                
            except Exception as e:
                await bot.send_video(chat_id=id,
                                     video=msg.video.file_id,
                                     caption=clean_caption,
                                     parse_mode='Markdown',
                                     caption_entities=telegram_entities)
                await msg.answer(text=str(e))
        
        elif msg.document:
            try:
                await bot.send_document(chat_id=id,
                                        document=msg.document.file_id,
                                        caption=clean_caption,
                                        parse_mode='Markdown',
                                        caption_entities=telegram_entities)
                
            except Exception as e:
                await bot.send_document(chat_id=id,
                                        document=msg.document.file_id,
                                        caption=clean_caption,
                                        parse_mode='Markdown',
                                        caption_entities=telegram_entities)
                await msg.answer(text=str(e))
        
        elif msg.text:
            await bot.send_message(chat_id=id,
                                   text=clean_caption,
                                   parse_mode='Markdown' if telegram_entities else None,
                                   entities=telegram_entities)
            


# Iterate over each channel peace and return it
def get_channels() -> list:

    channels_str = config['Main'].get('CHANNELS', '').strip()

    channels = channels_str.split(',') if channels_str else []
    
    return channels


# Move all the links to the bottom using RegEx
def move_links_to_end(text: str) -> str:
    links = re.findall(r'\((https?://[^\s)]+)\)', text)
    cleaned_text = re.sub(r'\s*\(https?://[^\s)]+\)', '', text)
    if links:
        cleaned_text += "\n\n" + "\n".join(links)
    return cleaned_text

# Extract entities from the old one
async def extract_entities(text, entities):
    entities_data = []
    for entity in entities:
        entities_data.append((entity.type, text[entity.offset : entity.offset + entity.length], entity.offset, entity.length, entity.url if not None else ""))
    
    return entities_data

# Remap entities and bring close matches
async def remap_entities(text, entities):
    new_entities = []
    words = text.split()

    for entity_type, entity_text, _, _, url in entities:

        closest_match = get_close_matches(entity_text, words, n=1, cutoff=0.7)

        if closest_match:
            new_offset = text.find(closest_match[0])
            
            new_entities.append((entity_type, closest_match[0], new_offset, len(closest_match[0]), url))

    return new_entities


async def main():
    # Add MediaGroupMiddleware
    router.message.middleware(MediaGroupMiddleware())  
    await dp.start_polling(bot)


if __name__ == "__main__":
    print("Bot started.")
    asyncio.run(main())
    print("Bot stopped.")