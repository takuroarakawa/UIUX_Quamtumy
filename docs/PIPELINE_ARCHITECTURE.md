# Dr. CANVAS — Paper → Narrative Pipeline（Architecture v0.1）

> 最終更新: 2026-05-31

## 設計原則

| 原則 | 内容 |
|------|------|
| **単一の正（Canonical IR）** | `MangaNameStory` / `MangaNamePage`（`manga-name-page.schema.json`）を最終形式とする |
| **段階的エンリッチメント** | 各ステージは immutable artifact を残す（`ai_artifacts`）。上書き・削除しない |
| **同期と非同期の分離** | Ingest は同期で受け付け、Reasoning は必ず Job 化する |
| **根拠可能性** | 各コマは `source_text_ref` で論文テキストにトレースバックできる |
| **プロバイダ差し替え** | LLM は環境変数で切り替え（OpenAI / Ollama / 将来の自前モデル）|

---

## レイヤ構成（概観）

```
┌────────────────────────────────────────────────────────────────┐
│  Presentation  (Vercel / index.html)                            │
│  - PDF アップロード / テキスト貼り付け                            │
│  - GET /api/ai/jobs/:id  でポーリング → 進捗バー表示              │
│  - ネーム編集 UI（Human-in-the-loop） 🔌 将来                    │
└──────────────────────────┬─────────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼─────────────────────────────────────┐
│  API Gateway  (Rust / Axum — drcanvas-api)                      │
│  POST /api/ai/ingest          → job_id を即返却                  │
│  GET  /api/ai/jobs/:id        → status + current_stage + artifact│
│  POST /api/ai/jobs/:id/narrate → ネームステージを追加キュー 🔌    │
│  （既存） Auth / Progress / Stripe                               │
└──────────┬───────────────────┬──────────────────────────────────┘
           │                   │
    ┌──────▼──────┐   ┌────────▼────────┐   ┌────────────────────┐
    │ Object Store │   │   Job Queue     │   │   PostgreSQL        │
    │（PDF / JSON）│   │  pg SKIP LOCKED │   │  users, artworks,  │
    │  🔌 S3/Blob  │   │  🔌 Redis/SQS   │   │  ai_jobs,          │
    └─────────────┘   └────────┬────────┘   │  ai_artifacts,     │
                               │            │  ai_job_quota_daily│
                      ┌────────▼────────┐   └────────────────────┘
                      │  Worker Plane   │
                      │  Rust tasks or  │
                      │  Python workers │
                      └────────┬────────┘
                               │
          ┌────────────────────▼─────────────────────────────┐
          │  Pipeline Stages（下表）                           │
          └───────────────────────────────────────────────────┘
```

---

## ステージ詳細

| Stage | 入力 | 処理 | 出力 Artifact | 拡張ポイント |
|-------|------|------|---------------|-------------|
| **A1_extract** | PDF bytes | テキスト抽出 | `extracted_text` | 🔌 pdftotext / pdfium / 商用 OCR |
| **A2_normalize** | raw text | 改行・ハイフン・エンコード正規化 | `normalized_text` | 言語検出 🔌 |
| **B1_segment** | normalized | セクション・見出し・図表キャプション検出 | `document_graph` | 🔌 GROBID / ヒューリスティック |
| **B2_chunk** | graph | トークン上限でチャンク + overlap | `chunks` (JSONL) | チャンク戦略 🔌 |
| **B3_summarize** | chunks | Map-Reduce 要約 | `paper_brief` | LLM 🔌 |
| **C1_logic_map** | brief + chunks | 論証構造（問題・ギャップ・方法・結果・限界）| `argument_map` | ルール + LLM 🔌 |
| **C2_narrative_plan** | argument_map | 起承転結・キャラ役割・ペーシング | `narrative_plan` | Name 哲学テンプレ 🔌 |
| **C3_name_generate** | plan | コマ・セリフ・`source_text_ref` | `MangaNameStory` | OpenAI / Ollama 🔌 |
| **D0_human_edit** | story | 漫画家修正（UI） | `story.vN` | 編集 UI |
| **D1_render** | story | 画像・リーダー | `pages/` | 画像モデル 🔌 |

### Canonical IR（データの「背骨」）

```
PDF
  → extracted_text         (A1)
  → normalized_text        (A2)
  → document_graph         (B1)
  → chunks.jsonl           (B2)
  → paper_brief.json       (B3)
  → argument_map.json      (C1)
  → narrative_plan.json    (C2)
  → MangaNameStory.json    (C3)  ← 唯一の「正」
      └─ pages[]: MangaNamePage
           └─ panels[]: { narrative_beat, visual_description,
                          dialogue, source_text_ref }
```

---

## DB スキーマ概要

マイグレーション: `migrations/20260531000001_ai_pipeline_jobs.sql`

