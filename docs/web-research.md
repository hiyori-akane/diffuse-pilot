# Webリサーチ機能

## 概要

Webリサーチ機能は、ユーザーがテーマや目的を指定すると、エージェントがWeb上から最新のベストプラクティス（プロンプトテクニック、推奨設定、人気のLoRA等）を自動的に収集し、要約して画像生成に反映する機能です。

## 設定

### 必要な環境変数

Webリサーチ機能を使用するには、Google Custom Search APIの認証情報が必要です。

`.env` ファイルに以下の環境変数を設定してください：

```bash
# Google Custom Search API の設定
GOOGLE_SEARCH_API_KEY=your_google_api_key_here
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id_here
```

### Google Custom Search APIの設定方法

1. **Google Cloud Consoleでプロジェクトを作成**
   - https://console.cloud.google.com/ にアクセス
   - 新しいプロジェクトを作成

2. **Custom Search APIを有効化**
   - APIとサービス > ライブラリ に移動
   - "Custom Search API" を検索して有効化

3. **APIキーを取得**
   - APIとサービス > 認証情報 に移動
   - "認証情報を作成" > "APIキー" を選択
   - 作成されたAPIキーをコピー

4. **検索エンジンIDを取得**
   - https://programmablesearchengine.google.com/ にアクセス
   - "Add" をクリックして新しい検索エンジンを作成
   - 検索対象: "全ウェブを検索" を選択
   - 作成後、検索エンジンIDをコピー

## 使い方

### Discord コマンド

Webリサーチを有効にして画像を生成するには、`/generate` コマンドで `web_research` オプションを `True` に設定します：

```
/generate instruction:"アニメスタイルの風景画" web_research:True
```

デフォルトでは `web_research` は `False` です。

### リサーチをスキップする

特定のキーワードを含む指示を送ると、Webリサーチを自動的にスキップします：

- "リサーチなし"
- "リサーチしない"
- "調べないで"
- "すぐに生成"

例：
```
/generate instruction:"リサーチなしで和風サイバーパンクの女性を生成" web_research:True
```

この場合、`web_research:True` が指定されていても、"リサーチなし" というキーワードが含まれているため、Webリサーチはスキップされます。

## 機能詳細

### 検索クエリ構築

ユーザーの指示から自動的に検索クエリを構築します。クエリには以下が含まれます：

- "Stable Diffusion"
- ユーザーのテーマ
- "prompt techniques"
- "best practices"

例：ユーザーが "アニメスタイルの風景画" と指定した場合、検索クエリは：
```
Stable Diffusion アニメスタイルの風景画 prompt techniques best practices
```

### ベストプラクティス抽出

検索結果からLLMを使用して以下の情報を抽出します：

- **summary**: 検索結果の要約（2-3文）
- **prompt_techniques**: 推奨されるプロンプトテクニック
- **recommended_loras**: 推奨されるLoRA
- **recommended_settings**: 推奨される設定（steps, cfg_scale, sampler等）
- **sources**: 参照元のURL

### キャッシング

検索結果は7日間キャッシュされます。同じテーマで再度リサーチを行う場合、キャッシュから結果を取得するため、API呼び出しを節約できます。

### レート制限

Google Custom Search APIのレート制限に対応しています：

- リクエスト間の最小間隔: 1秒
- レート制限エラー時の指数バックオフ（最大3回リトライ）

## Discord での表示

画像生成が完了すると、Webリサーチのサマリーが表示されます：

```
🎉 画像生成が完了しました！ (4枚)

📚 Webリサーチサマリー:
アニメスタイルの風景画には、詳細な色彩表現と空気感の表現が重要です。

💡 推奨テクニック: detailed background, anime landscape, vibrant colors
📖 参照元: https://example.com/tips, https://example.com/guide

**プロンプト:**
```
anime landscape, detailed background, vibrant colors, sunset, ...
```
**パラメータ:**
• モデル: default
• サイズ: 512x512
• ステップ数: 30
• CFG Scale: 8.0
...
```

## トラブルシューティング

### Webリサーチが実行されない

- 環境変数 `GOOGLE_SEARCH_API_KEY` と `GOOGLE_SEARCH_ENGINE_ID` が正しく設定されているか確認
- APIキーが有効か確認
- Google Cloud Console でCustom Search APIが有効化されているか確認

### エラーが発生する

Webリサーチでエラーが発生しても、画像生成自体は継続されます。ログに警告が記録され、リサーチ結果なしで画像生成が行われます。

### レート制限に達する

Google Custom Search APIには無料枠があります（1日100クエリ）。上限に達した場合は、翌日までお待ちいただくか、有料プランへのアップグレードをご検討ください。

## データベース

### web_research_cache テーブル

検索結果をキャッシュするためのテーブル：

| カラム | 型 | 説明 |
|--------|-----|------|
| id | String(36) | UUID |
| query_hash | String(64) | クエリのSHA-256ハッシュ |
| query | Text | 検索クエリ |
| results | JSON | リサーチ結果 |
| created_at | DateTime | 作成日時 |
| expires_at | DateTime | 有効期限（作成日時 + 7日） |

キャッシュエントリは自動的には削除されません。定期的なクリーンアップが必要な場合は、`expires_at` を基準に古いエントリを削除してください。

## セキュリティ

- APIキーは `.env` ファイルに保存され、Gitにコミットされません
- APIキーは環境変数から読み込まれ、ログに記録されません
- 検索クエリとキャッシュデータは暗号化されていません（機密情報を含む検索は避けてください）

## パフォーマンス

- 初回リサーチ: 検索 + LLM処理で約5-10秒
- キャッシュヒット時: 1秒未満
- リサーチなしの通常生成に比べて、約5-10秒の追加時間

## API制限

Google Custom Search API の制限：

- 無料枠: 1日100クエリ
- クエリごとの結果: 最大10件（本実装では5件取得）
- レート制限: リクエストごとの最小間隔1秒（本実装で対応済み）

詳細は Google の公式ドキュメントを参照してください：
https://developers.google.com/custom-search/v1/overview
