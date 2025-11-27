"""
Bot 起動スクリプト

Discord Bot とキューワーカーを起動します。
"""

import asyncio

from src.config.logging import setup_logging
from src.database.connection import init_db
from src.services.discord_bot import run_bot


async def main():
    """メイン関数"""
    # ログ設定
    setup_logging()

    # データベース初期化
    await init_db()

    # Bot 起動
    await run_bot()


if __name__ == "__main__":
    asyncio.run(main())
