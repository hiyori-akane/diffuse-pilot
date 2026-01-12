---
description: "Task list for 画像生成エージェント implementation"
---

# Tasks: 画像生成エージェント

**Input**: Design documents from `/specs/001-image-gen-agent/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-contract.json

**Tests**: Tests are NOT explicitly requested in the specification, so test tasks are excluded.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

This is a single project - paths use `src/`, `tests/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project directory structure: src/{models,services,api,database,config}, tests/{unit,integration,contract}, data/images
- [x] T002 Initialize Python project with pyproject.toml: FastAPI, discord.py, SQLAlchemy 2.0, Alembic, pydantic, httpx, ollama client, Black, Ruff, pre-commit
- [x] T003 [P] Configure Black formatter in pyproject.toml with line-length=100
- [x] T004 [P] Configure Ruff linter in pyproject.toml with select rules
- [x] T005 [P] Setup pre-commit hooks in .pre-commit-config.yaml for Black and Ruff
- [x] T006 Create requirements.txt from pyproject.toml dependencies
- [x] T007 Create .env.example file with all required environment variables (DISCORD_BOT_TOKEN, SD_API_URL, OLLAMA_API_URL, etc.)
- [x] T008 Create .gitignore for Python project (.env, __pycache__, *.pyc, data/, venv/, .coverage)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T009 Create database connection module in src/database/connection.py with async SQLAlchemy engine for SQLite
- [x] T010 Create Alembic configuration in alembic.ini and alembic/env.py for async migrations
- [x] T011 Create initial Alembic migration script for all 7 entities (GenerationRequest, GenerationMetadata, GeneratedImage, GlobalSettings, ThreadContext, LoRAMetadata, QueuedTask)
- [x] T012 [P] Create base configuration in src/config/settings.py using pydantic.BaseSettings for environment variable loading
- [x] T013 [P] Create logging configuration in src/config/logging.py with INFO level, structured logging format
- [x] T014 [P] Create error handling utilities in src/services/error_handler.py for consistent error responses
- [x] T015 Create GenerationRequest model in src/models/generation.py with all fields, enums, validations
- [x] T016 Create GenerationMetadata model in src/models/generation.py with all fields, JSON columns, validations
- [x] T017 Create GeneratedImage model in src/models/generation.py with file_path, discord_url, relationships
- [x] T018 [P] Create GlobalSettings model in src/models/settings.py with guild_id, user_id, JSON columns
- [x] T019 [P] Create ThreadContext model in src/models/settings.py with generation_history JSON, latest_metadata_id FK
- [x] T020 [P] Create LoRAMetadata model in src/models/lora.py with name, file_path, description, tags, file_hash
- [x] T021 [P] Create QueuedTask model in src/models/lora.py with task_type enum, priority, status enum, payload JSON
- [x] T022 Run Alembic migration to create database schema: alembic upgrade head
- [x] T023 Create FastAPI application instance in src/main.py with CORS middleware, exception handlers, lifespan events
- [x] T024 Create health check endpoint in src/api/health.py returning status and timestamp

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Discord経由の基本画像生成 (Priority: P1) 🎯 MVP

**Goal**: ユーザーがDiscordで自然言語の指示を送ると、エージェントが自動的にプロンプトを作成し、適切な設定を選択して、Stable Diffusionで画像を生成し、結果をDiscordのスレッドに投稿する。

**Independent Test**: Discordでスラッシュコマンド「/generate 和風サイバーパンクの女性、夕景、彩度高め」と入力し、エージェントがプロンプトを生成し、Stable Diffusionで画像を作成し、Discordスレッドに投稿することを確認できる。

### Implementation for User Story 1

