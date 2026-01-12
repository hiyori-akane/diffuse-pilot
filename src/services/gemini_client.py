"""
Gemini API クライアント

Google Gemini APIを使用して画像を直接生成
"""

import asyncio
import base64
import json
from io import BytesIO
from typing import Any

from google import genai
from google.genai import types
from google.genai.types import HarmCategory, HarmBlockThreshold
from PIL import Image

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.services.error_handler import ApplicationError, ErrorCode

logger = get_logger(__name__)


class GeminiAPIError(ApplicationError):
    """Gemini API エラー"""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(
            code=ErrorCode.LLM_API_ERROR,
            message=message,
            original_error=original_error,
        )


class GeminiClient:
    """Gemini API クライアント（画像生成用）"""

    def __init__(self):
        self.settings = get_settings()
        if not self.settings.gemini_api_key:
            raise GeminiAPIError("Gemini API キーが設定されていません")

        # Gemini クライアントの初期化
        self.client = genai.Client(api_key=self.settings.gemini_api_key)
        # Gemini 3 画像生成モデルを使用
        self.model = "gemini-3-pro-image-preview"

    async def generate_images(
        self,
        instruction: str,
        reference_image: Image.Image | None = None,
        previous_thought_signatures: list[str] | None = None,
    ) -> dict[str, Any]:
        """Gemini APIで画像を直接生成

        Args:
            instruction: 画像生成の指示（日本語OK）
            reference_image: 編集用の参照画像（オプション）
            previous_thought_signatures: 会話履歴のthought signatures（編集時に必要）

        Returns:
            生成結果を含む辞書
            {
                "images": [PIL.Image, ...],
                "thought_signatures": ["sig1", "sig2", ...],
                "description": "生成した画像の説明"
            }
        """
        try:
            # コンテンツパーツを構築
            parts = []

            # 参照画像がある場合は追加（編集モード）
            if reference_image:
                # PIL ImageをBase64エンコード
                buffer = BytesIO()
                reference_image.save(buffer, format="PNG")
                # Gemini SDKのBlob.dataは生バイトを受け取る想定。Base64文字列ではなくそのまま渡す。
                image_bytes = buffer.getvalue()

                parts.append(
                    types.Part(
                        inline_data=types.Blob(
                            mime_type="image/png",
                            data=image_bytes,
                        )
                    )
                )

            # テキスト指示を追加
            parts.append(types.Part(text=instruction))

            # コンテンツを構築
            contents = [types.Content(parts=parts)]

            # 会話履歴がある場合（編集モード）、thought signaturesを追加
            if previous_thought_signatures:
                # 前回のレスポンスを再構築（thought signatures付き）
                previous_parts = []
                for i, sig in enumerate(previous_thought_signatures):
                    # 最初のパートにsignatureを追加
                    if i == 0:
                        previous_parts.append(
                            types.Part(
                                text="Previous generation",
                                thought_signature=sig,
                            )
                        )
                    else:
                        # 画像パートにもsignatureを追加
                        previous_parts.append(
                            types.Part(
                                inline_data=types.Blob(
                                    mime_type="image/png",
                                    data="",  # ダミーデータ
                                ),
                                thought_signature=sig,
                            )
                        )

                # モデルの前回レスポンスを挿入
                contents.insert(
                    0,
                    types.Content(
                        role="model",
                        parts=previous_parts,
                    ),
                )

            # Gemini SDK は同期HTTP通信のためイベントループブロックを回避
            # asyncio.to_thread() で別スレッド実行し Discord heartbeat 遅延を防ぐ
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=1.0,
                    # 安全性設定をすべてOFFに設定
                    safety_settings=[
                        types.SafetySetting(
                            category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=HarmBlockThreshold.OFF,
                        ),
                        types.SafetySetting(
                            category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            threshold=HarmBlockThreshold.OFF,
                        ),
                        types.SafetySetting(
                            category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            threshold=HarmBlockThreshold.OFF,
                        ),
                        types.SafetySetting(
                            category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            threshold=HarmBlockThreshold.OFF,
                        ),
                        types.SafetySetting(
                            category=HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
                            threshold=HarmBlockThreshold.OFF,
                        ),
                    ],
                ),
            )

            # レスポンスから画像とthought signaturesを抽出
            images = []
            thought_signatures = []
            description = ""

            for part in response.parts:
                if hasattr(part, "thought_signature") and part.thought_signature:
                    sig = part.thought_signature
                    # 署名は文字列想定。誤ってバイト列や巨大データが入るケースをフィルタ。
                    if isinstance(sig, bytes):
                        try:
                            sig = sig.decode("utf-8", errors="ignore")
                        except Exception:
                            # デコード不能ならBase64化
                            sig = base64.b64encode(sig).decode("ascii")
                    # 1KB超の署名は異常とみなしスキップ（画像バイトを誤取得した可能性）
                    if len(sig) > 1024:
                        logger.warning(
                            "Skipping oversized thought_signature",
                            extra={"length": len(sig)},
                        )
                    else:
                        thought_signatures.append(sig)

                if hasattr(part, "text") and part.text:
                    description = part.text

                if hasattr(part, "inline_data") and part.inline_data:
                    # 常に PIL.Image 型で返すよう統一（queue_manager での .save() 互換性のため）
                    try:
                        # inline_data.data は生バイト列
                        raw_bytes = part.inline_data.data
                        image = Image.open(BytesIO(raw_bytes))
                        images.append(image)
                    except Exception as pil_err:
                        logger.error(
                            "画像パートの変換に失敗しました",
                            extra={
                                "error": str(pil_err),
                                "part_has_inline_data": True,
                                "data_type": type(part.inline_data.data).__name__,
                                "data_length": len(part.inline_data.data)
                                if hasattr(part.inline_data, "data") and part.inline_data.data
                                else 0,
                            },
                        )
                        raise

            logger.info(
                f"Generated {len(images)} images via Gemini",
                extra={
                    "instruction_length": len(instruction),
                    "has_reference": reference_image is not None,
                    "thought_signatures_count": len(thought_signatures),
                },
            )

            return {
                "images": images,
                "thought_signatures": thought_signatures,
                "description": description,
            }

        except Exception as e:
            logger.exception(f"Gemini image generation error: {str(e)}")
            raise GeminiAPIError(
                f"Gemini APIで画像生成エラーが発生しました: {str(e)}",
                original_error=e,
            ) from e
