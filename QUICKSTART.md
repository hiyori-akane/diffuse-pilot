# Diffuse Pilot クイックスタートガイド

## 前提条件

以下のサービスが起動している必要があります：

1. **Stable Diffusion (Automatic1111)**
   - URL: http://localhost:7860 (デフォルト)
   - API が有効であること

2. **Ollama LLM サーバー**
   - URL: http://localhost:11434 (デフォルト)
   - モデル: huihui_ai/gpt-oss-abliterated:20b-v2-q4_K_M がインストール済み

3. **Discord Bot**
   - Bot トークンを取得済み
   - 必要な権限:
     - Applications Commands (アプリケーションコマンド)
     - Send Messages (メッセージを送信)
     - Send Messages in Threads (スレッドでメッセージを送信)
     - Create Public Threads (公開スレッドの作成)
     - Read Message History (メッセージ履歴を読む)
   - 注意: Privileged Intents (Message Content Intent) は不要です（スラッシュコマンドのみ使用）

## セットアップ手順

### 1. 環境変数の設定

`.env` ファイルを作成：

```bash
cp .env.example .env
```

編集して必要な値を設定：

```bash
# Discord Bot Configuration
DISCORD_BOT_TOKEN=your_actual_discord_bot_token_here

# Stable Diffusion API Configuration
SD_API_URL=http://localhost:7860
SD_API_TIMEOUT=600

# Ollama LLM Configuration
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=huihui_ai/gpt-oss-abliterated:20b-v2-q4_K_M

# Database Configuration
DATABASE_URL=sqlite+aiosqlite:///./data/database.db

# Storage Configuration
IMAGE_STORAGE_PATH=./data/images

# Generation Defaults
DEFAULT_SAMPLER=Euler a
# DEFAULT_SCHEDULER=Automatic  # 任意。未設定なら自動選択に委ねる
DEFAULT_MODEL=sdxl  # 任意。グローバル既定モデル
```

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 3. データベースのセットアップ

```bash
# マイグレーション実行
alembic upgrade head
```

### 4. Bot の起動

```bash
python -m src.bot
```

起動ログの確認：

```
2024-01-01 00:00:00 | INFO | src.config.logging | Database initialized
2024-01-01 00:00:00 | INFO | src.services.discord_bot | Commands synced
2024-01-01 00:00:00 | INFO | src.services.queue_manager | Queue worker started
2024-01-01 00:00:00 | INFO | src.services.discord_bot | Logged in as YourBot#1234 (ID: 123456789)
```

## 使い方

### 画像生成

1. Discord サーバーで `/generate` コマンドを入力
2. `instruction` パラメータに生成したい画像の説明を入力
3. Enter を押して送信

例：
```
/generate instruction:和風サイバーパンクの女性、夕景、彩度高め
```

### 動作確認

Bot の応答確認：
```
/ping
```

期待される応答：
```
🏓 Pong! レイテンシ: 50ms
```

## トラブルシューティング

### Bot が起動しない

**症状**: `discord.errors.LoginFailure`

**解決策**:
- `.env` ファイルの `DISCORD_BOT_TOKEN` が正しいか確認
- トークンに余分な空白やクォートがないか確認

### スレッド作成エラー（403 Forbidden）

**症状**: `discord.errors.Forbidden: 403 Forbidden (error code: 50001): Missing Access`

**原因**: Botがスレッドを作成する権限がないか、チャンネルがスレッド作成に対応していない

**解決策**:
1. **チャンネルタイプを確認**:
   - スレッドは「テキストチャンネル」または「ニュースチャンネル」でのみ作成できます
   - フォーラムチャンネル、ボイスチャンネル、アナウンスチャンネルでは利用できません

2. **Bot権限を確認**:
   Discord Developer Portal でBotに以下の権限が付与されているか確認:
   - Send Messages (メッセージを送信)
   - Send Messages in Threads (スレッドでメッセージを送信)
   - Create Public Threads (公開スレッドの作成)
   - Read Message History (メッセージ履歴を読む)

3. **チャンネルごとの権限を確認**:
   - チャンネル設定 → 権限 → Botロールの権限を確認
   - 必要に応じてチャンネルレベルでBot権限を上書き

4. **Botを再招待**（権限が不足している場合）:
   - Developer Portal → OAuth2 → URL Generator
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: 上記の権限を選択
   - 生成されたURLでBotを招待

### 画像生成が開始されない

**症状**: `/generate` コマンドは成功するが、画像が生成されない

**解決策**:
1. Stable Diffusion が起動しているか確認
   ```bash
   curl http://localhost:7860/sdapi/v1/sd-models
   ```

2. Ollama が起動しているか確認
   ```bash
   curl http://localhost:11434/api/tags
   ```

3. ログを確認
   ```bash
   # Bot のログで ERROR を探す
   ```

### データベースエラー

**症状**: `sqlalchemy.exc.OperationalError`

**解決策**:
1. `data` ディレクトリが存在するか確認
   ```bash
   mkdir -p data/images
   ```

2. マイグレーションを再実行
   ```bash
   alembic upgrade head
   ```

### タイムアウトエラー

**症状**: `SD_API_TIMEOUT` エラー

**解決策**:
- `.env` の `SD_API_TIMEOUT` を増やす（デフォルト: 600秒）
- Stable Diffusion のパフォーマンスを確認

## 開発モード

### FastAPI サーバーも起動する場合

ターミナル1（Bot）:
```bash
python -m src.bot
```

ターミナル2（API）:
```bash
python -m src.main
```

API ヘルスチェック:
```bash
curl http://localhost:8000/health
```

### ログレベルの変更

`.env` で設定：
```bash
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

## 次のステップ

- [User Story 2: グローバル設定管理](../specs/001-image-gen-agent/spec.md#user-story-2---グローバル設定管理-priority-p2) の実装
- [User Story 3: スレッド内での反復改善](../specs/001-image-gen-agent/spec.md#user-story-3---スレッド内での反復改善-priority-p1) の実装
- テストの追加
- デプロイ設定

## サポート

問題が発生した場合:
1. ログを確認
2. [Issues](https://github.com/hiyori-akane/diffuse-pilot/issues) で報告
3. スタックトレースと環境情報を含める