```
ai_jobs
  id               UUID  PK
  user_id          UUID  FK → users（NULL = お試し）
  input_source     VARCHAR  'pdf_upload' | 'text_paste'
  input_ref        TEXT     Object Store キー（PDF 用）
  input_text       TEXT     貼り付けテキスト本文
  input_text_hash  CHAR(64) SHA-256（重複排除）
  paper_title      TEXT
  doi              VARCHAR
  status           VARCHAR  pending → running → completed | failed | cancelled
  current_stage    VARCHAR  A1_extract … C3_name_generate
  retry_count      SMALLINT
  error_message    TEXT
  created_at       TIMESTAMPTZ
  updated_at       TIMESTAMPTZ
  started_at       TIMESTAMPTZ
  completed_at     TIMESTAMPTZ

ai_artifacts
  id               UUID  PK
  job_id           UUID  FK → ai_jobs（CASCADE DELETE）
  stage            VARCHAR  ステージ名
  artifact_type    VARCHAR  extracted_text / manga_name_story 等
  artifact_inline  JSONB    小成果物はここにインライン保存
  artifact_key     TEXT     大成果物は Object Store キー
  size_bytes       BIGINT
  schema_version   VARCHAR
  model_used       VARCHAR  LLM プロバイダ + モデル名
  created_at       TIMESTAMPTZ

ai_job_quota_daily
  user_id          UUID  FK → users
  period_date      DATE
  job_count        INTEGER
  PK (user_id, period_date)

VIEW v_job_name_result
  → job_id ごとの最新 C3_name_generate artifact を高速取得
```

### 主要クエリパターン

```sql
-- ① ワーカー: pending ジョブを1件取得してロック（FOR UPDATE SKIP LOCKED）
SELECT id, input_source, input_ref, input_text, paper_title
FROM ai_jobs
WHERE status = 'pending'
ORDER BY created_at ASC
LIMIT 1
FOR UPDATE SKIP LOCKED;

-- ② UI ポーリング: ジョブ状態 + 最終成果物を1クエリで取得
SELECT j.status, j.current_stage, j.error_message,
       r.story_json, r.story_key, r.model_used
FROM ai_jobs j
LEFT JOIN v_job_name_result r ON r.job_id = j.id
WHERE j.id = $1;

-- ③ クォータ加算（ジョブ作成時に実行）
INSERT INTO ai_job_quota_daily (user_id, period_date, job_count)
VALUES ($1, CURRENT_DATE, 1)
ON CONFLICT (user_id, period_date)
DO UPDATE SET job_count = ai_job_quota_daily.job_count + 1,
              updated_at = NOW();

-- ④ 重複排除チェック（同一テキストの完了ジョブを再利用）
SELECT id FROM ai_jobs
WHERE input_text_hash = $1
  AND status = 'completed'
ORDER BY completed_at DESC
LIMIT 1;
```

---

## 既存コードとのマッピング

| 設計ステージ | 現状 | 次アクション |
|-------------|------|-------------|
| A1_extract | ✅ `POST /api/ai/pdf-text` | Job 化してラップ |
| C3（簡易） | ✅ `POST /api/ai/paper-outline`（4 beats のみ） | Job 化 + 互換ラッパ |
| C3（本格） | ✅ `tools/paper-manga-name/paper_to_name.py` | ワーカーへ統合 |
| Job / Artifact | ✅ **このマイグレーション** | ← 今ここ |
| B1–B3 | ❌ 未実装 | Phase 2 |
| D0 Edit UI | ❌ 未実装 | Phase 3 |

---

## 非同期シーケンス（推奨フロー）

```
User → POST /api/ai/ingest (PDF or text)
         └→ API: Object Store に保存 / input_text を検証
         └→ DB: ai_jobs INSERT (status=pending)
         └→ Queue: enqueue
         └→ User: { job_id }

Worker (polling: FOR UPDATE SKIP LOCKED)
  → A1_extract → ai_artifacts INSERT (stage=A1_extract)
  → A2_normalize → ai_artifacts INSERT
  → B1–B3 (将来)
  → C1–C3 → ai_artifacts INSERT (stage=C3_name_generate)
  → ai_jobs UPDATE (status=completed, completed_at=NOW())

User → GET /api/ai/jobs/:id
         └→ v_job_name_result JOIN で story_json を返却
```

---

## 拡張ロードマップ（Phase 別）

```
Phase 1（2–3週）
  ├─ POST /api/ai/ingest エンドポイント実装
  ├─ ワーカー: A1_extract → C3_name_generate（paper_to_name.py 統合）
  └─ GET /api/ai/jobs/:id ポーリング

Phase 2（4–6週）
  ├─ B1_segment / B2_chunk / B3_summarize の実装
  ├─ Object Store 統合（Vercel Blob or S3）
  └─ クォータ制限 UI

Phase 3（以降）
  ├─ D0 Human-in-the-loop 編集 UI
  ├─ D1 画像生成統合
  └─ 評価セット（ゴールデン PDF + 期待 MangaNameStory）
```