- [x] T025 [P] [US1] Create Discord bot client in src/services/discord_bot.py with discord.py, slash command registration
- [x] T026 [P] [US1] Implement /generate slash command handler in src/services/discord_bot.py to create thread and queue request
- [x] T027 [P] [US1] Create Ollama LLM client wrapper in src/services/prompt_agent.py with httpx for async requests
- [x] T028 [P] [US1] Create Stable Diffusion API client in src/services/sd_client.py with httpx, 600s timeout
- [x] T029 [US1] Implement prompt generation logic in src/services/prompt_agent.py using Ollama LLM (huihui_ai/gpt-oss-abliterated:20b-v2-q4_K_M)
- [x] T030 [US1] Implement parameter selection logic in src/services/prompt_agent.py (steps, cfg_scale, sampler, seed, width=512, height=512)
- [x] T031 [US1] Create task queue manager in src/services/queue_manager.py for sequential task processing (1 request at a time)
- [x] T032 [US1] Implement image generation workflow in src/services/queue_manager.py: fetch task → generate prompt → call SD API → save image → update DB
- [x] T033 [US1] Add image file storage logic in src/services/queue_manager.py to save images to data/images/ with UUID filenames
- [x] T034 [US1] Implement Discord thread posting in src/services/discord_bot.py to upload images with metadata (prompt, model, LoRA, settings)
- [x] T035 [US1] Add error handling in src/services/queue_manager.py for SD API errors and timeouts with Discord error message posting
- [x] T036 [US1] Implement request status tracking in src/services/queue_manager.py updating GenerationRequest status (pending → processing → completed/failed)
- [x] T037 [US1] Add logging for all major operations in src/services/queue_manager.py (request received, prompt generated, SD API called, images saved, posted to Discord)
- [x] T038 [US1] Create bot startup script in src/bot.py to initialize Discord client and start queue worker
- [x] T039 [US1] Implement generation API endpoint POST /api/v1/generate in src/api/generate.py per api-contract.json
- [x] T040 [US1] Implement GET /api/v1/requests/{request_id} endpoint in src/api/generate.py to return request details

**Checkpoint**: At this point, User Story 1 should be fully functional - users can generate images via Discord /generate command

---

## Phase 4: User Story 2 - グローバル設定管理 (Priority: P2)

**Goal**: ユーザーがDiscordコマンドでグローバル設定（デフォルトモデル、LoRA、Stable Diffusion設定、デフォルトプロンプト）を変更すると、以降の画像生成でその設定が自動的に適用される。

**Independent Test**: Discordで「/settings set model sdxl」と入力し、次回の画像生成でSDXLモデルが使用されることを確認できる。また、「/settings set default_lora anime-style」と設定し、以降の生成で自動的にそのLoRAが適用されることを確認できる。

### Implementation for User Story 2

- [x] T041 [P] [US2] Create GlobalSettings service in src/services/settings_service.py with CRUD operations (get, create, update)
- [x] T042 [P] [US2] Implement /settings slash command group in src/services/discord_bot.py with subcommands (set, show, reset)
- [x] T043 [US2] Implement /settings set command handler in src/services/discord_bot.py to update GlobalSettings for guild/user
- [x] T044 [US2] Implement /settings show command handler in src/services/discord_bot.py to display current settings
- [x] T045 [US2] Implement /settings reset command handler in src/services/discord_bot.py to delete custom settings
- [x] T046 [US2] Add settings lookup logic in src/services/prompt_agent.py to load GlobalSettings before prompt generation
- [x] T047 [US2] Update parameter selection in src/services/prompt_agent.py to merge GlobalSettings defaults with user instruction
- [x] T048 [US2] Add default_prompt_suffix appending in src/services/prompt_agent.py to final prompt
- [x] T049 [US2] Implement GET /api/v1/settings endpoint in src/api/settings.py per api-contract.json
- [x] T050 [US2] Implement PUT /api/v1/settings endpoint in src/api/settings.py per api-contract.json
- [x] T051 [US2] Add validation in src/services/settings_service.py for default_model, default_lora_list format

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently - settings persist and apply to future generations

---

## Phase 5: User Story 3 - スレッド内での反復改善 (Priority: P1)

**Goal**: ユーザーが画像生成結果のスレッドに追加指示を返信すると、エージェントが前回の設定を復元し、追加指示の差分だけを更新して新しい画像を生成する。

