"""
SD WebUI Stubのテスト
"""

import base64
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from src.sd_webui_stub import app

# TestClientはasync/awaitをサポートしていないため、同期的にテストする
client = TestClient(app)


def test_root_endpoint():
    """ルートエンドポイントのテスト"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "endpoints" in data
    assert "/sdapi/v1/txt2img" in data["endpoints"]


def test_txt2img_endpoint():
    """txt2imgエンドポイントのテスト"""
    # リクエストデータ
    request_data = {
        "prompt": "test prompt",
        "negative_prompt": "bad quality",
        "steps": 20,
        "cfg_scale": 7.0,
        "width": 512,
        "height": 512,
        "batch_size": 2,
        "sampler_name": "Euler a",
        "seed": -1,
    }

    response = client.post("/sdapi/v1/txt2img", json=request_data)
    assert response.status_code == 200

    data = response.json()

    # レスポンスの構造を確認
    assert "images" in data
    assert "parameters" in data
    assert "info" in data

    # 画像が指定された枚数生成されているか
    assert len(data["images"]) == request_data["batch_size"]

    # パラメータが正しく返されているか
    assert data["parameters"]["prompt"] == request_data["prompt"]
    assert data["parameters"]["negative_prompt"] == request_data["negative_prompt"]
    assert data["parameters"]["steps"] == request_data["steps"]
    assert data["parameters"]["cfg_scale"] == request_data["cfg_scale"]
    assert data["parameters"]["width"] == request_data["width"]
    assert data["parameters"]["height"] == request_data["height"]

    # 画像がbase64エンコードされたPNG形式か確認
    for img_data in data["images"]:
        # base64デコード
        img_bytes = base64.b64decode(img_data)
        # PIL Imageとして開けるか確認
        img = Image.open(BytesIO(img_bytes))
        assert img.format == "PNG"
        assert img.size == (request_data["width"], request_data["height"])


def test_txt2img_default_parameters():
    """txt2imgエンドポイントのデフォルトパラメータテスト"""
    # 最小限のリクエストデータ
    request_data = {
        "prompt": "minimal test",
    }

    response = client.post("/sdapi/v1/txt2img", json=request_data)
    assert response.status_code == 200

    data = response.json()

    # デフォルト値で画像が生成されているか
    assert len(data["images"]) == 1  # デフォルトbatch_size
    assert data["parameters"]["width"] == 512  # デフォルトwidth
    assert data["parameters"]["height"] == 512  # デフォルトheight


def test_get_models_endpoint():
    """sd-modelsエンドポイントのテスト"""
    response = client.get("/sdapi/v1/sd-models")
    assert response.status_code == 200

    models = response.json()

    # モデルリストが返されているか
    assert isinstance(models, list)
    assert len(models) > 0

    # 各モデルが必要なフィールドを持っているか
    for model in models:
        assert "title" in model
        assert "model_name" in model
        assert "hash" in model
        assert "filename" in model


def test_get_loras_endpoint():
    """lorasエンドポイントのテスト"""
    response = client.get("/sdapi/v1/loras")
    assert response.status_code == 200

    loras = response.json()

    # LoRAリストが返されているか
    assert isinstance(loras, list)
    assert len(loras) > 0

    # 各LoRAが必要なフィールドを持っているか
    for lora in loras:
        assert "name" in lora
        assert "alias" in lora
        assert "path" in lora


def test_txt2img_various_sizes():
    """txt2imgエンドポイントの様々なサイズテスト"""
    sizes = [
        (256, 256),
        (512, 512),
        (768, 768),
        (512, 768),
        (768, 512),
    ]

    for width, height in sizes:
        request_data = {
            "prompt": f"test {width}x{height}",
            "width": width,
            "height": height,
        }

        response = client.post("/sdapi/v1/txt2img", json=request_data)
        assert response.status_code == 200

        data = response.json()
        img_bytes = base64.b64decode(data["images"][0])
        img = Image.open(BytesIO(img_bytes))

        # 正しいサイズの画像が生成されているか
        assert img.size == (width, height)
