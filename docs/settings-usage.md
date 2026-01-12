# グローバル設定管理機能

Phase 4: User Story 2 で実装されたグローバル設定管理機能の使い方を説明します。

## 機能概要

ユーザーが Discord コマンドまたは API でグローバル設定を管理できます。設定は以下の項目をカスタマイズできます：

- **デフォルトモデル**: 使用する Stable Diffusion モデル
- **デフォルト LoRA**: 自動的に適用される LoRA のリスト
- **デフォルトプロンプト suffix**: すべてのプロンプトに自動追加されるテキスト
- **デフォルト SD パラメータ**: ステップ数、CFG スケール、サンプラー、画像サイズなど（scheduler はグローバル設定では未管理）
- **アプリケーション既定**: `.env` の `DEFAULT_MODEL`, `DEFAULT_SAMPLER` と任意 `DEFAULT_SCHEDULER`（指定しなければ API の自動スケジューラ）

## Discord コマンド

### `/settings show`

現在の設定を表示します。

```
/settings show
```

**表示内容：**
- ユーザー専用の設定がある場合はそれを表示
- サーバーデフォルト設定がある場合はそれを表示
- 両方ある場合は両方を表示し、ユーザー設定が優先されることを通知
- どちらもない場合は「設定がまだ作成されていません」と表示

### `/settings set`

設定を更新します。

```
/settings set setting_type:デフォルトモデル value:sdxl scope:ユーザー専用
```

**パラメータ:**
- `setting_type`: 設定の種類（必須）
- `value`: 設定値（必須）
- `scope`: 設定の適用範囲（オプション、デフォルト: ユーザー専用）
  - `ユーザー専用`: あなた専用の設定として保存
  - `サーバー全体`: サーバー全体のデフォルト設定として保存

設定可能な項目：
- **デフォルトモデル**: モデル名（例: `sdxl`, `sd15`）
- **デフォルトプロンプト suffix**: プロンプトに追加するテキスト（例: `masterpiece, best quality`）
- **ステップ数**: 生成ステップ数（1-150）
- **CFG スケール**: CFG スケール（1.0-30.0）
- **サンプラー**: サンプラー名（例: `Euler a`, `DPM++ 2M Karras`）
  - 注意: スケジューラはコマンド経由では設定できません。アプリ側で未指定の場合は Stable Diffusion WebUI が自動選択します。
- **画像幅**: 画像の幅（64-2048）
- **画像高さ**: 画像の高さ（64-2048）

例：
```
# ユーザー専用設定
/settings set setting_type:ステップ数 value:30 scope:ユーザー専用

# サーバー全体のデフォルト設定
/settings set setting_type:デフォルトモデル value:sdxl scope:サーバー全体
/settings set setting_type:デフォルトプロンプト suffix value:masterpiece, best quality, highly detailed scope:サーバー全体
```

### `/settings reset`

設定をリセット（削除）します。

```
/settings reset scope:ユーザー専用
```

**パラメータ:**
- `scope`: 設定の適用範囲（オプション、デフォルト: ユーザー専用）
  - `ユーザー専用`: あなた専用の設定を削除
  - `サーバー全体`: サーバー全体のデフォルト設定を削除

例：
```
# ユーザー専用設定をリセット
/settings reset scope:ユーザー専用

# サーバー全体のデフォルト設定をリセット
/settings reset scope:サーバー全体
```

## API エンドポイント

### GET /api/v1/settings

グローバル設定を取得します。

**リクエスト:**
```http
GET /api/v1/settings?guild_id=123456789&user_id=987654321
```

**パラメータ:**
- `guild_id` (必須): Discord サーバー（guild）ID
- `user_id` (オプション): Discord ユーザー ID（省略時はサーバーデフォルト）

**レスポンス（200 OK）:**
```json
{
  "settings_id": "uuid",
  "guild_id": "123456789",
  "user_id": "987654321",
  "default_model": "sdxl",
  "default_lora_list": [
    {"name": "anime-style", "weight": 1.0}
  ],
  "default_prompt_suffix": "masterpiece, best quality",
  "default_sd_params": {
    "steps": 30,
    "cfg_scale": 7.5,
    "sampler": "DPM++ 2M Karras",
    "width": 768,
    "height": 768
  },
  "created_at": "2025-11-14T12:00:00Z",
  "updated_at": "2025-11-14T12:30:00Z"
}
```

