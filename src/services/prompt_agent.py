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
    sampler: str | None = Field(default=None, description="サンプラー名（Euler a, DPM++ 2M Karras 等）")
    scheduler: str | None = Field(default=None, description="スケジューラ名（Automatic, Karras 等、未指定可）")
    width: int = Field(description="画像幅（整数、512, 768, 1024等）", ge=64, le=2048)
    height: int = Field(description="画像高さ（整数、512, 768, 1024等）", ge=64, le=2048)


class PromptAgent:
    """プロンプト生成エージェント"""

    # SD パラメータのキー名リスト（promptとnegative_prompt以外）
    _SD_PARAM_KEYS = ["steps", "cfg_scale", "sampler", "scheduler", "width", "height"]

    # Webリサーチスキップキーワード
    WEB_RESEARCH_SKIP_KEYWORDS = ["リサーチなし", "リサーチしない", "調べないで", "すぐに生成"]

    def __init__(self):
        self.settings = get_settings()
        self.llm_client = OllamaClient()
        self._web_research_service = None  # Lazy initialization to avoid circular import

    async def close(self):
        """クライアントを閉じる"""
        await self.llm_client.close()
        if self._web_research_service:
            await self._web_research_service.close()

    async def generate_prompt(
        self,
        user_instruction: str,
        previous_metadata: GenerationMetadata | None = None,
        global_settings: dict[str, Any] | None = None,
        web_research: bool = False,
    ) -> dict[str, Any]:
        """ユーザー指示からプロンプトとパラメータを生成

        Args:
            user_instruction: ユーザーの自然言語指示
            previous_metadata: 前回の生成メタデータ（追加指示の場合）
            global_settings: グローバル設定
            web_research: Webリサーチを実施するか

        Returns:
            生成されたプロンプトとパラメータの辞書

        Raises:
            LLMAPIError: LLM API エラー
        """
        try:
            logger.info(
                f"Generating prompt from user instruction: {user_instruction[:100]}...",
                extra={"has_previous": previous_metadata is not None, "web_research": web_research},
            )

            # Webリサーチを実施（要求された場合のみ）
            research_result = None
            if web_research and not previous_metadata:  # 新規生成時のみリサーチ
                research_result = await self._perform_web_research(user_instruction)

            # システムプロンプト構築
            system_prompt = self._build_system_prompt()

            # ユーザープロンプト構築
            user_prompt = self._build_user_prompt(
                user_instruction, previous_metadata, global_settings, research_result
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
            result = self._apply_defaults(
                result, previous_metadata, global_settings, research_result
            )

            # Webリサーチ結果を含める
            if research_result:
                result["web_research"] = research_result

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
  "sampler": "サンプラー名（DPM++ 2M Karras 等）",
  "scheduler": "スケジューラ名（Beta, DDIM, Karras, Exponential 等）",
  "width": 画像幅（整数、512, 768, 1024等）,
  "height": 画像高さ（整数、512, 768, 1024等）
}

