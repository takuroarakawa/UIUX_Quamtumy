-- User: Stripe（顧客・Connect アカウント）
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT,
    ADD COLUMN IF NOT EXISTS stripe_account_id TEXT;

-- 作品（Doctor Canvas コア）
CREATE TABLE IF NOT EXISTS artworks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    author_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title VARCHAR(512) NOT NULL,
    description TEXT,
    doi VARCHAR(256),
    thumbnail_url TEXT,
    content_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_published BOOLEAN NOT NULL DEFAULT false,
    price BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS artworks_author_id_idx ON artworks (author_id);
CREATE INDEX IF NOT EXISTS artworks_published_idx ON artworks (is_published) WHERE is_published = true;

-- 購入・決済セッション整合（webhook で paid へ更新想定）
CREATE TABLE IF NOT EXISTS artwork_purchases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artwork_id UUID NOT NULL REFERENCES artworks (id) ON DELETE CASCADE,
    buyer_user_id UUID REFERENCES users (id) ON DELETE SET NULL,
    stripe_checkout_session_id TEXT UNIQUE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    amount BIGINT NOT NULL,
    currency VARCHAR(8) NOT NULL DEFAULT 'jpy',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    paid_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS artwork_purchases_artwork_buyer_idx
    ON artwork_purchases (artwork_id, buyer_user_id);
CREATE INDEX IF NOT EXISTS artwork_purchases_session_idx ON artwork_purchases (stripe_checkout_session_id);
