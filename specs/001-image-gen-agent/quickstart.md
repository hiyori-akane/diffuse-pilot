# quickstart.md

このドキュメントでは、画像生成エージェントをローカル環境で立ち上げて、基本的な動作を確認する手順を説明します。

## 前提条件

以下のソフトウェアとサービスが必要です：

1. **Python 3.10 以上**（推奨: Python 3.11）
2. **Stable Diffusion（Automatic1111）**がローカルまたはアクセス可能なサーバーで稼働していること
   - デフォルトでは `http://localhost:7860` を想定
   - API が有効化されていること（`--api` オプションで起動）
3. **Ollama**（ローカル LLM サーバー）がインストールされ、稼働していること
   - モデル `huihui_ai/gpt-oss-abliterated:20b-v2-q4_K_M` がダウンロード済みであること
   - デフォルトでは `http://localhost:11434` を想定
4. **Discord Bot トークン**
   - [Discord Developer Portal](https://discord.com/developers/applications) でアプリケーションを作成
   - Bot トークンを取得
   - スラッシュコマンド権限とスレッド作成権限を付与
5. **ストレージ容量**：最低 50GB の空き容量（画像とメタデータの保存用）
6. **（オプション）Google Search API キー**（Web リサーチ機能を有効にする場合）

---

## セットアップ手順

### 1. リポジトリをクローン

```bash
git clone https://github.com/hiyori-akane/diffuse-pilot.git
cd diffuse-pilot
```

### 2. 仮想環境を作成

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate  # Windows
```

### 3. 依存パッケージをインストール

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**主要な依存パッケージ（参考）**:
- `fastapi`
- `discord.py`
- `sqlalchemy>=2.0`
- `alembic`
- `pydantic`
- `httpx`
- `ollama` (Ollama クライアント)
- `black` (コードフォーマッター)
- `ruff` (静的解析ツール)
- `pytest` (テストフレームワーク)

### 4. 環境変数を設定

プロジェクトルートに `.env` ファイルを作成し、以下の変数を設定します：

```env
# Discord Bot 設定
DISCORD_BOT_TOKEN=your_discord_bot_token_here

# Stable Diffusion API 設定
SD_API_URL=http://localhost:7860

# Ollama LLM 設定
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=huihui_ai/gpt-oss-abliterated:20b-v2-q4_K_M

# データベース設定
DATABASE_URL=sqlite:///./diffuse_pilot.db

# ストレージ設定
IMAGE_STORAGE_PATH=/Volumes/Develop/diffuse-pilot/storage/images

# （オプション）Web リサーチ設定
GOOGLE_SEARCH_API_KEY=your_google_api_key_here
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id_here

# ログレベル
LOG_LEVEL=INFO
```

**注意**: 本番環境では `.env` ファイルをコミットせず、環境変数を直接設定してください。

### 5. データベースをマイグレーション

Alembic を使用して、データベースのテーブルを初期化します：

```bash
alembic upgrade head
```

### 6. ストレージディレクトリを作成

画像を保存するディレクトリを作成します：

```bash
mkdir -p storage/images
```

### 7. Discord Bot をサーバーに招待

1. Discord Developer Portal でアプリケーションの「OAuth2 → URL Generator」にアクセス
2. **SCOPES**: `bot`, `applications.commands` を選択
3. **BOT PERMISSIONS**: 以下を選択
   - Send Messages
   - Create Public Threads
   - Send Messages in Threads
   - Attach Files
   - Use Slash Commands
4. 生成された URL をブラウザで開き、Bot を Discord サーバーに招待

---

## 起動手順

### 1. Automatic1111 を起動

別のターミナルで Stable Diffusion（Automatic1111）を起動します：

```bash
cd /path/to/stable-diffusion-webui
./webui.sh --api
```

### 2. Ollama を起動

Ollama がバックグラウンドで稼働していることを確認します：

```bash
ollama serve
```

別のターミナルで、使用するモデルがダウンロード済みか確認：

```bash
ollama list
```

もしモデルがなければ、ダウンロード：

```bash
ollama pull huihui_ai/gpt-oss-abliterated:20b-v2-q4_K_M
```

### 3. FastAPI サーバーを起動

API サーバーを起動します：

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Discord Bot を起動

別のターミナルで Discord Bot を起動します：

```bash
python src/bot.py
```

**確認**: Bot がオンラインになったことを Discord で確認してください。

---

## 基本的な動作確認

### 1. 画像生成コマンドを試す

Discord のチャンネルで以下のスラッシュコマンドを実行します：

```
/generate 和風サイバーパンクの女性、夕景、彩度高め
```

- Bot がスレッドを作成し、「画像生成中...」と応答します
- 数分後、生成された画像がスレッドに投稿されます
- 生成に使用されたプロンプト、モデル、設定が添えられます

### 2. 追加指示で画像を修正

スレッド内で以下のように返信します：

```
もっと明るく、笑顔にして
```

- Bot が前回の設定を復元し、追加指示を反映した新しい画像を生成します

### 3. グローバル設定を変更

```
/settings set model sdxl
```

- Bot が「デフォルトモデルを SDXL に設定しました」と応答します
- 次回の画像生成で SDXL モデルが自動的に使用されます

### 4. LoRA リストを確認

```
/lora list
```

- Bot が利用可能な LoRA の一覧を表示します

---

## API エンドポイントの確認

FastAPI サーバーが起動している状態で、ブラウザで以下にアクセスします：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

ここで API の仕様を確認し、手動でリクエストを送信してテストできます。

---

## トラブルシューティング

### Bot が応答しない

1. Discord Bot トークンが正しく設定されているか確認
2. Bot がサーバーに招待されているか確認
3. Bot に適切な権限が付与されているか確認
4. `src/bot.py` のログを確認してエラーメッセージをチェック

### 画像生成がタイムアウトする

1. Stable Diffusion（Automatic1111）が稼働しているか確認
2. `SD_API_URL` が正しく設定されているか確認
3. Automatic1111 のログでエラーを確認
4. タイムアウト時間（デフォルト 600 秒）を延長する必要がある場合は、設定ファイルを編集

### Ollama が応答しない

1. Ollama サーバーが稼働しているか確認（`ollama serve`）
2. モデルがダウンロード済みか確認（`ollama list`）
3. `OLLAMA_API_URL` と `OLLAMA_MODEL` が正しく設定されているか確認

### データベースエラー

1. Alembic マイグレーションが最新か確認（`alembic current`）
2. データベースファイル（`diffuse_pilot.db`）が存在し、アクセス可能か確認
3. 外部キー制約が有効化されているか確認（SQLite の場合、`PRAGMA foreign_keys = ON;` が設定されているか）

---

## 次のステップ

1. **テストを実行**: `pytest tests/` でユニットテストを実行し、分岐網羅（C1）カバレッジを確認
2. **コード品質チェック**: `ruff check .` と `black --check .` で静的解析とフォーマットを確認
3. **本番デプロイ**: Docker イメージをビルドして、本番環境にデプロイ（詳細は `docs/deployment.md` を参照）
4. **モニタリング設定**: Prometheus + Grafana でメトリクスを監視（詳細は `docs/monitoring.md` を参照）

---

## 参考リンク

- [Discord Developer Portal](https://discord.com/developers/applications)
- [Automatic1111 Web UI](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
- [Ollama](https://ollama.ai/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)

---

## サポート

問題が発生した場合は、GitHub Issues で報告してください：  
https://github.com/hiyori-akane/diffuse-pilot/issues
