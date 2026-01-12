# data-model.md

このドキュメントでは、画像生成エージェントの主要エンティティ、フィールド、関連、バリデーション、状態遷移を定義します。

## エンティティ概要

以下のエンティティは SQLAlchemy 2.0 (async) + SQLModel で実装され、SQLite DB に永続化されます。

---

## 1. GenerationRequest

画像生成リクエストを表すエンティティ。ユーザーが Discord で指示を送信すると生成されます。

### フィールド

| フィールド名 | 型 | 制約 | 説明 |
|------------|-----|------|------|
| id | UUID | PK | リクエストの一意識別子 |
| guild_id | str | NOT NULL, INDEXED | Discord サーバー（guild）ID |
| user_id | str | NOT NULL, INDEXED | Discord ユーザー ID |
| thread_id | str | NOT NULL, INDEXED | Discord スレッド ID |
| original_instruction | str | NOT NULL | ユーザーの元指示（自然言語） |
| status | enum | NOT NULL | リクエストステータス（pending / processing / completed / failed） |
| created_at | datetime | NOT NULL | 作成日時（UTC） |
| updated_at | datetime | NOT NULL | 更新日時（UTC） |
| error_message | str | NULLABLE | エラー時のメッセージ |

### 関連

- **1対多**: GenerationRequest → GeneratedImage（1つのリクエストから複数の画像が生成される）
- **1対1**: GenerationRequest → GenerationMetadata（最終的に使用された設定）

### バリデーション

- `guild_id`, `user_id`, `thread_id` は Discord API の形式（数値文字列）に準拠
- `original_instruction` は最大 2000 文字（Discord メッセージ上限を考慮）
- `status` は定義された enum 値のみ許容

### 状態遷移

```
pending → processing → completed
                    ↘ failed
```

- **pending**: リクエスト受付直後、キューに入れられた状態
- **processing**: プロンプト生成・設定選定・画像生成中
- **completed**: 画像が正常に生成され、Discord に投稿完了
- **failed**: 何らかのエラーで失敗（タイムアウト / API エラー等）

---

## 2. GenerationMetadata

画像生成に使用した完全な設定を保存するエンティティ。再現性のために全パラメータを記録します。

### フィールド

| フィールド名 | 型 | 制約 | 説明 |
|------------|-----|------|------|
| id | UUID | PK | メタデータの一意識別子 |
| request_id | UUID | FK (GenerationRequest.id), NOT NULL | 関連する GenerationRequest |
| prompt | str | NOT NULL | 最終的に使用されたプロンプト |
| negative_prompt | str | NULLABLE | ネガティブプロンプト |
| model_name | str | NOT NULL | 使用された Stable Diffusion モデル名 |
| lora_list | JSON | NULLABLE | 使用された LoRA のリスト（名前、重み） |
| steps | int | NOT NULL | Sampling steps |
| cfg_scale | float | NOT NULL | CFG scale |
| sampler | str | NOT NULL | サンプラー名（e.g., Euler a, DPM++） |
| scheduler | str | NULLABLE | スケジューラー名 |
| seed | int | NOT NULL | 使用された seed 値 |
| width | int | NOT NULL | 画像幅（px） |
| height | int | NOT NULL | 画像高さ（px） |
| raw_params | JSON | NULLABLE | その他のパラメータを JSON で保存（拡張性） |
| created_at | datetime | NOT NULL | 作成日時（UTC） |

### 関連

- **多対1**: GenerationMetadata → GenerationRequest
- **1対多**: GenerationMetadata → GeneratedImage（同じ設定で複数枚生成される場合）

### バリデーション

- `steps`: 1 ≤ steps ≤ 150（一般的な Stable Diffusion の範囲）
- `cfg_scale`: 1.0 ≤ cfg_scale ≤ 30.0
- `seed`: 0 ≤ seed ≤ 2^32 - 1
- `width`, `height`: 64 ≤ size ≤ 2048（8の倍数を推奨）

---

## 3. GeneratedImage

生成された画像を表すエンティティ。ファイルパス、Discord 投稿 URL、メタデータへの参照を持ちます。

### フィールド

| フィールド名 | 型 | 制約 | 説明 |
|------------|-----|------|------|
| id | UUID | PK | 画像の一意識別子 |
| request_id | UUID | FK (GenerationRequest.id), NOT NULL | 関連するリクエスト |
| metadata_id | UUID | FK (GenerationMetadata.id), NOT NULL | 使用された設定 |
| file_path | str | NOT NULL, UNIQUE | ローカルストレージのファイルパス |
| discord_url | str | NULLABLE | Discord にアップロード後の CDN URL |
| file_size_bytes | int | NOT NULL | ファイルサイズ（バイト） |
| created_at | datetime | NOT NULL | 生成日時（UTC） |

### 関連

- **多対1**: GeneratedImage → GenerationRequest
- **多対1**: GeneratedImage → GenerationMetadata

### バリデーション

- `file_path` は絶対パスで、存在検証可能
- `file_size_bytes` > 0

---

## 4. GlobalSettings

サーバー（guild）ごと、ユーザーごとのグローバル設定を保存します。

### フィールド

| フィールド名 | 型 | 制約 | 説明 |
|------------|-----|------|------|
| id | UUID | PK | 設定の一意識別子 |
| guild_id | str | NOT NULL, INDEXED | Discord サーバー ID |
| user_id | str | NULLABLE, INDEXED | ユーザー ID（NULL の場合はサーバー全体のデフォルト） |
| default_model | str | NULLABLE | デフォルトの Stable Diffusion モデル |
| default_lora_list | JSON | NULLABLE | デフォルト LoRA リスト |
| default_prompt_suffix | str | NULLABLE | 自動追加するプロンプト suffix |
| default_sd_params | JSON | NULLABLE | デフォルトの SD パラメータ（steps, cfg, sampler 等） |
| created_at | datetime | NOT NULL | 作成日時 |
| updated_at | datetime | NOT NULL | 更新日時 |

