# GitHubのContributorsからkght6123を削除する方法

## 状況

GitHubのContributorsページに古いアカウント（kght6123）が表示されたままになっている場合があります。これはGitHubのキャッシュが原因です。

## 現在の履歴状態

ローカルリポジトリの履歴は既に完全にクリーンです：

```bash
# 確認コマンド
git log --all --format="%an %ae" | sort | uniq
# 結果: hiyori-akane cooker-94-less@icloud.com のみ
```

## GitHubのContributorsが更新されない理由

1. **GitHubのキャッシュ**: GitHubは統計情報をキャッシュしており、即座に更新されません
2. **更新タイミング**: 新しいコミットがプッシュされたときに再計算されます
3. **完全な削除**: 場合によっては24-48時間かかることがあります

## 対処方法

### 方法1: 新しいコミットをプッシュして更新を促す（推奨）

GitHubのキャッシュを更新するため、新しいコミットをプッシュします：

```bash
# ダミーコミットを作成
git commit --allow-empty -m "Update contributors cache"
git push origin main
```

### 方法2: 時間を置いて待つ

GitHub側で自動的にキャッシュが更新されるのを待ちます（通常24-48時間）。

### 方法3: GitHubサポートに連絡

上記の方法で解決しない場合、GitHubサポートに連絡してキャッシュのクリアを依頼できます：

1. https://support.github.com/contact にアクセス
2. 「リポジトリのContributors情報が古い」旨を説明
3. リポジトリURLを提供

### 方法4: リポジトリの再作成（最終手段）

どうしても解決しない場合は、リポジトリを削除して再作成します：

```bash
# 1. GitHubでリポジトリを削除
# https://github.com/hiyori-akane/diffuse-pilot/settings

# 2. 同じ名前で新規リポジトリを作成

# 3. ローカルから再プッシュ
git remote set-url origin https://github.com/hiyori-akane/diffuse-pilot.git
git push -u origin main
```

**注意**: リポジトリを削除すると、Issues、Pull Requests、Stars、Watchersなども削除されます。

## 確認方法

### ローカルの履歴を確認

```bash
# すべてのコミットの著者を確認
git log --all --format="%an %ae"

# kght6123が含まれていないことを確認
git log --all --format="%an %ae" | grep -i kght6123
# 結果: 何も表示されなければOK
```

### GitHubのContributorsを確認

以下のURLで確認できます：
```
https://github.com/hiyori-akane/diffuse-pilot/graphs/contributors
```

## よくある質問

### Q. 履歴を削除したのにContributorsに残っているのはなぜ？

A. GitHubは統計情報をキャッシュしているためです。新しいコミットをプッシュすることで、キャッシュの更新を促すことができます。

### Q. どのくらい待てば更新される？

A. 通常は新しいコミットをプッシュ後、数時間から24時間以内に更新されます。最大48時間かかる場合もあります。

### Q. Contributorsグラフの過去の統計も消える？

A. はい、履歴を完全に削除したため、過去の統計グラフもリセットされます。

### Q. フォークしたリポジトリのContributorsはどうなる？

A. フォーク元のリポジトリには影響しません。フォークしたリポジトリのContributorsのみが対象です。

## 参考リンク

- [GitHub Docs - About repository contributors](https://docs.github.com/en/repositories/viewing-activity-and-data-for-your-repository/viewing-a-projects-contributors)
- [GitHub Docs - Why are my contributions not showing up on my profile?](https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-github-profile/managing-contribution-settings-on-your-profile/why-are-my-contributions-not-showing-up-on-my-profile)
