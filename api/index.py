"""Telegram webhook entrypoint for a Vercel Python Function.

Vercel maps this file to /api. Telegram must POST updates to that exact URL.
"""
import asyncio
import json
import logging
import os
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def telegram_json(token, method, payload, timeout=8):
    """Call a Telegram Bot API method without logging or exposing the token."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API {method} returned ok=false")
    return result


def get_bot_token():
    """Read token from Vercel env, preferring the standard key."""
    return (
        os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("BOT_TOKEN")
        or os.getenv("botmetatron")
    )


def handle_start(update, token):
    """Reply directly to /start, avoiding DB imports for this basic interaction."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return False
    text = message.get("text") or ""
    first = text.strip().split(maxsplit=1)[0].split("@", 1)[0].lower() if text.strip() else ""
    if first != "/start":
        return False
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        logger.warning("/start update had no chat id")
        return True
    telegram_json(token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            "¡Hola! Soy el bot de la tienda.\n"
            "Usa /show_categories para ver productos, /search para buscar "
            "y /help para conocer los comandos."
        ),
    })
    return True


def database_configuration_error():
    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    return [name for name in required if not os.getenv(name)]


def handle_without_database(update, token, missing):
    """Keep basic commands usable until database settings are added in Vercel."""
    message = update.get("message") or update.get("edited_message")
    if message:
        text = (message.get("text") or "").strip()
        command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text else ""
        chat_id = (message.get("chat") or {}).get("id")
        if chat_id is None:
            return
        if command == "/help":
            reply = (
                "Comandos disponibles:\\n"
                "/start — iniciar el bot\\n"
                "/help — mostrar esta ayuda\\n"
                "/show_categories — ver el catálogo (requiere configurar Supabase)\\n"
                "/search — buscar productos (requiere configurar Supabase)"
            )
        elif command in ("/show_categories", "/search", "/register", "/add_product", "/add_category"):
            reply = (
                "El bot recibe tus mensajes, pero la tienda aún no está conectada a su base de datos. "
                "El administrador debe configurar en Vercel: " + ", ".join(missing) + "."
            )
        else:
            return
        telegram_json(token, "sendMessage", {"chat_id": chat_id, "text": reply})
        return

    callback = update.get("callback_query")
    if callback and callback.get("id"):
        telegram_json(token, "answerCallbackQuery", {
            "callback_query_id": callback["id"],
            "text": "La tienda aún necesita la configuración de su base de datos.",
            "show_alert": True,
        })


def process_other_update(payload, token):
    """Run the existing python-telegram-bot handlers for non-/start updates."""
    from telegram import Update
    from telegram.ext import ApplicationBuilder
    from telegram_ecommerce.handlers import all_handlers

    async def process():
        app = ApplicationBuilder().token(token).build()
        for telegram_handler in all_handlers:
            app.add_handler(telegram_handler)
        await app.initialize()
        try:
            update = Update.de_json(payload, app.bot)
            await app.process_update(update)
        finally:
            await app.shutdown()

    asyncio.run(process())


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._respond_ok(b"Telegram webhook is ready at /api; send updates with POST")

    def do_POST(self):
        try:
            secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
            provided_secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if secret and provided_secret != secret:
                logger.warning("Webhook secret mismatch; update acknowledged but ignored")
                self._respond_ok()
                return

            # Preferred Vercel variable name; accept existing project names too.
            token = get_bot_token()
            if not token:
                logger.error(
                    "Missing Telegram token: set TELEGRAM_BOT_TOKEN (or legacy BOT_TOKEN/botmetatron)"
                )
                self._respond_ok()
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 1_000_000:
                logger.warning("Webhook received invalid or oversized request body")
                self._respond_ok()
                return

            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if not isinstance(payload, dict):
                logger.warning("Webhook body is not a JSON object")
                self._respond_ok()
                return

            try:
                if not handle_start(payload, token):
                    missing_db = database_configuration_error()
                    if missing_db:
                        logger.error("Missing database environment variables: %s", ", ".join(missing_db))
                        handle_without_database(payload, token, missing_db)
                    else:
                        process_other_update(payload, token)
            except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError):
                logger.exception("Failed to process Telegram update")
            except Exception:
                logger.exception("Unexpected error processing Telegram update")
        except Exception:
            logger.exception("Invalid Telegram webhook request")
        finally:
            # Telegram requires a successful HTTP response; avoid retries on
            # transient handler errors. Keep handler execution quick (< Vercel timeout).
            try:
                # Response is sent exactly once; this is the fallback for errors
                # raised before the regular acknowledgement.
                if not getattr(self, "_response_sent", False):
                    self._respond_ok()
            except Exception:
                logger.exception("Could not send webhook acknowledgement")

    def _respond_ok(self, body=b"ok"):
        self._response_sent = True
        super().send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Avoid logging request details that could contain private data.
        return
