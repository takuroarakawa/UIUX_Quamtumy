# Stripe 導入ロードマップ（A: 決済）

DB には既に `artworks` / `artwork_purchases` および `users` の Stripe 関連カラム用マイグレーション（`backend/migrations/20260318000001_artworks_stripe_purchases.sql`）があります。**アプリコードはこれから段階的に接続**します。

## フェーズ 0 — 準備

1. [Stripe Dashboard](https://dashboard.stripe.com/) でアカウント・商品方針を決める（日本向け JPY 等）。
2. **テストモード**の `sk_test_...` / `whsec_...` を取得。
3. Fly（またはローカル）の secrets に保存（平文をリポジトリに入れない）:
   - `STRIPE_SECRET_KEY`
   - `STRIPE_WEBHOOK_SECRET`（エンドポイント作成後）

## 実装済み（MVP）

### `POST /api/checkout/session`

- **認証:** `Authorization: Bearer <JWT>`（ログインユーザーが購入者）
- **Body:** `{ "artwork_id": "<UUID>" }`
- **条件:** `artworks.is_published = true` かつ `price > 0`、かつ購入者 ≠ `author_id`
- **応答:** `{ "ok": true, "checkout_url": "https://checkout.stripe.com/...", "session_id": "cs_..." }`
- **DB:** `artwork_purchases` に `pending` で 1 行挿入（`stripe_checkout_session_id` 付き）

### 必須環境変数（Fly secrets 例）

| 変数 | 説明 |
|------|------|
| `STRIPE_SECRET_KEY` | `sk_test_...` / `sk_live_...` |
| `FRONTEND_ORIGIN` | 成功/キャンセル URL のベースに使用（下記省略時） |
| `STRIPE_SUCCESS_URL` | （任意）フル URL。未設定なら `{FRONTEND_ORIGIN}/?checkout=success` |
| `STRIPE_CANCEL_URL` | （任意）フル URL。未設定なら `{FRONTEND_ORIGIN}/?checkout=cancel` |

```powershell
flyctl secrets set STRIPE_SECRET_KEY="sk_test_..." FRONTEND_ORIGIN="https://uiux-quamtumy.vercel.app"
```

### テスト用に DB に作品を 1 件（例）

`artworks` は `author_id` が必須なので、**既存ユーザーの UUID** を使います。

```sql
INSERT INTO artworks (author_id, title, is_published, price, content_json)
VALUES (
  (SELECT id FROM users ORDER BY created_at LIMIT 1),
  'Stripe テスト作品',
  true,
  500,
  '{}'::jsonb
)
RETURNING id;
```

返った `id` を `artwork_id` に指定して REST で叩く。

## `checkout.session.completed` で paid 更新とは？

**ターミナルに貼る処理ではありません。** 流れは次のとおりです。

1. ユーザーが Stripe Checkout で支払いに成功する。
2. **Stripe のサーバー**が、あなたが登録した **Webhook URL** に対して HTTP `POST` でイベント JSON を送る（イベント種別が `checkout.session.completed`）。
3. あなたの API（`POST /api/webhooks/stripe`）がその JSON を受け取り、**署名 `Stripe-Signature` を検証**したうえで DB を更新する:
   - `artwork_purchases` の `stripe_checkout_session_id` が一致する行の `status` を **`paid`** にし、`paid_at` を入れる。

### あなたが行う設定（ダッシュボード）

1. [Stripe Dashboard](https://dashboard.stripe.com/) → **Developers** → **Webhooks** → **Add endpoint**
2. **Endpoint URL** に本番 API を指定（例）:  
   `https://drcanvas-api.fly.dev/api/webhooks/stripe`
3. イベントで **`checkout.session.completed`** を選択。
4. 表示される **Signing secret**（`whsec_...`）を Fly の secrets に保存:

```powershell
flyctl secrets set STRIPE_WEBHOOK_SECRET="whsec_..."
```

5. `flyctl deploy` で API を再デプロイ。

### ローカル検証（任意）

[Stripe CLI](https://stripe.com/docs/stripe-cli) で:

```bash
stripe listen --forward-to localhost:3000/api/webhooks/stripe
```

表示された `whsec_...` をローカルの `.env` に `STRIPE_WEBHOOK_SECRET` として使う。

---

## 実装済み: `POST /api/webhooks/stripe`

- **生ボディ**で署名検証（JSON にパースする前に raw が必要）。
- 環境変数 **`STRIPE_WEBHOOK_SECRET`** 必須（未設定時は 503）。
- **レート制限（governor）の外**にルートを置き、Stripe の再送を阻害しにくくしてある。

## フェーズ 1 — Checkout（買い切り）の次

1. ~~API: `POST /api/checkout/session`~~（上記で稼働）
2. ~~フロント: 「購入」ボタンでその URL へリダイレクト。~~（`index.html` の `#auth`・ログイン時「購入ページへ」＋戻り `?checkout=success|cancel` のバナー）
3. ~~Webhook: `checkout.session.completed` で `artwork_purchases` を `paid` に更新。~~（上記エンドポイントで実装）

## フェーズ 2 — Connect（作者への分配）

- 研究者ごとに Stripe Connect アカウントを紐づけ（`users.stripe_account_id`）。
- プラットフォーム手数料は `application_fee_amount` 等で設計。

## フェーズ 3 — 投げ銭・サブスク

- 創業計画書の「投げ銭」「月額購読」と整合する料金プランを別途設計。

## セキュリティ

- Webhook は **必ず署名検証**（`STRIPE_WEBHOOK_SECRET`）。
- 金額・`artwork_id` はセッション作成時にサーバー側で再検証（クライアント信頼しない）。

## 参考

- [Stripe Docs — Checkout](https://stripe.com/docs/payments/checkout)
- [Stripe Docs — Webhooks](https://stripe.com/docs/webhooks)
