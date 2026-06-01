-- 作品進捗（最後のスプレッド位置）
-- ログインユーザーごとの再開用（認証前は MVP では guest は localStorage フォールバック）
CREATE TABLE IF NOT EXISTS work_progress (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    work_key TEXT NOT NULL,
    last_spread_index INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, work_key)
);

CREATE INDEX IF NOT EXISTS work_progress_work_key_idx ON work_progress (work_key);

