-- コメント（作品ごと・ログインユーザー）
CREATE TABLE IF NOT EXISTS work_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_key TEXT NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL CHECK (char_length(body) BETWEEN 1 AND 500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS work_comments_work_key_idx ON work_comments (work_key, created_at DESC);

-- お気に入り（作品ごと・ログインユーザー）
CREATE TABLE IF NOT EXISTS work_favorites (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    work_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, work_key)
);

CREATE INDEX IF NOT EXISTS work_favorites_user_id_idx ON work_favorites (user_id, created_at DESC);