**エラーレスポンス（404 Not Found）:**
```json
{
  "detail": "Settings not found"
}
```

### PUT /api/v1/settings

グローバル設定を更新（または作成）します。

**リクエスト:**
```http
PUT /api/v1/settings
Content-Type: application/json

{
  "guild_id": "123456789",
  "user_id": "987654321",
  "default_model": "sdxl",
  "default_prompt_suffix": "masterpiece, best quality",
  "default_sd_params": {
    "steps": 30,
    "cfg_scale": 7.5
  }
}
```

**リクエストボディ:**
- `guild_id` (必須): Discord サーバー（guild）ID
- `user_id` (オプション): Discord ユーザー ID（null の場合はサーバーデフォルト）
- `default_model` (オプション): デフォルトモデル
- `default_lora_list` (オプション): デフォルト LoRA リスト
- `default_prompt_suffix` (オプション): デフォルトプロンプト suffix
- `default_sd_params` (オプション): デフォルト SD パラメータ

**レスポンス（200 OK）:**
GET と同じ形式のレスポンス

**エラーレスポンス（400 Bad Request）:**
```json
{
  "detail": "デフォルトモデル名が無効です"
}
```

## 設定の優先順位

画像生成時、設定は以下の優先順位で適用されます：

1. **ユーザー設定**: ユーザー専用の設定がある場合、それを使用
2. **サーバーデフォルト設定**: ユーザー設定がない場合、サーバーデフォルト設定を使用
3. **アプリケーションデフォルト**: どちらもない場合、環境変数で定義されたデフォルト値 (`DEFAULT_SAMPLER`, `DEFAULT_SCHEDULER`) を使用。`DEFAULT_SCHEDULER` が未設定なら scheduler は送信されず API が自動補正。

## バリデーション

設定値は以下のバリデーションルールに従います：

- **default_model**: 空でない文字列
- **default_lora_list**: 配列または辞書形式。各要素に `name` フィールドが必要
- **steps**: 1 から 150 の整数
- **cfg_scale**: 1.0 から 30.0 の数値
- **width / height**: 64 から 2048 の整数

バリデーションエラーが発生した場合、エラーメッセージが返されます。未知サンプラーは送信前に省略され API の既定に委ねられます（ログに警告出力）。

## 使用例

### シナリオ 1: サーバーデフォルト設定の作成

管理者がサーバー全体のデフォルト設定を作成：

```
/settings set setting_type:デフォルトモデル value:sdxl scope:サーバー全体
/settings set setting_type:ステップ数 value:25 scope:サーバー全体
/settings set setting_type:デフォルトプロンプト suffix value:masterpiece, best quality scope:サーバー全体
```

この設定はサーバー内の全ユーザーに適用されます（ユーザー個別設定がない場合）。

### シナリオ 2: ユーザー個別設定の作成

ユーザーが自分専用の設定を作成：

```
/settings set setting_type:ステップ数 value:40 scope:ユーザー専用
/settings set setting_type:CFG スケール value:8.0 scope:ユーザー専用
```

この設定はそのユーザーの画像生成にのみ適用されます。`scope` パラメータを省略した場合、デフォルトで「ユーザー専用」になります。

### シナリオ 3: 画像生成での自動適用

ユーザーが `/generate` コマンドを実行すると、上記で設定した値が自動的に適用されます：

```
/generate instruction:美しい風景
```

この指示に対して、以下の設定が自動適用されます：
- モデル: sdxl
- ステップ数: 40（ユーザー設定）
- CFG スケール: 8.0（ユーザー設定）
- プロンプト suffix: "masterpiece, best quality"（サーバー設定）

最終的なプロンプト: "beautiful landscape, masterpiece, best quality"

## トラブルシューティング

### 設定が反映されない

1. `/settings show` で設定が正しく保存されているか確認
2. ユーザー設定とサーバー設定のどちらが適用されているか確認
3. バリデーションエラーが発生していないか確認

### バリデーションエラー

設定値が許容範囲外の場合、エラーメッセージが表示されます。エラーメッセージに従って値を修正してください。

### 設定をリセットしたい

`/settings reset` コマンドを実行すると、設定を削除できます。サーバーデフォルト設定に戻したい場合に使用します。
