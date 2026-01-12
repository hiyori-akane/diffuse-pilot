"""
Stable Diffusion WebUI API スタブサーバー

高性能なGPUサーバーを起動せずに、他の機能の動作確認を可能にするためのスタブサーバー。
実際の画像生成は行わず、ダミーレスポンスを返します。
受け取ったリクエストは指定されたDiscordチャンネルに通知されます。
"""

import asyncio
import base64
import io
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import discord
from fastapi import FastAPI, Request
from PIL import Image, ImageDraw

from src.config.logging import get_logger

logger = get_logger(__name__)

# Discord通知用のクライアント（オプション）
discord_client: discord.Client | None = None
discord_channel_id: int | None = None


async def startup():
    """アプリケーション起動時の処理"""
    logger.info("Starting SD WebUI Stub server")

    # Discord通知が有効な場合、クライアントをセットアップ
    # 環境変数から設定を読み込む（オプション）
    import os

    stub_discord_channel_id = os.getenv("STUB_DISCORD_CHANNEL_ID")
    discord_bot_token = os.getenv("DISCORD_BOT_TOKEN")

    if stub_discord_channel_id and discord_bot_token:
        try:
            channel_id = int(stub_discord_channel_id)
            await setup_discord_client(discord_bot_token, channel_id)
            logger.info(f"Discord notification enabled for channel {channel_id}")
        except ValueError:
            logger.error(f"Invalid STUB_DISCORD_CHANNEL_ID: {stub_discord_channel_id}")
    else:
        logger.info(
            "Discord notification disabled (STUB_DISCORD_CHANNEL_ID or DISCORD_BOT_TOKEN not set)"
        )


async def shutdown():
    """アプリケーション終了時の処理"""
    logger.info("Shutting down SD WebUI Stub server")

    # Discordクライアントを終了
    if discord_client:
        await discord_client.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    # 起動時の処理
    await startup()
    yield
    # 終了時の処理
    await shutdown()


app = FastAPI(title="SD WebUI Stub", version="1.0.0", lifespan=lifespan)


