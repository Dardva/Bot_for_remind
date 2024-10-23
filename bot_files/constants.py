import os

from dotenv import load_dotenv

load_dotenv()

ANIMAL_URLS = {
    'cat': 'https://api.thecatapi.com/v1/images/search',
    'dog': 'https://dog.ceo/api/breeds/image/random',
    'fox': 'https://randomfox.ca/floof/',
    'duck': 'https://random-d.uk/api/random',
}

BOT_TOKEN = os.getenv('TOKEN')
BOSS_IDS = os.getenv('BOSS_IDS')
BOSSES = [int(boss) for boss in BOSS_IDS.split(sep=', ')]
