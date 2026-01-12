# マニュアル

## コマンド一覧

- /ping: Botの稼働確認
- /generate instruction:<説明>: 画像生成を開始

### 設定

- `/settings show` - displays active settings (user > guild > app defaults), showing both user and server settings when available
- `/settings set <type> <value> [scope]` - updates specific setting with scope selection
  - `scope:ユーザー専用` (default) - user-specific settings
  - `scope:サーバー全体` - server-wide default settings
- `/settings reset [scope]` - removes user/guild settings with scope selection
  - `scope:ユーザー専用` (default) - remove user-specific settings
  - `scope:サーバー全体` - remove server-wide default settings

### 設定例

```python
# Via Discord - User-specific settings (default)
/settings set setting_type:デフォルトモデル value:sdxl
/settings set setting_type:ステップ数 value:30
/settings set setting_type:シード値 value:20251121

# Via Discord - Server-wide default settings
/settings set setting_type:デフォルトモデル value:sdxl scope:サーバー全体
/settings set setting_type:ステップ数 value:25 scope:サーバー全体
```