プロンプトは具体的で詳細に、品質向上のキーワード（masterpiece, best quality, highly detailed等）を含めてください。
ネガティブプロンプトには一般的な不要要素（worst quality, low quality, blurry等）を含めてください。
scheduler は未指定でも構いません（その場合はサーバー自動選択）。
"""

    def _build_user_prompt(
        self,
        user_instruction: str,
        previous_metadata: GenerationMetadata | None = None,
        global_settings: dict[str, Any] | None = None,
        research_result: dict[str, Any] | None = None,
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

            # Webリサーチ結果を追加
            if research_result:
                prompt += "Webリサーチ結果:\n"
                if research_result.get("summary"):
                    prompt += f"要約: {research_result['summary']}\n\n"
                if research_result.get("prompt_techniques"):
                    techniques = ", ".join(research_result["prompt_techniques"])
                    prompt += f"推奨プロンプトテクニック: {techniques}\n\n"
                if research_result.get("recommended_settings"):
                    settings = research_result["recommended_settings"]
                    prompt += f"推奨設定: {settings}\n\n"

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
        research_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """デフォルト値を適用

                優先順位:
                    1. 前回メタデータ（追加指示時）
                    2. グローバル設定（ユーザー/サーバー）
                    3. Webリサーチ推奨（新規時のみ、LLM未指定項目の補完）
                    4. LLM生成値
                    5. アプリケーションデフォルト（settings）

                sampler は SDGenerationParams 側で既定値を持たないためここで補完する。
                scheduler は現時点では LLM/設定経路に存在しないため扱わない（明示指定時のみ後段で使用）。
        """
        # ベースデフォルト（アプリ設定）
        defaults = {
            "steps": self.settings.default_steps,
            "cfg_scale": self.settings.default_cfg_scale,
            "sampler": self.settings.default_sampler,
            "scheduler": self.settings.default_scheduler,
            "width": self.settings.default_width,
            "height": self.settings.default_height,
        }

        # グローバル設定で上書き
        if global_settings:
            sd_params = global_settings.get("default_sd_params", {})
            for key in ["steps", "cfg_scale", "sampler", "scheduler", "width", "height"]:
                if sd_params.get(key) is not None:
                    defaults[key] = sd_params[key]

        # 前回メタデータ（追加指示時）は最優先
        if previous_metadata:
            defaults.update(
                {
                    "prompt": previous_metadata.prompt,
                    "negative_prompt": previous_metadata.negative_prompt or "",
                    "steps": previous_metadata.steps,
                    "cfg_scale": previous_metadata.cfg_scale,
                    "sampler": previous_metadata.sampler,
                    "scheduler": previous_metadata.scheduler,
                    "width": previous_metadata.width,
                    "height": previous_metadata.height,
                }
            )

        # まず defaults で埋める（result に値が無い場合）
        for key, default_value in defaults.items():
            if result.get(key) is None:
                result[key] = default_value

        # Webリサーチ推奨（新規生成時のみ）: LLM が埋めていない項目の補完
        if research_result and not previous_metadata:
            recommended = research_result.get("recommended_settings", {})
            for key in self._SD_PARAM_KEYS:
                if result.get(key) is None and recommended.get(key) is not None:
                    result[key] = recommended[key]

        # グローバル設定（明示）で再度上書き（最終優先）
        if global_settings:
            sd_params = global_settings.get("default_sd_params", {})
            for key in self._SD_PARAM_KEYS:
                if sd_params.get(key) is not None:
                    result[key] = sd_params[key]

        # 追加指示モードの場合は前回メタデータのパラメータを LLM 値より優先して最終的に上書き
        if previous_metadata:
            for key in self._SD_PARAM_KEYS:
                prev_value = getattr(previous_metadata, key, None)
                if prev_value is not None:
                    result[key] = prev_value
            # prompt / negative_prompt も差分指定がない限り前回を基準
            if previous_metadata.prompt:
                result["prompt"] = previous_metadata.prompt
            if previous_metadata.negative_prompt:
                result["negative_prompt"] = previous_metadata.negative_prompt

        # デフォルトプロンプト suffix を追加（追加指示時も suffix が未含有なら付与）
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

    async def _perform_web_research(self, user_instruction: str) -> dict[str, Any] | None:
        """Webリサーチを実施

        Args:
            user_instruction: ユーザーの指示

        Returns:
            リサーチ結果、実施しない場合はNone
        """
        # Lazy initialization of web research service (singleton per PromptAgent instance)
        if self._web_research_service is None:
            from src.services.web_research import WebResearchService

            self._web_research_service = WebResearchService()

        try:
            # "リサーチなしで生成" などのキーワードをチェック
            if any(keyword in user_instruction for keyword in self.WEB_RESEARCH_SKIP_KEYWORDS):
                logger.info("Skipping web research due to user instruction")
                return None

            # Webリサーチを実施
            research_result = await self._web_research_service.research_best_practices(
                user_instruction
            )

            return research_result

        except Exception as e:
            # Webリサーチに失敗してもエラーにせず、警告だけ出す
            logger.warning(f"Web research failed, continuing without it: {str(e)}")
            return None
