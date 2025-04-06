# Bot Forwarder
A telegram bot that allows the user to remove unnecessary "water words" from the forwarded message, translates it and send to the specified channel/s.

## Installation
Use the following command to install dependencies:

```pip install -r requirements.txt```

Get into ```config.ini``` file and insert bot token in the ```token``` variable. Then scroll down to the ```lang_to_translate``` and insert the target language to translate. In the ```owner_id``` insert your own Telegram ID (it's necessary for the security purposes)

## Development details
A little description about each file and its functionality.

| File | Description     
| :-------- | :------- 
| `clean_caption.py` | A module that removes unnecessary words from the message and returns clean caption. |
| `middleware.py` | A special module that converts albums into single model that could be scraped and maintend at once. |
| `translate.py` | A module that detects and translates incoming text. |
| `config.ini` | File that contains sensitive information. |