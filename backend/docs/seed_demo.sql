-- ============================================================
-- Dr.CANVAS デモ用シードデータ
-- 実行方法（ローカル Docker）:
--   docker exec -i <コンテナ名> psql -U quantumy -d quantumy < seed_demo.sql
-- 実行方法（Neon / psql）:
--   psql "$DATABASE_URL" -f seed_demo.sql
-- 実行方法（Fly.io）:
--   flyctl ssh console -C "psql \$DATABASE_URL" → SQLを貼る
-- ============================================================

-- ── Step 1: デモ著者ユーザーを作成（既存なら何もしない） ────────────────────
-- password = "demo1234" の argon2id ハッシュ（Dev 確認用）
-- 本番では /api/register で作ったユーザーの UUID を author_id に使うこと

INSERT INTO users (email, password_hash, display_name)
VALUES (
  'demo-author@drcanvas.app',
  -- argon2id ハッシュ: "demo1234"（アプリが検証できる形式）
  -- ※ 実際の値は `cargo run` 後に /api/register で作るのが確実
  '$argon2id$v=19$m=19456,t=2,p=1$ZGVtb3NhbHQxMjM0NTY$placeholder_hash_replace_me',
  '博士漫画家（デモ）'
)
ON CONFLICT DO NOTHING;

-- ── Step 2: デモ著者の UUID を取得してアートワークを INSERT ─────────────────
-- ローカルで /api/register → /api/login で取ったユーザーの UUID に
-- 置き換えると確実に動く。
DO $$
DECLARE
  v_author_id UUID;