### 関連

- スタンドアロン（他エンティティとの直接関連なし）

### バリデーション

- `guild_id` は必須
- `user_id` は NULLABLE（サーバーデフォルトの場合）
- UNIQUE制約: (guild_id, user_id) — 同一サーバー・同一ユーザーの設定は1つのみ

---

## 5. ThreadContext

スレッドごとのコンテキスト（生成履歴、最新設定）を管理します。

### フィールド

| フィールド名 | 型 | 制約 | 説明 |
|------------|-----|------|------|
| id | UUID | PK | コンテキストの一意識別子 |
| guild_id | str | NOT NULL, INDEXED | Discord サーバー ID |
| thread_id | str | NOT NULL, UNIQUE | Discord スレッド ID |
| user_id | str | NOT NULL | スレッド作成者 |
| generation_history | JSON | NULLABLE | 生成履歴（request_id のリスト） |
| latest_metadata_id | UUID | FK (GenerationMetadata.id), NULLABLE | 最新の設定への参照 |
| created_at | datetime | NOT NULL | 作成日時 |
| updated_at | datetime | NOT NULL | 更新日時 |

### 関連

- **多対1**: ThreadContext → GenerationMetadata（latest_metadata_id）

### バリデーション

- `thread_id` は UNIQUE（スレッドごとに1つのコンテキスト）
- `generation_history` は JSON 配列形式

### 状態遷移

スレッドコンテキストは、新しい画像が生成されるたびに `latest_metadata_id` と `generation_history` が更新されます。

---

## 6. LoRAMetadata

LoRA ファイルの情報を保存します。説明文、タグ、ファイルパス等を管理します。

### フィールド

| フィールド名 | 型 | 制約 | 説明 |
|------------|-----|------|------|
| id | UUID | PK | LoRA の一意識別子 |
| name | str | NOT NULL, UNIQUE | LoRA 名（ファイル名から取得） |
| file_path | str | NOT NULL, UNIQUE | ローカルストレージのファイルパス |
| description | str | NULLABLE | LoRA の説明文 |
| tags | JSON | NULLABLE | タグのリスト（例: ["anime", "style"]） |
| file_hash | str | NULLABLE | ファイルハッシュ（SHA256、改ざん検知用） |
| downloaded_at | datetime | NULLABLE | ダウンロード日時（将来の自動ダウンロード機能用） |
| created_at | datetime | NOT NULL | DB 登録日時 |

### 関連

- スタンドアロン（GenerationMetadata の lora_list で名前参照される）

### バリデーション

- `name` は UNIQUE
- `file_path` は UNIQUE、存在検証可能
- `file_hash` は SHA256 形式（64文字の16進数）

---

## 7. QueuedTask

タスクキューを管理するエンティティ。画像生成、LoRA ダウンロード、Web リサーチなどのタスクを順次処理します。

### フィールド

| フィールド名 | 型 | 制約 | 説明 |
|------------|-----|------|------|
| id | UUID | PK | タスクの一意識別子 |
| task_type | enum | NOT NULL | タスク種別（image_gen / lora_download / web_research） |
| priority | int | NOT NULL, DEFAULT 0 | 優先度（高いほど先に処理） |
| status | enum | NOT NULL | ステータス（queued / processing / completed / failed） |
| payload | JSON | NOT NULL | タスク固有のペイロード（リクエスト ID 等） |
| error_message | str | NULLABLE | エラー時のメッセージ |
| created_at | datetime | NOT NULL | 作成日時 |
| started_at | datetime | NULLABLE | 処理開始日時 |
| completed_at | datetime | NULLABLE | 完了日時 |

### 関連

- スタンドアロン（payload に他エンティティの ID を含む）

### バリデーション

- `task_type` は定義された enum 値のみ
- `status` は定義された enum 値のみ
- `payload` は JSON 形式

### 状態遷移

```
queued → processing → completed
                   ↘ failed
```

- **queued**: キューに入れられた状態
- **processing**: ワーカーが処理中
- **completed**: 正常完了
- **failed**: エラーで失敗

---

## ER 図（簡易版）

```
GenerationRequest (1) ─────< (∞) GeneratedImage
       │                            │
       │                            │
       └──> (1) GenerationMetadata <┘
                     ↑
                     │
            ThreadContext (latest_metadata_id)

GlobalSettings (standalone, per guild/user)
LoRAMetadata (standalone, referenced by name in GenerationMetadata.lora_list)
QueuedTask (standalone, contains payload with IDs)
```

---

## 実装時の考慮事項

1. **JSON フィールド**: `lora_list`, `raw_params`, `default_lora_list`, `default_sd_params`, `generation_history`, `tags`, `payload` は SQLite の JSON 型を利用（SQLAlchemy の `JSON` 型マッピング）。
2. **インデックス**: `guild_id`, `user_id`, `thread_id` には B-tree インデックスを作成してクエリ高速化。
3. **外部キー制約**: SQLite で外部キー制約を有効化（`PRAGMA foreign_keys = ON`）。
4. **タイムゾーン**: すべての datetime は UTC で保存し、表示時にローカライズ。
5. **マイグレーション**: Alembic でスキーマ変更を管理。初期マイグレーションでこれらのテーブルを作成。

---

次のステップ:
- API 契約（OpenAPI スキーマ）の生成
- quickstart.md の作成
