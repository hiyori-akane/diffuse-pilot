# research.md

このファイルは Phase 0 の成果物として、Technical Context の "NEEDS CLARIFICATION" を解決するための決定（Decision）、根拠（Rationale）、代替案（Alternatives）をまとめたものです。

## 前提（推定）
- 開発はローカル（macOS）、本番は Linux コンテナを想定。
- 初期リリースはプロトタイプ / 小規模運用（高同時負荷は想定しない）。必要に応じてスケール方針を見直す。

### 決定 1: 想定スケール
- Decision: 初期は「数十〜数百ギルド、合計で数千ユーザー、ピークで数リクエスト/分」を想定する。負荷は低く、単一ワーカーで順次処理（現仕様）を前提とする。
- Rationale: 仕様書のキュー戦略（1リクエストずつ処理）と成功基準（生成時間目標）に合致。プロトタイプの単純運用で早く価値を出すため。
- Alternatives: すぐに k8s 上でスケール可能な設計にする（メリット: 自動スケール、可用性／HA。デメリット: 開発複雑性増、運用コスト増）。

### 決定 2: 本番デプロイ方式
- Decision: 初期は Docker + systemd / docker-compose でのデプロイを許容。将来的に k8s へ移行するパスを用意する。
- Rationale: シンプルで立ち上げが早い。ローカルで Automatic1111 や Ollama を使うケースと親和性が高い。
- Alternatives: すぐに k8s（Helm）で運用開始（推奨は将来的移行）。

### 決定 3: モニタリング / アラート
- Decision: Prometheus + Grafana を基本とし、必要メトリクス（キュー長、リクエストレイテンシ、SD API エラー率、ディスク容量）をエクスポートする。
- Rationale: OSS で導入コストが低く、将来 k8s に移行しても継続して利用可能。
- Alternatives: SaaS APM（Datadog / Sentry）を使う（導入が早いがコストあり）。

### 決定 4: LoRA/モデル自動ダウンロード
- Decision: 初期は明示的ダウンロードを OFF（仕様の通り）。将来的な自動ダウンロードは、ライセンス・ハッシュ検証・署名の仕組みを設けてから有効化する。
- Rationale: ライセンス・セキュリティ問題のリスク低減。まずはローカルに配置されたリソースで開始する。
- Alternatives: 直ちに自動ダウンロードを実装（リスク: 非互換・ライセンス違反・セキュリティ問題）。

### 決定 5: Web リサーチ（Google Search API）
- Decision: Google Search API を利用する方針。ただしキャッシングとレートリミット対策（backoff + local cache）を組み込む。代替として SerpAPI 等の専用サービスも検討候補。
- Rationale: 要件で Google Search API が明示されているため。結果キャッシュにより同一クエリのコストを削減。
- Alternatives: SerpAPI / Bing Web Search / カスタムスクレイピング（利用規約順守の必要あり）。

### 決定 6: LLM（Ollama）統合
- Decision: Ollama 互換クライアントでローカル LLM を呼び出す。リクエストは短時間のタイムアウトと再試行戦略を持たせ、バッチ/ratelimit 制御を実装する。
- Rationale: ローカルLLMは通信コストと応答遅延の点で有利。モデルは `huihui_ai/gpt-oss-abliterated:20b-v2-q4_K_M` を初期ターゲットにする（仕様に明記）。
- Alternatives: リモート API（Azure/OpenAI等）を併用してフォールバックする。

### 決定 7: DB/Migration
- Decision: SQLModel (SQLAlchemy 2.0) + Alembic を採用し、SQLite を初期ストレージとする。生成パラメータの raw dump は JSON カラムに保存する。
- Rationale: 仕様と憲法の整合性（SQLite + SQLAlchemy が想定されている）。移行・拡張のためAlembicを利用。
- Alternatives: すぐに PostgreSQL を採用（利点: JSONB、同時接続耐性）。移行は将来のスケールに応じて検討。


## ベストプラクティス / 実装ヒント
- エラー耐性: Stable Diffusion 呼び出しは 600s タイムアウト、exponential backoff を採用。長時間処理は非同期タスクで実行。
- 再現性: 生成に使った全パラメータ（seed 含む）を完全に保存し、再生成 API を提供する。
- セキュリティ: LoRA/モデルのメタデータは署名・ハッシュを保存し、改ざん検知を容易にする。
- LLM プロンプト: プロンプト設計エージェントはテンプレート + スロット方式で、ユーザー入力はエスケープ/正規化して渡す。
- テスト: 憲法に合わせて `unittest` + 分岐網羅（C1）を満たすユニットテストを作成する。外部依存はモック化する。

## 仮定の明記（ユーザーアクションが必要なもの）
- 想定トラフィック（複数ギルド / リクエストレート）の目標値の確定
- 本番デプロイ先（k8s 必須か否か）
- Webリサーチ用APIキーの保有とレート制限


---

次のステップ:
1. この research.md をレビューして、上記の仮定（特にスケールとデプロイ方式）を承認するか、具体値を指定してください。
2. 承認を受けたら Phase 1 に進み、`data-model.md`、`/contracts`、`quickstart.md` を生成します。