**Independent Test**: 最初の画像生成後、スレッドに「もっと明るく、笑顔にして」と返信し、エージェントが前回のプロンプトと設定を保持したまま、明るさと表情の指示だけを反映した新しい画像を生成することを確認できる。

### Implementation for User Story 3

- [ ] T052 [P] [US3] Create ThreadContext service in src/services/thread_service.py with CRUD operations (get, create, update)
- [ ] T053 [P] [US3] Implement thread message listener in src/services/discord_bot.py to detect replies in generation threads
- [ ] T054 [US3] Add ThreadContext creation logic in src/services/queue_manager.py after first image generation
- [ ] T055 [US3] Implement context restoration in src/services/prompt_agent.py to load latest_metadata from ThreadContext
- [ ] T056 [US3] Add differential prompt merging in src/services/prompt_agent.py to combine previous prompt + new instruction
- [ ] T057 [US3] Update queue_manager to save updated metadata to ThreadContext after each generation
- [ ] T058 [US3] Add generation_history tracking in src/services/thread_service.py to append request_ids
- [ ] T059 [US3] Implement /reset command in src/services/discord_bot.py to clear ThreadContext for a thread
- [ ] T060 [US3] Implement GET /api/v1/threads/{thread_id}/context endpoint in src/api/context.py per api-contract.json
- [ ] T061 [US3] Add context-aware error messages in src/services/discord_bot.py when ThreadContext is missing

**Checkpoint**: All User Stories 1, 2, and 3 should now be independently functional - iterative refinement works in threads

---

## Phase 6: User Story 4 - Webリサーチによる設定最適化 (Priority: P3)

**Goal**: ユーザーがテーマや目的を指定すると、エージェントがWeb上から最新のベストプラクティス（プロンプトテクニック、推奨設定、人気のLoRA等）を自動的に収集し、要約して画像生成に反映する。

**Independent Test**: 「アニメスタイルの風景画を生成したい」と指示し、エージェントがアニメスタイル風景画に適したプロンプトテクニックやLoRAを自動的にWebから収集し、適用した結果を生成することを確認できる。

### Implementation for User Story 4

- [ ] T062 [P] [US4] Create Google Search API client in src/services/web_research.py with httpx, API key from settings
- [ ] T063 [P] [US4] Implement search query builder in src/services/web_research.py to construct queries from user theme
- [ ] T064 [P] [US4] Add result caching in src/services/web_research.py using SQLite cache table with TTL
- [ ] T065 [US4] Implement best practice extraction in src/services/web_research.py using LLM to summarize search results
- [ ] T066 [US4] Add web_research flag handling in src/services/discord_bot.py /generate command (optional parameter)
- [ ] T067 [US4] Integrate web research into prompt generation in src/services/prompt_agent.py when flag is true
- [ ] T068 [US4] Add research summary posting in src/services/discord_bot.py to include summary in thread
- [ ] T069 [US4] Implement rate limiting in src/services/web_research.py with exponential backoff for Google API
- [ ] T070 [US4] Add "リサーチなしで生成" detection in src/services/discord_bot.py to skip web research

**Checkpoint**: All user stories should now be independently functional - web research enhances generations when enabled

---

## Phase 7: LoRA Management & Additional Features

**Purpose**: LoRA metadata management and supporting features

