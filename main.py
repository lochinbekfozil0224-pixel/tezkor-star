# ==========================================================
#   MAIN LAUNCHER
#   Bot va FastAPI'ni bir vaqtda parallel ishga tushiradi
# ==========================================================

import asyncio
import logging
import os

import uvicorn

from bot import setup_bot
from api import app as api_app
import database as db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger("main")


async def run_bot():
    """Telegram bot polling"""
    bot, dp = await setup_bot()
    log.info("🤖 Bot polling boshlandi")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def run_api():
    """FastAPI uvicorn server"""
    port = int(os.environ.get("PORT", 8000))
    config = uvicorn.Config(
        api_app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    log.info(f"🌐 API server: http://0.0.0.0:{port}")
    await server.serve()


async def main():
    # Database init
    await db.init_db()
    log.info("✅ Database tayyor")

    # Ikkalasini parallel ishga tushiramiz
    await asyncio.gather(
        run_bot(),
        run_api(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("🛑 To'xtatildi")
