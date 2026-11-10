"""Telegram webhook for Vercel Python Functions (api/index.py -> /api).

Secrets belong in Vercel Environment Variables, never in source control.
"""
import asyncio
import hmac
import json
import logging
import os
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)
MAX_BODY_BYTES = 1_000_000


def telegram_json(token, method, payload, timeout=8):
    """Call Telegram API and sanitize failures so the token never enters logs."""
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok"):
            raise RuntimeError("Telegram API returned ok=false")
        return result
    except Exception as exc:
        # urllib exceptions may include the request URL, which contains BOT_TOKEN.
        raise RuntimeError(f"Telegram API {method} request failed ({type(exc).__name__})") from None


def get_bot_token():
    """Use private Vercel env vars; keep legacy variable names working."""
    return (
        os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("BOT_TOKEN")
        or os.getenv("botmetatron")
    )


def handle_start(update, token):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return False
    text = (message.get("text") or "").strip()
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text else ""
    if command != "/start":
        return False
    chat_id = (message.get("chat") or {}).get("id")
    if chat_id is not None:
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
    return [key for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD") if not os.getenv(key)]


def handle_without_database(update, token, missing):
    message = update.get("message") or update.get("edited_message")
    if message:
        text = (message.get("text") or "").strip()
        command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text else ""
        chat_id = (message.get("chat") or {}).get("id")
        if chat_id is None:
            return
        if command == "/help":
            reply = (
                "Comandos disponibles:\n"
                "/start — iniciar el bot\n"
                "/help — mostrar esta ayuda\n"
                "/show_categories — ver el catálogo (requiere configurar Supabase)\n"
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
    """Run the original bot handlers for updates when database config exists."""
    from telegram import Update
    from telegram.ext import ApplicationBuilder
    from telegram_ecommerce.handlers import all_handlers

    async def process():
        app = ApplicationBuilder().token(token).build()
        for telegram_handler in all_handlers:
            app.add_handler(telegram_handler)
        await app.initialize()
        try:
            await app.process_update(Update.de_json(payload, app.bot))
        finally:
            await app.shutdown()

    asyncio.run(process())


class handler(BaseHTTPRequestHandler):
    def _respond(self, status, body):
        self._response_sent = True
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._respond(200, b"Telegram webhook is ready at /api; updates require authenticated POST")

    def do_POST(self):
        try:
            secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
            provided = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            # Fail closed: never accept Telegram updates without a configured secret.
            if not secret:
                logger.error("TELEGRAM_WEBHOOK_SECRET is not configured")
                self._respond(503, b"Webhook secret is not configured")
                return
            if not hmac.compare_digest(provided, secret):
                logger.warning("Rejected webhook request with invalid Telegram secret header")
                self._respond(403, b"Forbidden")
                return

            token = get_bot_token()
            if not token:
                logger.error("Set TELEGRAM_BOT_TOKEN (legacy BOT_TOKEN/botmetatron are also supported)")
                self._respond(503, b"Bot token is not configured")
                return

            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._respond(400, b"Invalid Content-Length")
                return
            if content_length <= 0 or content_length > MAX_BODY_BYTES:
                self._respond(400, b"Invalid request body size")
                return
            try:
                payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._respond(400, b"Invalid JSON")
                return
            if not isinstance(payload, dict):
                self._respond(400, b"JSON object required")
                return

            try:
                if not handle_start(payload, token):
                    missing_db = database_configuration_error()
                    if missing_db:
                        logger.error("Database configuration missing: %s", ", ".join(missing_db))
                        handle_without_database(payload, token, missing_db)
                    else:
                        process_other_update(payload, token)
            except Exception as exc:
                # Acknowledge valid Telegram updates to avoid endless webhook retries.
                # Never include exception text: it may contain credentials/URLs.
                logger.error("Update processing failed (%s)", type(exc).__name__)
            self._respond(200, b"ok")
        except Exception as exc:
            logger.error("Webhook request failed (%s)", type(exc).__name__)
            if not getattr(self, "_response_sent", False):
                self._respond(200, b"ok")

    def log_message(self, fmt, *args):
        # Avoid access log details and accidental disclosure of private data.
        return
