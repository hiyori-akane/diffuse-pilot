"""
設定管理モジュール

環境変数を読み込み、アプリケーション全体で使用する設定を提供します。
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """アプリケーション設定"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Discord Bot Configuration
    discord_bot_token: str = Field(..., description="Discord Bot トークン")

    # Stable Diffusion API Configuration
    sd_api_url: str = Field(default="http://localhost:7860", description="Stable Diffusion API URL")
    sd_api_timeout: int = Field(default=600, description="SD API タイムアウト（秒）")

    # Ollama LLM Configuration
    ollama_api_url: str = Field(default="http://localhost:11434", description="Ollama API URL")
    ollama_model: str = Field(
        default="huihui_ai/qwen3-abliterated:0.6b", description="使用する LLM モデル"
    )

    # Gemini API Configuration
    gemini_api_key: str = Field(default="", description="Gemini API キー")

    # xAI API Configuration
    xai_api_key: str = Field(default="", description="xAI API キー")

    # Database Configuration
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/database.db", description="データベース URL"
    )

    # Storage Configuration
    image_storage_path: Path = Field(
        default=Path("./data/images"), description="画像保存ディレクトリパス"
    )

    # Application Configuration
    log_level: str = Field(default="INFO", description="ログレベル")
    environment: str = Field(default="development", description="実行環境")

    # Default Generation Settings
    default_model: str | None = Field(
        default=None, description="デフォルト SD モデル（環境変数 DEFAULT_MODEL から取得）"
    )
    default_image_count: int = Field(default=4, description="デフォルト画像生成枚数")
    default_width: int = Field(default=512, description="デフォルト画像幅")
    default_height: int = Field(default=512, description="デフォルト画像高さ")
    default_steps: int = Field(default=20, description="デフォルトステップ数")
    default_cfg_scale: float = Field(default=7.0, description="デフォルト CFG スケール")
    default_sampler: str | None = Field(default=None, description="デフォルトサンプラー")
    # Scheduler は未指定時 API の自動選択に委ねるため任意
    default_scheduler: str | None = Field(
        default=None, description="デフォルトスケジューラ（未指定時は送信しない）"
    )

    # Queue Configuration
    queue_error_retry_interval: float = Field(
        default=5.0, description="キューエラー時の再試行間隔（秒）"
    )

    # Web Research (Optional)
    google_search_api_key: str = Field(default="", description="Google Search API キー")
    google_search_engine_id: str = Field(default="", description="Google Search エンジン ID")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 画像保存ディレクトリの作成
        self.image_storage_path.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """設定インスタンスを取得（シングルトン）"""
    return Settings()
