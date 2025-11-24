# Implementation Plan: 画像生成エージェント

**Branch**: `001-image-gen-agent` | **Date**: 2025-11-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-image-gen-agent/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Discord上で自然言語指示から画像生成を自動化するエージェントシステム。ユーザーはスラッシュコマンドで指示を送信し、エージェントがプロンプト生成、パラメータ選定、Stable Diffusion API呼び出し、結果投稿を自動実行する。スレッド内での反復改善、グローバル設定管理、オプションのWebリサーチ機能を提供する。

技術アプローチ: 単一Pythonプロセスでの統合実行。discord.py + FastAPI + SQLAlchemy 2.0（async）+ SQLite。ローカルLLM（Ollama互換）でプロンプト生成、Automatic1111 APIで画像生成。1リクエストずつ順次処理するキューイングシステム。

## Technical Context

**Language/Version**: Python 3.10+（開発: macOS, 本番ターゲット: Linux コンテナ）  
**Primary Dependencies**: FastAPI, discord.py, SQLAlchemy 2.0 (async), Alembic, pydantic, httpx, Ollama-compatible LLM client, Automatic1111 API client (http wrapper), Black, Ruff, pre-commit  
**Storage**: SQLite（初期）、画像ファイルはローカルストレージ（SQLiteと同じディレクトリに専用フォルダ）  
**Testing**: unittest, coverage.py（C1分岐網羅目標）, モック/スタブによる外部依存の代替  
**Target Platform**: Linux コンテナ（初期はDocker + systemd/docker-compose、将来的にk8s移行パスを確保）  
**Project Type**: 単一プロジェクト（ボットアプリケーション）  
**Performance Goals**: 初回画像生成3分以内（Webリサーチなし）、追加指示への応答2分以内、数リクエスト/分の処理能力  
**Constraints**: Stable Diffusion API タイムアウト600秒、Discord APIレート制限順守、1リクエストずつ順次処理（並列実行なし）  
**Scale/Scope**: 初期想定: 数十〜数百ギルド、合計数千ユーザー、ピーク数リクエスト/分

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原則 | 状態 | 備考 |
|------|------|------|
| **I. コード品質の強制実施** | ✅ PASS | RuffとBlackによる静的解析・フォーマットを実装予定。GitHub Actionsでの自動チェックと自動修正を設定。 |
| **II. 分岐網羅によるテスト駆動開発** | ✅ PASS | unittestフレームワーク使用、C1分岐網羅を目標設定済み。coverage.pyでカバレッジレポート生成予定。 |
| **III. ボット優先のUX思想** | ✅ PASS | ボットアプリケーションとして設計。UX最適化は二の次、機能的正確性と信頼性を優先。 |
| **IV. パフォーマンス実用主義** | ✅ PASS | 測定可能な要件（3分以内の生成時間）を設定。早すぎる最適化を避け、保守可能なコードを優先。 |
| **V. ドキュメント言語規約** | ✅ PASS | すべてのドキュメント、コミットメッセージ、コメントを日本語で記述。 |

**総合判定**: ✅ すべての憲法原則に準拠。Phase 0への進行を承認。

## Project Structure

### Documentation (this feature)

```text
specs/001-image-gen-agent/
├── spec.md              # 機能仕様書（既存）
├── plan.md              # このファイル（実装計画）
├── research.md          # Phase 0 完了（技術調査・決定事項）
├── data-model.md        # Phase 1 出力（データモデル定義）
├── quickstart.md        # Phase 1 出力（開発者向けクイックスタート）
├── contracts/           # Phase 1 出力（API契約定義）
│   └── api-contract.json
└── tasks.md             # Phase 2 出力（タスク分解 - /speckit.tasksコマンドで生成）
```

### Source Code (repository root)

```text
src/
├── models/              # SQLAlchemy モデル定義
│   ├── generation.py    # GenerationRequest, GenerationMetadata, GeneratedImage
│   ├── settings.py      # GlobalSettings, ThreadContext
│   └── lora.py          # LoRAMetadata, QueuedTask
├── services/            # ビジネスロジック
│   ├── discord_bot.py   # Discord Bot統合（discord.py）
│   ├── prompt_agent.py  # プロンプト生成エージェント（LLM呼び出し）
│   ├── sd_client.py     # Stable Diffusion API クライアント
│   ├── web_research.py  # Webリサーチエージェント（オプション）
│   └── queue_manager.py # タスクキュー管理（順次処理）
├── api/                 # FastAPI エンドポイント
│   ├── health.py        # ヘルスチェック
│   └── admin.py         # 管理用API（オプション）
├── database/            # DB関連
│   ├── connection.py    # SQLAlchemy async engine設定
│   └── migrations/      # Alembic マイグレーション
├── config/              # 設定管理
│   └── settings.py      # pydantic設定（環境変数読み込み）
└── main.py              # アプリケーションエントリーポイント

tests/
├── unit/                # ユニットテスト（モック使用）
│   ├── test_models.py
│   ├── test_prompt_agent.py
│   ├── test_sd_client.py
│   └── test_queue_manager.py
├── integration/         # 統合テスト（実DB使用）
│   ├── test_discord_flow.py
│   └── test_generation_flow.py
└── contract/            # 契約テスト
    └── test_sd_api.py

data/                    # データ保存ディレクトリ
├── database.db          # SQLite DB
└── images/              # 生成画像保存フォルダ
```

**Structure Decision**: 単一プロジェクト構成を採用。ボットアプリケーションとして、すべての機能を1つのPythonプロセスで統合実行する。モジュール分割により保守性を確保しつつ、デプロイの簡素化を優先。

## Complexity Tracking

憲法違反はありません。すべての原則に準拠した設計となっています。

---

## Phase 0: 調査完了 ✅

**成果物**: `research.md`

すべての技術的決定事項が文書化されました：
- 想定スケール、デプロイ方式、モニタリング戦略
- LoRA/モデル管理方針、Web リサーチ実装方針
- LLM統合、DB/マイグレーション戦略
- ベストプラクティスと実装ヒント

---

## Phase 1: 設計完了 ✅

**成果物**: 
- `data-model.md` - 7つのエンティティの詳細定義、ER図、バリデーション、状態遷移
- `contracts/api-contract.json` - API契約定義（OpenAPI仕様）
- `quickstart.md` - 開発者向けセットアップ手順
- `.github/copilot-instructions.md` - GitHub Copilot向けコンテキスト更新

**Constitution Check（再評価）**: ✅ すべての憲法原則に準拠を維持

---

## Phase 2: タスク分解

Phase 2 は `/speckit.tasks` コマンドで実行されます。このコマンドは Phase 1 完了後に実行してください。

**期待される成果物**: `tasks.md` - 実装タスクの優先順位付き分解リスト