def create_dummy_image(width: int = 512, height: int = 512, text: str = "STUB") -> str:
    """ダミー画像を生成してbase64エンコードした文字列を返す

    Args:
        width: 画像の幅
        height: 画像の高さ
        text: 画像に描画するテキスト

    Returns:
        base64エンコードされた画像データ
    """
    # ピンク色のグラデーション背景を作成
    img = Image.new("RGB", (width, height), color=(255, 192, 203))
    draw = ImageDraw.Draw(img)

    # テキストを描画
    try:
        # デフォルトフォントを使用
        # PILのデフォルトフォントを使用（サイズ指定なし）
        text_bbox = draw.textbbox((0, 0), text)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        position = ((width - text_width) // 2, (height - text_height) // 2)
        draw.text(position, text, fill=(128, 0, 128))
    except Exception as e:
        logger.warning(f"Failed to draw text: {e}")

    # グリッド線を描画（SD生成風に見せるため）
    grid_color = (220, 160, 180)
    for i in range(0, width, width // 8):
        draw.line([(i, 0), (i, height)], fill=grid_color, width=1)
    for i in range(0, height, height // 8):
        draw.line([(0, i), (width, i)], fill=grid_color, width=1)

    # base64エンコード
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()
    return base64.b64encode(img_bytes).decode()


async def notify_discord(endpoint: str, request_data: dict[str, Any]):
    """Discordチャンネルにリクエスト情報を通知

    Args:
        endpoint: APIエンドポイント
        request_data: リクエストデータ
    """
    if not discord_client or not discord_channel_id:
        return

    try:
        channel = discord_client.get_channel(discord_channel_id)
        if not channel:
            logger.warning(f"Discord channel {discord_channel_id} not found")
            return

        # 通知メッセージを作成
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"**[SD Stub]** `{endpoint}` at {timestamp}\n```json\n"

        # リクエストデータを整形（長すぎる場合は省略）
        request_str = json.dumps(request_data, ensure_ascii=False, indent=2)
        if len(request_str) > 1800:  # Discordの文字数制限を考慮
            request_str = request_str[:1800] + "\n... (truncated)"

        message += request_str + "\n```"

        await channel.send(message)
        logger.info(f"Sent notification to Discord channel {discord_channel_id}")

    except Exception as e:
        logger.error(f"Failed to send Discord notification: {e}")


@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "message": "Stable Diffusion WebUI API Stub",
        "version": "1.0.0",
        "endpoints": [
            "/sdapi/v1/txt2img",
            "/sdapi/v1/sd-models",
            "/sdapi/v1/loras",
            "/sdapi/v1/samplers",
            "/sdapi/v1/schedulers",
            "/sdapi/v1/upscalers",
        ],
    }


@app.post("/sdapi/v1/txt2img")
async def txt2img(request: Request):
    """Text-to-Image API スタブ

    実際の画像生成は行わず、ダミー画像を返します。
    """
    request_data = await request.json()
    logger.info(f"Received txt2img request: {request_data.get('prompt', 'N/A')[:100]}")

    # Discord通知（バックグラウンドで実行）
    asyncio.create_task(notify_discord("POST /sdapi/v1/txt2img", request_data))

    # リクエストパラメータを取得
    width = request_data.get("width", 512)
    height = request_data.get("height", 512)
    batch_size = request_data.get("batch_size", 1)
    prompt = request_data.get("prompt", "")

    # ダミー画像を生成
    images = []
    for i in range(batch_size):
        text = f"STUB\n{prompt[:20]}\n{i+1}/{batch_size}"
        img_data = create_dummy_image(width, height, text)
        images.append(img_data)

    # SD WebUI API互換のレスポンスを返す
    response = {
        "images": images,
        "parameters": {
            "prompt": request_data.get("prompt", ""),
            "negative_prompt": request_data.get("negative_prompt", ""),
            "steps": request_data.get("steps", 20),
            "cfg_scale": request_data.get("cfg_scale", 7.0),
            "width": width,
            "height": height,
            "sampler_name": request_data.get("sampler_name", "Euler a"),
            "seed": request_data.get("seed", -1),
            "batch_size": batch_size,
        },
        "info": json.dumps(
            {
                "stub": True,
                "message": "This is a stub response",
                "timestamp": datetime.now().isoformat(),
            }
        ),
    }

    logger.info(
        f"Generated {len(images)} stub images " f"({width}x{height}, batch_size={batch_size})"
    )

    return response


@app.get("/sdapi/v1/sd-models")
async def get_models():
    """利用可能なモデル一覧を返す（スタブ）"""
    logger.info("Received get models request")

    # Discord通知（バックグラウンドで実行）
    asyncio.create_task(notify_discord("GET /sdapi/v1/sd-models", {}))

    # ダミーのモデルリストを返す
    models = [
        {
            "title": "sd_xl_base_1.0.safetensors",
            "model_name": "sd_xl_base_1.0",
            "hash": "stub_hash_001",
            "sha256": "stub_sha256_001",
            "filename": "/models/Stable-diffusion/sd_xl_base_1.0.safetensors",
            "config": None,
        },
        {
            "title": "v1-5-pruned-emaonly.safetensors",
            "model_name": "v1-5-pruned-emaonly",
            "hash": "stub_hash_002",
            "sha256": "stub_sha256_002",
            "filename": "/models/Stable-diffusion/v1-5-pruned-emaonly.safetensors",
            "config": None,
        },
        {
            "title": "dreamshaper_8.safetensors",
            "model_name": "dreamshaper_8",
            "hash": "stub_hash_003",
            "sha256": "stub_sha256_003",
            "filename": "/models/Stable-diffusion/dreamshaper_8.safetensors",
            "config": None,
        },
    ]

    logger.info(f"Returning {len(models)} stub models")
    return models


@app.get("/sdapi/v1/loras")
async def get_loras():
    """利用可能なLoRA一覧を返す（スタブ）"""
    logger.info("Received get loras request")

    # Discord通知（バックグラウンドで実行）
    asyncio.create_task(notify_discord("GET /sdapi/v1/loras", {}))

    # ダミーのLoRAリストを返す
    loras = [
        {
            "name": "add_detail",
            "alias": "add_detail",
            "path": "/models/Lora/add_detail.safetensors",
            "metadata": {},
        },
        {
            "name": "lighting_lora",
            "alias": "lighting",
            "path": "/models/Lora/lighting_lora.safetensors",
            "metadata": {},
        },
        {
            "name": "style_anime_v1",
            "alias": "anime_style",
            "path": "/models/Lora/style_anime_v1.safetensors",
            "metadata": {},
        },
    ]

    logger.info(f"Returning {len(loras)} stub loras")
    return loras


@app.get("/sdapi/v1/samplers")
async def get_samplers():
    """利用可能なサンプラー一覧を返す（スタブ）"""
    logger.info("Received get samplers request")

    # Discord通知（バックグラウンドで実行）
    asyncio.create_task(notify_discord("GET /sdapi/v1/samplers", {}))

    # ダミーのサンプラーリストを返す
    samplers = [
        {"name": "Euler", "aliases": ["euler"]},
        {"name": "Euler a", "aliases": ["euler_a"]},
        {"name": "LMS", "aliases": ["lms"]},
        {"name": "Heun", "aliases": ["heun"]},
        {"name": "DPM2", "aliases": ["dpm2"]},
        {"name": "DPM2 a", "aliases": ["dpm2_a"]},
        {"name": "DPM++ 2S a", "aliases": ["dpmpp_2s_a"]},
        {"name": "DPM++ 2M", "aliases": ["dpmpp_2m"]},
        {"name": "DPM++ SDE", "aliases": ["dpmpp_sde"]},
        {"name": "DPM fast", "aliases": ["dpm_fast"]},
        {"name": "DPM adaptive", "aliases": ["dpm_adaptive"]},
        {"name": "LMS Karras", "aliases": ["lms_karras"]},
        {"name": "DPM2 Karras", "aliases": ["dpm2_karras"]},
        {"name": "DPM2 a Karras", "aliases": ["dpm2_a_karras"]},
        {"name": "DPM++ 2S a Karras", "aliases": ["dpmpp_2s_a_karras"]},
        {"name": "DPM++ 2M Karras", "aliases": ["dpmpp_2m_karras"]},
        {"name": "DPM++ SDE Karras", "aliases": ["dpmpp_sde_karras"]},
        {"name": "DDIM", "aliases": ["ddim"]},
        {"name": "PLMS", "aliases": ["plms"]},
        {"name": "UniPC", "aliases": ["unipc"]},
    ]

    logger.info(f"Returning {len(samplers)} stub samplers")
    return samplers


@app.get("/sdapi/v1/schedulers")
async def get_schedulers():
    """利用可能なスケジューラ一覧を返す（スタブ）"""
    logger.info("Received get schedulers request")

    # Discord通知（バックグラウンドで実行）
    asyncio.create_task(notify_discord("GET /sdapi/v1/schedulers", {}))

    # ダミーのスケジューラリストを返す
    schedulers = [
        {"name": "Automatic", "label": "Automatic"},
        {"name": "Uniform", "label": "Uniform"},
        {"name": "Karras", "label": "Karras"},
        {"name": "Exponential", "label": "Exponential"},
        {"name": "Polyexponential", "label": "Polyexponential"},
        {"name": "SGM Uniform", "label": "SGM Uniform"},
    ]

    logger.info(f"Returning {len(schedulers)} stub schedulers")
    return schedulers


@app.get("/sdapi/v1/upscalers")
async def get_upscalers():
    """利用可能なアップスケーラー一覧を返す（スタブ）"""
    logger.info("Received get upscalers request")

    # Discord通知（バックグラウンドで実行）
    asyncio.create_task(notify_discord("GET /sdapi/v1/upscalers", {}))

    # ダミーのアップスケーラーリストを返す
    upscalers = [
        {"name": "None", "model_name": None, "model_path": None, "model_url": None, "scale": 1},
        {
            "name": "Lanczos",
            "model_name": None,
            "model_path": None,
            "model_url": None,
            "scale": 4,
        },
        {
            "name": "Nearest",
            "model_name": None,
            "model_path": None,
            "model_url": None,
            "scale": 4,
        },
        {
            "name": "ESRGAN_4x",
            "model_name": "ESRGAN_4x",
            "model_path": "https://github.com/cszn/KAIR/releases/download/v1.0/ESRGAN.pth",
            "model_url": None,
            "scale": 4,
        },
        {
            "name": "R-ESRGAN 4x+",
            "model_name": "RealESRGAN_x4plus",
            "model_path": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
            "model_url": None,
            "scale": 4,
        },
        {
            "name": "R-ESRGAN 4x+ Anime6B",
            "model_name": "RealESRGAN_x4plus_anime_6B",
            "model_path": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
            "model_url": None,
            "scale": 4,
        },
        {
            "name": "SwinIR 4x",
            "model_name": "SwinIR_4x",
            "model_path": "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-L_x4_GAN.pth",
            "model_url": None,
            "scale": 4,
        },
    ]

    logger.info(f"Returning {len(upscalers)} stub upscalers")
    return upscalers


async def setup_discord_client(token: str, channel_id: int):
    """Discord通知用クライアントをセットアップ

    Args:
        token: Discord Bot トークン
        channel_id: 通知先チャンネルID
    """
    global discord_client, discord_channel_id

    discord_channel_id = channel_id

    # Discordクライアントを作成
    intents = discord.Intents.default()
    discord_client = discord.Client(intents=intents)

    @discord_client.event
    async def on_ready():
        logger.info(f"Discord client ready: {discord_client.user}")

    # 非同期でDiscordに接続
    asyncio.create_task(discord_client.start(token))


def run_stub(host: str = "0.0.0.0", port: int = 7860):
    """スタブサーバーを起動

    Args:
        host: バインドするホスト
        port: バインドするポート
    """
    import uvicorn

    logger.info(f"Starting SD WebUI Stub on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_stub()