- [ ] T071 [P] Create LoRA scanning service in src/services/lora_service.py to scan local LoRA directory and populate LoRAMetadata
- [ ] T072 [P] Implement SHA256 hash calculation in src/services/lora_service.py for file_hash field
- [ ] T073 [P] Create /lora list command in src/services/discord_bot.py to display available LoRAs with descriptions
- [ ] T074 [P] Implement GET /api/v1/loras endpoint in src/api/lora.py per api-contract.json
- [ ] T075 Add LoRA availability check in src/services/prompt_agent.py before generation
- [ ] T076 Add LoRA suggestion logic in src/services/prompt_agent.py when requested LoRA is missing
- [ ] T077 Implement image compression in src/services/discord_bot.py for files exceeding Discord size limit

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T078 [P] Add comprehensive docstrings to all modules in src/ following Google style
- [ ] T079 [P] Create deployment Dockerfile with multi-stage build for production
- [ ] T080 [P] Create docker-compose.yml with bot, Automatic1111, Ollama services
- [ ] T081 [P] Document environment variables in docs/environment.md
- [ ] T082 [P] Create monitoring setup in docs/monitoring.md with Prometheus metrics endpoints
- [ ] T083 Add Prometheus metrics exposition in src/main.py using prometheus_client (queue length, latency, error rate)
- [ ] T084 Add structured logging with request IDs in src/services/queue_manager.py
- [ ] T085 Implement graceful shutdown in src/bot.py and src/main.py for queue completion
- [ ] T086 Add retry logic with exponential backoff in src/services/sd_client.py for transient errors
- [ ] T087 Run Black formatter on all source files: black src/ tests/
- [ ] T088 Run Ruff linter and fix issues: ruff check --fix src/ tests/
- [ ] T089 Validate quickstart.md by following all setup steps in fresh environment
- [ ] T090 Create backup/restore documentation in docs/backup.md for database and images
- [ ] T091 Add security hardening documentation in docs/security.md for secrets management
- [ ] T092 [P] Create GitHub Actions workflow .github/workflows/lint-and-format.yml with Ruff and Black execution
- [ ] T093 [P] Create GitHub Actions workflow .github/workflows/test.yml for unittest execution with coverage reporting
- [ ] T094 [P] Create GitHub Actions workflow .github/workflows/merge-gate.yml to block merges on CI failures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can proceed in parallel if staffed
  - Or sequentially in priority order: US1 (P1) → US3 (P1) → US2 (P2) → US4 (P3)
- **LoRA Management (Phase 7)**: Depends on US1 completion (generation workflow established)
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Integrates with US1 but independently testable
- **User Story 3 (P1)**: Can start after Foundational (Phase 2) - Integrates with US1 but independently testable
- **User Story 4 (P3)**: Can start after Foundational (Phase 2) - Integrates with US1 but independently testable

### Within Each User Story

- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: Foundational Phase

```bash
# After T009-T014 complete, launch all models in parallel:
Task T015: "Create GenerationRequest model in src/models/generation.py"
Task T016: "Create GenerationMetadata model in src/models/generation.py"
Task T017: "Create GeneratedImage model in src/models/generation.py"
Task T018: "Create GlobalSettings model in src/models/settings.py"
Task T019: "Create ThreadContext model in src/models/settings.py"
Task T020: "Create LoRAMetadata model in src/models/lora.py"
Task T021: "Create QueuedTask model in src/models/lora.py"
```

---

## Parallel Example: User Story 1

```bash
# After foundational phase, launch independent US1 components:
Task T025: "Create Discord bot client in src/services/discord_bot.py"
Task T027: "Create Ollama LLM client wrapper in src/services/prompt_agent.py"
Task T028: "Create Stable Diffusion API client in src/services/sd_client.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (基本画像生成)
4. Complete Phase 5: User Story 3 (反復改善) - This is also P1 priority
5. **STOP and VALIDATE**: Test US1 + US3 together independently
6. Deploy/demo if ready - This provides core value: generate images + iterative refinement

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 3 → Test independently → Deploy/Demo (反復機能追加)
4. Add User Story 2 → Test independently → Deploy/Demo (設定管理追加)
5. Add User Story 4 → Test independently → Deploy/Demo (Webリサーチ追加)
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Discord + 基本生成)
   - Developer B: User Story 2 (設定管理)
   - Developer C: User Story 3 (スレッド反復)
   - Developer D: User Story 4 (Webリサーチ)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies - can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All datetime fields use UTC timezone
- PRAGMA foreign_keys = ON must be set for SQLite
- Environment variables loaded via pydantic BaseSettings
- Discord rate limits must be respected (discord.py handles this)
- Image storage path must be created before first generation
- Tests are NOT included as they were not requested in specification
