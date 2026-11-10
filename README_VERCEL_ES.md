# Bot de Telegram E-commerce en Vercel

Adaptación del repositorio `raulpy271/telegram_ecommerce` para procesar actualizaciones con webhook en una función serverless.

## Variables de entorno
Configura en Vercel como variables privadas:
- `BOT_TOKEN`: token de tu bot creado con @BotFather.
- `TELEGRAM_WEBHOOK_SECRET`: secreto aleatorio largo (solo letras, números, `_` o `-`).
- `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: credenciales de tu proyecto Supabase (conexión PostgreSQL).
- `DB_PORT`: opcional; si se omite o está vacío, el código usa `5432` para PostgreSQL. Si eliges el pooler de transacciones de Supabase, usa el puerto que muestra Supabase (a menudo `6543`).
- `DB_DIALECT`: opcional; por defecto `postgresql`. Solo define `mysql` si conectas una base MySQL.
- `DB_SSLMODE`: opcional; por defecto `require` para cifrar la conexión PostgreSQL.
- `ADMINS`: usernames de administradores separados por comas.
- `PROVIDER_TOKEN`: opcional, para pagos de Telegram.

No subas `.env` ni tokens al repositorio. La conexión se construye con `SQLAlchemy URL.create`, que escapa correctamente usuario/contraseña; el puerto se convierte a entero y usa `5432` si falta o está vacío. Para Supabase usa el host, puerto, base de datos y usuario indicados en **Project Settings → Database → Connection string**. Ejecuta `alembic upgrade head` en la base administrada antes de iniciar el bot. La migración del índice FULLTEXT solo se ejecuta en MySQL; la búsqueda ahora funciona en PostgreSQL y MySQL.

## Publicar
1. Importa este repositorio en Vercel y despliega.
2. Configura las variables de entorno y vuelve a desplegar.
3. En Telegram Bot API, llama a `setWebhook` con `url=https://TU-DOMINIO/api` y `secret_token` igual a `TELEGRAM_WEBHOOK_SECRET`. Usa una herramienta segura y no compartas la URL con el token del bot.
4. En Vercel, `api/index.py` se publica directamente en la ruta `/api`; no uses la raíz del dominio ni `/api/webhook`. Comprueba con `https://TU-DOMINIO/api` que la función responde “Telegram webhook is ready at /api; send updates with POST”.
5. Define `BOT_TOKEN` en Vercel → Project → Settings → Environment Variables y vuelve a desplegar. Define también `TELEGRAM_WEBHOOK_SECRET` y usa ese mismo valor al registrar el webhook.
6. Comprueba la configuración en Telegram usando `getWebhookInfo` con el token del bot: el campo `url` debe ser exactamente `https://TU-DOMINIO/api` y `last_error_message` debe estar vacío. Después envía `/start` al bot y revisa los registros de la función `/api` en Vercel; Telegram enviará un POST, no un GET.
7. El endpoint confirma updates con HTTP 200 incluso si falla un manejador para evitar reintentos infinitos. Revisa los logs de Vercel para corregir errores de token, base de datos o permisos; HTTP 200 por sí solo no garantiza que el mensaje se haya procesado.

Si el webhook sigue sin llegar, vuelve a llamar a `setWebhook` con el mismo endpoint y `secret_token` exactamente igual a `TELEGRAM_WEBHOOK_SECRET` (sin espacios ni comillas extra) y confirma que desplegaste el commit más reciente en el dominio al que apunta ese webhook.

## Estado cuando aún no hay base de datos
El webhook responde a `/start` y `/help` sin conexión a la base. Los comandos `/show_categories`, `/search`, `/register` y los comandos de administración avisan qué variables de base faltan en lugar de fallar sin respuesta. Para activar la tienda completa, configura `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT` (opcional; predeterminado 5432) y `DB_DIALECT=postgresql`, y aplica las migraciones con Alembic.

## Limitación importante
El proyecto original guarda estado de conversaciones en memoria; Vercel puede reciclar funciones entre llamadas. Esta adaptación sirve para pruebas y necesita persistencia de conversaciones/pedidos antes de aceptar compras reales. El propio repositorio declara que es una demo educativa no preparada para producción.
