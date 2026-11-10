# Bot de Telegram E-commerce en Vercel

Adaptación de `raulpy271/telegram_ecommerce` para procesar actualizaciones mediante webhook en una Vercel Python Function.

## Secretos: nunca dentro del código
No incluyas tokens o contraseñas en archivos Python, README, GitHub ni en el chat. Cifrar un secreto dentro del mismo código/repositorio no lo protege: quien vea el código puede recuperar el valor o la clave. Configura todos los secretos en Vercel → Project → Settings → Environment Variables, marcados como Sensitive/Encrypted:

- `TELEGRAM_BOT_TOKEN`: token de @BotFather. Por compatibilidad, el código también reconoce `BOT_TOKEN` y `botmetatron`.
- `TELEGRAM_WEBHOOK_SECRET`: valor aleatorio (1–256 caracteres, solo A–Z, a–z, 0–9, `_` o `-`). Es obligatorio para aceptar POST.
- `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: credenciales Supabase PostgreSQL.
- `DB_PORT`: puerto de Supabase; si se omite o está vacío, PostgreSQL usa `5432`.
- Opcionales: `DB_DIALECT=postgresql`, `DB_SSLMODE=require`, `ADMINS` y `PROVIDER_TOKEN`.

Selecciona los entornos que uses (Production y Preview si aplica) y vuelve a desplegar cada vez que cambies variables.

## Webhook y autenticación
Vercel sirve `api/index.py` en `/api`. Registra el webhook apuntando a `https://TU-DOMINIO/api` y pasa `secret_token` igual al valor de `TELEGRAM_WEBHOOK_SECRET`. La función compara ese valor con `X-Telegram-Bot-Api-Secret-Token`, usando comparación constante. No confíes únicamente en listas de IP: el secreto del webhook es el mecanismo diseñado para verificar la autenticidad de las solicitudes de Telegram y evita depender de rangos de IP variables.

Comprueba `getWebhookInfo`: `url` debe ser exactamente la ruta del proyecto y `last_error_message` no debe tener error. Un GET a `/api` solo verifica salud; Telegram entrega mensajes por POST.

## Supabase
La URL PostgreSQL se arma con `SQLAlchemy URL.create`, para escapar de forma segura los caracteres de usuario y contraseña. Ejecuta `alembic upgrade head` contra la base externa antes de probar la tienda. La búsqueda y la migración de índice están adaptadas para PostgreSQL además de MySQL.

## Comportamiento sin base configurada
`/start` y `/help` pueden responder sin base de datos. Los comandos de tienda avisan si faltan variables de Supabase. Con base disponible, el endpoint invoca los handlers originales.

## Limitaciones
El proyecto fuente declara que es una demo educativa. Los estados de conversación se guardan en memoria y pueden perderse entre invocaciones serverless; persiste estados y pedidos antes de usar el bot para transacciones reales.
