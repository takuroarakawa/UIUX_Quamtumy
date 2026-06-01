-- ─────────────────────────────────────────────────────────────────────────────
-- AI Pipeline Jobs（Dr. CANVAS 論文→ネーム 非同期パイプライン）
--
-- ステージ命名規則（stage 列）:
--   A1_extract        PDF→テキスト抽出
--   A2_normalize      改行・エンコ正規化
--   B1_segment        セクション・見出し検出
--   B2_chunk          トークン上限チャンク分割
--   B3_summarize      Map-Reduce 要約
--   C1_logic_map      論証構造（問題・ギャップ・結果）抽出
--   C2_narrative_plan 起承転結プラン生成
--   C3_name_generate  MangaNameStory JSON 生成
-- ─────────────────────────────────────────────────────────────────────────────

-- ─────────────────────────────────────────────────────────────────────────────
-- ai_jobs: ジョブのライフサイクル管理
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_jobs (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    -- user_id は NULL 可（非ログインの「お試し」を受け入れる MVP 方針）
    -- 将来はクォータ集計の基点になる
    user_id          UUID         REFERENCES users(id) ON DELETE SET NULL,

    -- ─── 入力メタ ───────────────────────────────────────────────────────────
    input_source     VARCHAR(32)  NOT NULL DEFAULT 'text_paste'
                     CHECK (input_source IN ('pdf_upload', 'text_paste')),
    -- pdf_upload 時: Object Store の参照キー（例: "jobs/{id}/raw.pdf"）
    input_ref        TEXT,
    -- text_paste 時: 貼り付けテキスト本文（上限はアプリ層で 80k 文字管理）
    input_text       TEXT,
    -- 重複排除・キャッシュ ヒット判定用 SHA-256
    input_text_hash  CHAR(64),
    -- 論文タイトル（任意。LLM プロンプト品質向上に利用）
    paper_title      TEXT,
    -- DOI（任意。著作権・引用追跡の基点）
    doi              VARCHAR(256),

    -- ─── ライフサイクル ───────────────────────────────────────────────────
    status           VARCHAR(32)  NOT NULL DEFAULT 'pending'
                     CHECK (status IN (
                         'pending',    -- キュー待ち
                         'running',    -- ワーカー処理中
                         'completed',  -- 全ステージ完了
                         'failed',     -- 復帰不能エラー
                         'cancelled'   -- ユーザー or 管理者によるキャンセル
                     )),
    -- 現在処理中のステージ名（UI の進捗バーに使う）
    current_stage    VARCHAR(64),
    -- リトライ回数上限（アプリ層で --max-iterations と連動）
    retry_count      SMALLINT     NOT NULL DEFAULT 0,
    -- 最後のエラー内容（失敗時に記録。PII を含まないよう注意）
    error_message    TEXT,

    -- ─── タイムスタンプ ───────────────────────────────────────────────────
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    started_at       TIMESTAMPTZ,           -- ワーカーが処理を開始した時刻
    completed_at     TIMESTAMPTZ            -- status が completed/failed になった時刻
);

-- ユーザー単位の履歴・クォータ集計用（user_id 非 NULL 行のみ対象）
CREATE INDEX IF NOT EXISTS ai_jobs_user_status_idx
    ON ai_jobs (user_id, status, created_at DESC)
    WHERE user_id IS NOT NULL;

-- ワーカーのポーリング: pending 行を created_at 順に取得
CREATE INDEX IF NOT EXISTS ai_jobs_pending_idx
    ON ai_jobs (created_at ASC)
    WHERE status = 'pending';

-- 重複排除チェック（同一テキストのジョブを探す）
CREATE INDEX IF NOT EXISTS ai_jobs_input_hash_idx
    ON ai_jobs (input_text_hash)
    WHERE input_text_hash IS NOT NULL;


-- ─────────────────────────────────────────────────────────────────────────────
-- ai_artifacts: 各ステージの出力物（追記専用・イミュータブル）
--
-- 1 ジョブ × 1 ステージ = 1 行が基本。
-- リトライ時は行を追加し最新を取得（DELETE は行わない）。
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_artifacts (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id           UUID         NOT NULL REFERENCES ai_jobs(id) ON DELETE CASCADE,

    -- どのステージの産物か（ステージ命名規則に従う）
    stage            VARCHAR(64)  NOT NULL,
    -- 成果物の論理型（extracted_text / paper_brief / manga_name_story 等）
    artifact_type    VARCHAR(64)  NOT NULL,

    -- 小さい成果物（～64 KB 目安）はインライン JSONB に直接保存（MVP で手軽）
    artifact_inline  JSONB,
    -- 大きい成果物は Object Store へ。このキーで取得する（例: "jobs/{job_id}/story.json"）
    artifact_key     TEXT,

    size_bytes       BIGINT,
    -- スキーマの後方互換を追跡するバージョン文字列
    schema_version   VARCHAR(16)  NOT NULL DEFAULT '0.1',
    -- LLM プロバイダ・モデル記録（品質追跡・コスト分析用）
    model_used       VARCHAR(128),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- artifact_inline と artifact_key のどちらか一方は必須
    CONSTRAINT ai_artifacts_storage_check
        CHECK (artifact_inline IS NOT NULL OR artifact_key IS NOT NULL)
);

-- ジョブ + ステージでの絞り込み（最新成果物取得: ORDER BY created_at DESC LIMIT 1）
CREATE INDEX IF NOT EXISTS ai_artifacts_job_stage_idx
    ON ai_artifacts (job_id, stage, created_at DESC);

-- artifact_type 単独検索（分析・デバッグ用）
CREATE INDEX IF NOT EXISTS ai_artifacts_type_idx
    ON ai_artifacts (artifact_type, created_at DESC);


-- ─────────────────────────────────────────────────────────────────────────────
-- ai_job_quota_daily: ユーザー単位の日次クォータ集計（将来の制限に備えて）
--
-- MVP では INSERT + ON CONFLICT DO UPDATE でカウンタを加算する。
-- 課金プランに応じて daily_limit を動的に参照する設計拡張ポイント。
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_job_quota_daily (
    user_id          UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- UTC 日付（CURRENT_DATE で一致させる）
    period_date      DATE         NOT NULL DEFAULT CURRENT_DATE,
    -- この日に作成したジョブ数
    job_count        INTEGER      NOT NULL DEFAULT 0,
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, period_date)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- ヘルパービュー: ジョブの最終ネーム成果物を高速取得
--
-- 利用例:
--   SELECT * FROM v_job_name_result WHERE job_id = $1;
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_job_name_result AS
SELECT DISTINCT ON (a.job_id)
    a.job_id,
    a.id              AS artifact_id,
    a.artifact_inline AS story_json,
    a.artifact_key    AS story_key,
    a.model_used,
    a.schema_version,
    a.created_at      AS generated_at
FROM ai_artifacts a
WHERE a.stage = 'C3_name_generate'
ORDER BY a.job_id, a.created_at DESC;
