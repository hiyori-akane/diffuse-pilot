# Diffuse Pilot

Discord上の自然言語指示から画像生成を自動化するエージェントシステム

## 概要

Diffuse Pilotは、DiscordのスラッシュコマンドでユーザーからReceived natural language instructions and automate the Prompts generation, parameter selection, Stable Diffusion API call, and result posting process.

## 主な機能

- ✨ **Discord統合**: スラッシュコマンド(`/generate`)で簡単に画像生成
- 🤖 **自動プロンプト生成**: LLMを使用してユーザーの自然言語指示を最適なプロンプトに変換
- 🎨 **Stable Diffusion連携**: Automatic1111 APIを使用した高品質な画像生成
- 📝 **スレッド管理**: 生成結果を専用スレッドで管理
- ⚡ **キューイングシステム**: 複数のリクエストを順次処理
- 🧪 **スタブサーバー**: GPU不要で開発・テスト可能なAPIスタブ

## 必要要件

- Python 3.10+
- Discord Bot Token（必要な権限: Applications Commands, Send Messages, Send Messages in Threads, Create Public Threads, Read Message History）
- Stable Diffusion (Automatic1111) API（または開発用にスタブサーバー）
- Ollama (LLM サーバー)

## セットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/hiyori-akane/diffuse-pilot.git
cd diffuse-pilot
```

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 開発用
```

### 3. 環境変数の設定

`.env.example`を`.env`にコピーして編集：

```bash
cp .env.example .env
```

必須の環境変数：
- `DISCORD_BOT_TOKEN`: Discord Bot トークン（Privileged Intents不要）
- `SD_API_URL`: Stable Diffusion API URL (default: http://localhost:7860)
- `OLLAMA_API_URL`: Ollama API URL (default: http://localhost:11434)
- `OLLAMA_MODEL`: 使用するLLMモデル (default: huihui_ai/gpt-oss-abliterated:20b-v2-q4_K_M)

オプションの環境変数：
- `GEMINI_API_KEY`: Gemini API キー（`/generate_gemini` コマンドを使用する場合に必要）

### 4. データベースのマイグレーション

```bash
alembic upgrade head
```

### 5. Botの起動

```bash
python -m src.bot
```

または、FastAPI サーバーも一緒に起動する場合:

```bash
# ターミナル1: Bot
python -m src.bot

# ターミナル2: FastAPI
python -m src.main
```

## 使い方

### Discord での画像生成

#### 通常モード (`/generate`)

1. Discordサーバーで `/generate` コマンドを実行
2. `instruction` パラメータに生成したい画像の説明を入力（日本語OK）
3. Botがスレッドを作成し、画像生成を開始
4. 完了すると生成された画像がスレッドに投稿されます

例：
```
/generate instruction:和風サイバーパンクの女性、夕景、彩度高め
```

#### Gemini AIモード (`/generate_gemini`)

1. Discordサーバーで `/generate_gemini` コマンドを実行
2. `instruction` パラメータに生成したい画像の説明を入力（日本語OK）
3. Gemini APIが直接画像を生成（Stable Diffusion不使用）
4. 完了すると生成された画像がスレッドに投稿されます

例：
```
/generate_gemini instruction:美しい夕焼けの山の風景
```

**Geminiモードの特徴:**
- **Gemini 3 Pro Image APIで直接画像生成**
- Stable Diffusionを使用せず、Gemini APIのみで完結
- 最高品質の画像生成設定
- Thought signaturesを保存し、会話的な画像編集に対応（今後実装予定）
- 日本語の指示から自然に高品質な画像を生成

**注意:** Geminiモードを使用するには、環境変数に `GEMINI_API_KEY` を設定する必要があります。

### ヘルスチェック

FastAPI サーバーが起動している場合：

```bash
curl http://localhost:8000/health
```

## プロジェクト構成

```
diffuse-pilot/
├── src/
│   ├── api/              # FastAPI エンドポイント
│   ├── config/           # 設定管理
│   ├── database/         # データベース接続
│   ├── models/           # SQLAlchemy モデル
│   ├── services/         # ビジネスロジック
│   ├── bot.py            # Bot 起動スクリプト
│   └── main.py           # FastAPI アプリケーション
├── tests/                # テスト
├── alembic/              # データベースマイグレーション
├── data/                 # データ保存ディレクトリ
│   ├── database.db       # SQLite DB
│   └── images/           # 生成画像
├── pyproject.toml        # プロジェクト設定
├── requirements.txt      # 依存関係
└── README.md             # このファイル
```

## 開発

### コードフォーマット

```bash
black src/ tests/
```

### リント

```bash
ruff check src/ tests/
```

### テスト

```bash
pytest
```

### カバレッジ

```bash
pytest --cov=src --cov-report=html
```

## SD WebUI スタブサーバー

GPU不要で開発・テストを行うための軽量スタブサーバーを提供しています。

### スタブサーバーの起動

```bash
# デフォルト設定でスタブサーバー起動（ポート7860）
python -m src.sd_webui_stub

# .envでSD_API_URLをスタブサーバーに向ける
SD_API_URL=http://localhost:7860
```

詳細は [SD WebUI スタブドキュメント](docs/sd-webui-stub.md) を参照してください。

## アーキテクチャ

### 主要コンポーネント

1. **Discord Bot** (`src/services/discord_bot.py`)
   - スラッシュコマンドの処理
   - スレッド管理
   - 結果の投稿

2. **Queue Manager** (`src/services/queue_manager.py`)
   - タスクキューの管理
   - 画像生成ワークフローの調整
   - 1リクエストずつ順次処理

3. **Prompt Agent** (`src/services/prompt_agent.py`)
   - LLMを使用したプロンプト生成
   - パラメータの最適化

4. **SD Client** (`src/services/sd_client.py`)
   - Stable Diffusion API との連携
   - 画像生成リクエストの送信

5. **Ollama Client** (`src/services/ollama_client.py`)
   - LLM API との連携
   - プロンプト生成のための推論

### データモデル

- `GenerationRequest`: 画像生成リクエスト
- `GenerationMetadata`: 生成に使用したパラメータ
- `GeneratedImage`: 生成された画像
- `GlobalSettings`: グローバル設定
- `ThreadContext`: スレッドコンテキスト
- `LoRAMetadata`: LoRA 情報
- `QueuedTask`: キューイングされたタスク

## ライセンス

MIT

## 貢献

プルリクエストを歓迎します！

1. このリポジトリをフォーク
2. フィーチャーブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add some amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

## サポート

問題が発生した場合は、[Issues](https://github.com/hiyori-akane/diffuse-pilot/issues)で報告してください。
