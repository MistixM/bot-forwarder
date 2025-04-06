from googletrans import Translator

import configparser

config = configparser.ConfigParser()
config.read('config.ini')

async def translate_text(text: str) -> str:
    async with Translator() as trans:
        try:
            result = await trans.translate(text, dest=config['Main']['LANG_TO_TRANSLATE'])
        except Exception as e: 
            print("Error while translating text: ", e)
            return
    
        return result.text

async def detect_lang(text: str) -> str:
    async with Translator() as trans:
        result = await trans.detect(text)

        return result.lang