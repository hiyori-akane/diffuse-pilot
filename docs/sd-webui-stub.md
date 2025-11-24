# Stable Diffusion WebUI APIスタブ

## 概要

`sd_webui_stub.py`は、高性能なGPUサーバーを起動せずに、Diffuse Pilotの他の機能を開発・テストするためのスタブサーバーです。実際の画像生成は行わず、ダミー画像とレスポンスを返します。

## 機能

- ✅ **Automatic1111 WebUI API互換**: 実際のSD WebUI APIと同じエンドポイントとレスポンス形式
- 🎨 **ダミー画像生成**: プロンプトとパラメータに基づいたダミーのPNG画像を返却
- 📢 **Discord通知（オプション）**: APIリクエストを指定のDiscordチャンネルに通知
- 🚀 **軽量・高速**: GPU不要で即座にレスポンスを返却

## サポートするエンドポイント

スタブは以下のStable Diffusion WebUI APIエンドポイントをサポートしています：

### 1. POST `/sdapi/v1/txt2img`
テキストから画像を生成（ダミー）

**リクエスト例:**
```json
{
  "prompt": "beautiful landscape",
  "negative_prompt": "bad quality",
  "width": 512,
  "height": 512,
  "steps": 20,
  "cfg_scale": 7.0,
  "batch_size": 1,
  "sampler_name": "Euler a",
  "seed": -1
}
```

**レスポンス:**
```json
{
  "images": ["<base64-encoded-png>", ...],
  "parameters": { ... },
  "info": "{\"stub\": true, ...}"
}
```

### 2. GET `/sdapi/v1/sd-models`
利用可能なモデル一覧を取得（ダミー）

**レスポンス例:**
```json
[
  {
    "title": "sd_xl_base_1.0.safetensors",
    "model_name": "sd_xl_base_1.0",
    "hash": "stub_hash_001",
    "filename": "/models/Stable-diffusion/sd_xl_base_1.0.safetensors"
  },
  ...
]
```

### 3. GET `/sdapi/v1/loras`
利用可能なLoRA一覧を取得（ダミー）

**レスポンス例:**
```json
[
  {
    "name": "add_detail",
    "alias": "add_detail",
    "path": "/models/Lora/add_detail.safetensors",
    "metadata": {}
  },
  ...
]
```

## セットアップ

### 1. 基本的な起動

スタブサーバーをデフォルト設定（ポート7860）で起動：

```bash
python -m src.sd_webui_stub
```

### 2. Diffuse Pilotの設定変更

`.env`ファイルで、Stable Diffusion APIのURLをスタブサーバーに向けます：

```bash
# スタブサーバーを使用する場合
SD_API_URL=http://localhost:7860

# 実際のSD WebUIを使用する場合（デフォルト）
# SD_API_URL=http://your-gpu-server:7860
```

### 3. Discord通知の有効化（オプション）

スタブサーバーが受け取ったリクエストをDiscordチャンネルに通知したい場合：

1. `.env`に通知先チャンネルIDを追加：

```bash
# Discord通知を有効化
STUB_DISCORD_CHANNEL_ID=1234567890123456789
```

2. 通知先チャンネルIDの確認方法：
   - Discordで開発者モードを有効化
   - チャンネルを右クリック→「IDをコピー」

3. スタブサーバーを起動すると、APIリクエストがそのチャンネルに送信されます

**通知の例:**
```
[SD Stub] POST /sdapi/v1/txt2img at 2024-01-15 10:30:00
{
  "prompt": "anime girl, high quality",
  "width": 512,
  "height": 768,
  ...
}
```

## 使用例

### ケース1: ローカル開発

GPUサーバーなしでDiffuse Pilotの開発を行う：

```bash
# ターミナル1: スタブサーバー起動
python -m src.sd_webui_stub

# ターミナル2: Diffuse Pilot起動
python -m src.bot
```

Discordで`/generate`コマンドを実行すると、スタブサーバーからダミー画像が返されます。

### ケース2: CI/CDパイプライン

テスト環境でスタブサーバーを使用：

```yaml
# GitHub Actions example
- name: Start stub server
  run: python -m src.sd_webui_stub &
  
- name: Run integration tests
  run: pytest tests/integration/
```

### ケース3: Discord通知でデバッグ

リクエスト内容を確認しながら開発：

```bash
# Discord通知を有効化してスタブ起動
export STUB_DISCORD_CHANNEL_ID=1234567890123456789
python -m src.sd_webui_stub
```

スタブが受け取ったすべてのリクエストが指定のDiscordチャンネルに投稿されます。

## ダミー画像について

スタブサーバーが生成するダミー画像の特徴：

- **形式**: PNG (base64エンコード)
- **サイズ**: リクエストで指定されたwidth/heightに準拠
- **内容**: 
  - ピンク色のグラデーション背景
  - "STUB"テキスト
  - プロンプトの一部（最大20文字）
  - バッチ番号（複数枚生成時）
  - グリッド線（SD生成風）

## カスタマイズ

### ポート番号の変更

```python
# src/sd_webui_stub.py の最後を編集
if __name__ == "__main__":
    run_stub(host="0.0.0.0", port=8080)  # ポート変更
```

または環境変数で指定：

```bash
# コマンドライン引数で指定
python -c "from src.sd_webui_stub import run_stub; run_stub(port=8080)"
```

### ダミーモデル/LoRAの追加

`src/sd_webui_stub.py`の`get_models()`や`get_loras()`関数を編集して、返却するモデル/LoRAリストをカスタマイズできます。

## トラブルシューティング

### ポートが使用中

```
Error: [Errno 98] Address already in use
```

**解決方法**: 
- 既存のSD WebUIまたはスタブサーバーを停止
- 別のポート番号を使用

### Discord通知が届かない

**確認事項**:
1. `STUB_DISCORD_CHANNEL_ID`が正しく設定されているか
2. Botがそのチャンネルにアクセス権限を持っているか
3. チャンネルIDが数値型で正しいか（引用符不要）

### ダミー画像が生成されない

スタブサーバーのログを確認：

```bash
python -m src.sd_webui_stub
# ログで "Generated X stub images" を確認
```

## 本番環境での注意

⚠️ **スタブサーバーは開発・テスト専用です**

本番環境では必ず実際のStable Diffusion WebUI APIを使用してください。スタブサーバーは：

- 実際の画像生成を行いません
- ダミーデータのみを返します
- 本番トラフィックに対応していません

## 参考

- [Automatic1111 WebUI API Documentation](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Diffuse Pilot README](../README.md)
