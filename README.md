# UIUX_Quamtumy / Doctor Canvas

理系研究を**マンガの文法**で届けるプロトタイプ。**フロントは単一 `index.html`（React CDN）**、API は **`backend/`（Rust / Axum）**。

## クイックリンク

| ドキュメント | 内容 |
|--------------|------|
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | 本番運用・障害切り分け |
| [docs/STRIPE.md](docs/STRIPE.md) | 決済（Stripe）ロードマップ |
| [docs/JWT-TOKENS.md](docs/JWT-TOKENS.md) | トークン強化ロードマップ |
| [docs/PAPER_TO_MANGA_AI.md](docs/PAPER_TO_MANGA_AI.md) | 論文→漫画 AI に必要なもの |
| [docs/CARGO-FILE-LOCK.md](docs/CARGO-FILE-LOCK.md) | `Blocking waiting for file lock` の対処 |
| [docs/ORCHESTRATOR.md](docs/ORCHESTRATOR.md) | Architect/Coder/Reviewer 自律ループの設計 |
| [tools/ai-orchestrator/](tools/ai-orchestrator/) | Python オーケストレーター（Rust 生成） |
| [backend/README.md](backend/README.md) | API 起動・Fly.io・環境変数 |

## 本番構成（例）

- **フロント:** Vercel（静的）
- **API:** Fly.io（Docker）
- **DB:** Neon（PostgreSQL）

フロントのログイン画面で **API 接続先**（Fly の `https://...`）を保存すると、登録・ログイン・進捗同期がその API に向きます。

## 論文→ネーム案 API

- `POST /api/ai/paper-outline` — 本文テキストからネーム案（`OPENAI_API_KEY` なしならモック）。
- トップページの「お試し」から呼び出し可能。

## 創業計画

- [創業計画書_Doctor_Canvas_草案.md](創業計画書_Doctor_Canvas_草案.md)（公庫用草案 + 技術メモ）