BEGIN

  -- 既存ユーザーを流用（一番最初に登録されたユーザー）
  SELECT id INTO v_author_id FROM users ORDER BY created_at LIMIT 1;

  IF v_author_id IS NULL THEN
    RAISE EXCEPTION '先に /api/register でユーザーを1件作成してください。';
  END IF;

  -- ── 作品1: 量子もつれ（無料・公開） ──────────────────────────────────────
  INSERT INTO artworks (
    author_id, title, description, doi,
    thumbnail_url, content_json, is_published, price
  )
  SELECT
    v_author_id,
    '量子もつれの謎を解け！',
    'EPRパラドックスから始まる、二つの粒子の「不思議な絆」を描く研究マンガ。アインシュタインも驚いた量子の世界へようこそ。',
    '10.1103/PhysRev.47.777',
    'https://picsum.photos/seed/qe01/600/900',
    '{
      "version": 1,
      "pages": [
        {
          "pageNumber": 1,
          "imageUrl": "https://dummyimage.com/600x900/0f1a2e/ffe03a&text=Page+1%0A%E9%87%8F%E5%AD%90%E3%82%82%E3%81%A4%E3%82%8C",
          "caption": "第1コマ: EPRパラドックスの提示"
        },
        {
          "pageNumber": 2,
          "imageUrl": "https://dummyimage.com/600x900/0f1a2e/ffe03a&text=Page+2%0A%E3%83%99%E3%83%AB%E3%81%AE%E4%B8%8D%E7%AD%89%E5%BC%8F",
          "caption": "第2コマ: ベルの不等式の検証"
        },
        {
          "pageNumber": 3,
          "imageUrl": "https://dummyimage.com/600x900/0f1a2e/ffe03a&text=Page+3%0A%E9%87%8F%E5%AD%90%E3%83%86%E3%83%AC%E3%83%9D%E3%83%BC%E3%83%86%E3%83%BC%E3%82%B7%E3%83%A7%E3%83%B3",
          "caption": "第3コマ: 量子テレポーテーションの実現"
        },
        {
          "pageNumber": 4,
          "imageUrl": "https://dummyimage.com/600x900/0f1a2e/ffe03a&text=Page+4%0A%E6%9C%AA%E6%9D%A5%E3%81%B8",
          "caption": "第4コマ: 量子コンピュータへの扉"
        }
      ],
      "meta": {
        "researchField": "量子情報・量子もつれ",
        "category": "SF",
        "academicMajor": "物理学",
        "academicMinor": "量子力学",
        "coverImageUrl": "https://dummyimage.com/600x900/0f1a2e/ffe03a&text=Dr.CANVAS%0A%E9%87%8F%E5%AD%90%E3%82%82%E3%81%A4%E3%82%8C"
      }
    }'::jsonb,
    true,  -- 公開
    0      -- 無料
  WHERE NOT EXISTS (
    SELECT 1 FROM artworks WHERE title = '量子もつれの謎を解け！' AND author_id = v_author_id
  );

  -- ── 作品2: がん細胞の叛乱（有料・公開） ──────────────────────────────────
  INSERT INTO artworks (
    author_id, title, description, doi,
    thumbnail_url, content_json, is_published, price
  )
  SELECT
    v_author_id,
    'がん細胞の叛乱 — 分子生物学最前線',
    'p53遺伝子の守護者が倒れた日、細胞の制御が失われていく。最先端のがん研究を社会派ドラマとして描く。',
    '10.1038/nature12373',
    'https://dummyimage.com/600x900/1a0a0a/ff6b6b&text=Cover',
    '{
      "version": 1,
      "pages": [
        {
          "pageNumber": 1,
          "imageUrl": "https://dummyimage.com/600x900/1a0a0a/ff6b6b&text=Page+1%0Ap53%E3%81%AE%E5%B4%A9%E5%A3%8A",
          "caption": "第1コマ: p53遺伝子の異変"
        },
        {
          "pageNumber": 2,
          "imageUrl": "https://dummyimage.com/600x900/1a0a0a/ff6b6b&text=Page+2%0A%E5%88%B6%E5%BE%A1%E3%81%AE%E5%96%AA%E5%A4%B1",
          "caption": "第2コマ: アポトーシスの阻害"
        },
        {
          "pageNumber": 3,
          "imageUrl": "https://dummyimage.com/600x900/1a0a0a/ff6b6b&text=Page+3%0A%E5%85%8D%E7%96%AB%E3%81%AE%E6%88%A6%E3%81%84",
          "caption": "第3コマ: 免疫細胞との攻防"
        },
        {
          "pageNumber": 4,
          "imageUrl": "https://dummyimage.com/600x900/1a0a0a/ff6b6b&text=Page+4%0A%E5%85%8D%E7%96%AB%E7%99%82%E6%B3%95",
          "caption": "第4コマ: 免疫療法の希望"
        },
        {
          "pageNumber": 5,
          "imageUrl": "https://dummyimage.com/600x900/1a0a0a/ff6b6b&text=Page+5%0A%E6%AC%A1%E3%81%AA%E3%82%8B%E6%88%A6%E3%81%84%E3%81%B8",
          "caption": "第5コマ: 次世代への継承"
        }
      ],
      "meta": {
        "researchField": "分子腫瘍学・がん免疫",
        "category": "社会派",
        "academicMajor": "生物学",
        "academicMinor": "分子生物学",
        "coverImageUrl": "https://dummyimage.com/600x900/1a0a0a/ff6b6b&text=Dr.CANVAS%0Ap53%E5%AE%88%E8%AD%B7%E8%80%85"
      }
    }'::jsonb,
    true,  -- 公開
    500    -- 500円
  WHERE NOT EXISTS (
    SELECT 1 FROM artworks WHERE title = 'がん細胞の叛乱 — 分子生物学最前線' AND author_id = v_author_id
  );

  RAISE NOTICE '✅ デモ作品を挿入しました（author_id: %）', v_author_id;
END;
$$;

-- ── 確認クエリ ─────────────────────────────────────────────────────────────
SELECT
  id,
  title,
  is_published,
  price,
  (content_json->'pages')::text AS pages_count,
  content_json->'meta'->>'researchField' AS research_field
FROM artworks
ORDER BY created_at DESC
LIMIT 10;
