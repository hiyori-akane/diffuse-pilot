"""
プロンプト生成エージェント

ユーザーの自然言語指示から Stable Diffusion 用のプロンプトとパラメータを生成
"""

import json
import random
from typing import Any

from pydantic import BaseModel, Field

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.models.generation import GenerationMetadata
from src.services.error_handler import LLMAPIError
from src.services.ollama_client import OllamaClient

logger = get_logger(__name__)


class PromptGenerationResponse(BaseModel):
    """プロンプト生成レスポンスのスキーマ"""

    prompt: str = Field(description="生成されたプロンプト（英語、カンマ区切り、詳細に）")
    negative_prompt: str = Field(description="ネガティブプロンプト（英語、カンマ区切り）")
    steps: int = Field(description="生成ステップ数（整数、20-50推奨）", ge=1, le=150)
    cfg_scale: float = Field(
        description="CFG スケール（浮動小数点、5.0-15.0推奨）", ge=1.0, le=30.0
    )
    sampler: str = Field(description="サンプラー名（Euler a, DPM++ 2M Karras 等）")
    width: int = Field(description="画像幅（整数、512, 768, 1024等）", ge=64, le=2048)
    height: int = Field(description="画像高さ（整数、512, 768, 1024等）", ge=64, le=2048)


class PromptAgent:
    """プロンプト生成エージェント"""

    # SD パラメータのキー名リスト（promptとnegative_prompt以外）
    _SD_PARAM_KEYS = ["steps", "cfg_scale", "sampler", "width", "height"]

    def __init__(self):
        self.settings = get_settings()
        self.llm_client = OllamaClient()

    async def close(self):
        """クライアントを閉じる"""
        await self.llm_client.close()

    async def generate_prompt(
        self,
        user_instruction: str,
        previous_metadata: GenerationMetadata | None = None,
        global_settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """ユーザー指示からプロンプトとパラメータを生成

        Args:
            user_instruction: ユーザーの自然言語指示
            previous_metadata: 前回の生成メタデータ（追加指示の場合）
            global_settings: グローバル設定

        Returns:
            生成されたプロンプトとパラメータの辞書

        Raises:
            LLMAPIError: LLM API エラー
        """
        try:
            logger.info(
                f"Generating prompt from user instruction: {user_instruction[:100]}...",
                extra={"has_previous": previous_metadata is not None},
            )

            # システムプロンプト構築
            system_prompt = self._build_system_prompt()

            # ユーザープロンプト構築
            user_prompt = self._build_user_prompt(
                user_instruction, previous_metadata, global_settings
            )

            # LLM で生成
            # JSON schema を生成
            json_schema = PromptGenerationResponse.model_json_schema()

            response_text = await self.llm_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                format=json_schema,
            )

            # レスポンスをパース
            # Ollama の structured outputs で返される JSON を直接パース
            response_data = json.loads(response_text)
            response_model = PromptGenerationResponse(**response_data)

            # 辞書に変換
            result = response_model.model_dump()

            # デフォルト値とマージ
            result = self._apply_defaults(result, previous_metadata, global_settings)

            logger.info(
                f"Prompt generation complete: {len(result['prompt'])} chars",
                extra={"sampler": result.get("sampler"), "steps": result.get("steps")},
            )

            return result

        except Exception as e:
            logger.error(f"Error in prompt generation: {str(e)}")
            if isinstance(e, LLMAPIError):
                raise
            raise LLMAPIError("Failed to generate prompt", original_error=e)

    def _build_system_prompt(self) -> str:
        """システムプロンプトを構築"""
        return """あなたは Stable Diffusion の画像生成に特化したプロンプトエンジニアです。
ユーザーの自然言語の指示から、効果的なプロンプト、ネガティブプロンプト、および最適なパラメータを生成してください。

出力は以下の JSON 形式で返してください：
{
  "prompt": "生成されたプロンプト（英語、カンマ区切り、詳細に）",
  "negative_prompt": "ネガティブプロンプト（英語、カンマ区切り）",
  "steps": 生成ステップ数（整数、20-50推奨）,
  "cfg_scale": CFG スケール（浮動小数点、5.0-15.0推奨）,
  "sampler": "サンプラー名（Euler a, DPM++ 2M Karras 等）",
  "width": 画像幅（整数、512, 768, 1024等）,
  "height": 画像高さ（整数、512, 768, 1024等）
}

プロンプトは具体的で詳細に、品質向上のキーワード（masterpiece, best quality, highly detailed等）を含めてください。
ネガティブプロンプトには一般的な不要要素（worst quality, low quality, blurry等）を含めてください。
"""

    def _build_user_prompt(
        self,
        user_instruction: str,
        previous_metadata: GenerationMetadata | None = None,
        global_settings: dict[str, Any] | None = None,
    ) -> str:
        """ユーザープロンプトを構築"""
        if previous_metadata:
            # 追加指示の場合
            prompt = f"""前回の生成設定：
プロンプト: {previous_metadata.prompt}
ネガティブプロンプト: {previous_metadata.negative_prompt}
ステップ数: {previous_metadata.steps}
CFG スケール: {previous_metadata.cfg_scale}
サンプラー: {previous_metadata.sampler}
サイズ: {previous_metadata.width}x{previous_metadata.height}

ユーザーの追加指示: {user_instruction}

上記の設定を基に、ユーザーの追加指示を反映した新しい設定を生成してください。
変更が不要な項目は前回の値をそのまま使用してください。"""
        else:
            # 新規生成の場合
            prompt = f"ユーザーの指示: {user_instruction}\n\n"

            if global_settings:
                default_prompt_suffix = global_settings.get("default_prompt_suffix")
                if default_prompt_suffix:
                    prompt += f"デフォルトプロンプト（末尾に追加）: {default_prompt_suffix}\n\n"

            prompt += "上記の指示に基づいて、画像生成用のプロンプトとパラメータを生成してください。"

        return prompt

    def _apply_defaults(
        self,
        result: dict[str, Any],
        previous_metadata: GenerationMetadata | None = None,
        global_settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """デフォルト値を適用

        優先順位: グローバル設定 > LLM生成値 > デフォルト値
        ただし、promptとnegative_promptはLLM生成値を優先
        """
        # 前回のメタデータがあればそれを優先
        if previous_metadata:
            defaults = {
                "prompt": previous_metadata.prompt,
                "negative_prompt": previous_metadata.negative_prompt or "",
                "steps": previous_metadata.steps,
                "cfg_scale": previous_metadata.cfg_scale,
                "sampler": previous_metadata.sampler,
                "width": previous_metadata.width,
                "height": previous_metadata.height,
            }
        # グローバル設定があればそれを使用
        elif global_settings:
            sd_params = global_settings.get("default_sd_params", {})
            defaults = {
                "steps": sd_params.get("steps", self.settings.default_steps),
                "cfg_scale": sd_params.get("cfg_scale", self.settings.default_cfg_scale),
                "sampler": sd_params.get("sampler", self.settings.default_sampler),
                "width": sd_params.get("width", self.settings.default_width),
                "height": sd_params.get("height", self.settings.default_height),
            }
        # デフォルト設定を使用
        else:
            defaults = {
                "steps": self.settings.default_steps,
                "cfg_scale": self.settings.default_cfg_scale,
                "sampler": self.settings.default_sampler,
                "width": self.settings.default_width,
                "height": self.settings.default_height,
            }

        # マージ（LLM の結果を優先）
        for key, default_value in defaults.items():
            if key not in result or result[key] is None:
                result[key] = default_value

        # グローバル設定から明示的に設定された値で上書き（ユーザー設定を優先）
        if global_settings:
            # sd_params の明示的な設定で上書き
            sd_params = global_settings.get("default_sd_params", {})
            # クラス定数のsd_paramsの各設定を適用（promptとnegative_prompt以外）
            for key in self._SD_PARAM_KEYS:
                if sd_params.get(key) is not None:
                    result[key] = sd_params[key]

        # デフォルトプロンプト suffix を追加
        if global_settings and global_settings.get("default_prompt_suffix"):
            suffix = global_settings["default_prompt_suffix"]
            if suffix not in result.get("prompt", ""):
                result["prompt"] = f"{result.get('prompt', '')}, {suffix}".strip(", ")

        # negative_prompt のデフォルト
        if not result.get("negative_prompt"):
            result["negative_prompt"] = (
                "worst quality, low quality, blurry, bad anatomy, bad hands, text, error, "
                "missing fingers, extra digit, fewer digits, cropped, jpeg artifacts, "
                "signature, watermark, username"
            )

        # seed のデフォルト
        # グローバル設定のseedを優先、なければランダム
        if global_settings and global_settings.get("seed") is not None:
            result["seed"] = global_settings["seed"]
        elif "seed" not in result or result["seed"] == -1:
            result["seed"] = random.randint(0, 2**32 - 1)

        return result
