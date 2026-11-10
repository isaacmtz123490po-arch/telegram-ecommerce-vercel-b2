
from os import environ

from telegram_ecommerce.utils.utils import create_admins_set

default_language = "en"
currency = "USD"
bot_token = (environ.get("TELEGRAM_BOT_TOKEN") or environ.get("BOT_TOKEN") or environ.get("botmetatron"))
if not bot_token:
    raise RuntimeError("Missing Telegram token: set TELEGRAM_BOT_TOKEN (or legacy BOT_TOKEN/botmetatron)")
provider_token = environ.get("PROVIDER_TOKEN")
admins = create_admins_set(environ.get("ADMINS", ""))
BAD_RATING = 0
REGULAR_RATING = 5
GOOD_RATING = 10


