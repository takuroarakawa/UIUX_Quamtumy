# Quantumy Auth API

Axum + PostgreSQL（sqlx）で **ユーザー登録・ログイン** を行うバックエンドです。

## 今すぐできること（ビルド待ちの間）

| 作業 | コマンド / 場所 |
|------|----------------|
| DB だけ起動 | `docker compose up -d` |
| API 仕様を眺める | `docs/openapi.yaml` |
| 手動で叩く | `api.http`（REST Client 拡張） |
| マイグレーション SQL | `migrations/` |

## 前提

- Rust（stable, `x86_64-pc-windows-msvc`）+ Visual Studio Build Tools（C++）
- または Docker（PostgreSQL 用）

## セットアップ

```powershell
cd backend
copy .env.example .env
# .env の DATABASE_URL を編集（Docker 利用時は下記と一致させる）

docker compose up -d

# 初回ビルド・起動（マイグレーションは起動時に自動実行）
cargo run
```

**Docker 利用時の `DATABASE_URL` 例:**

```
postgres://quantumy:quantumy_secret@localhost:5432/quantumy
```

## 本番デプロイ（案A: Docker + Fly.io / Render など）

このバックエンドは `backend/Dockerfile` を同梱しているので、Docker対応のPaaSへそのまま載せられます。

### 推奨構成（品質優先）

- DB: Neon（Postgres）
- API: Fly.io（Dockerデプロイ）
- Front: Vercel（静的）

### 必須環境変数（本番）

- `DATABASE_URL`: Postgres（Neon の **Connection string** をそのまま可。`postgresql://` / `postgres://` どちらでも可）
- `JWT_SECRET`: **必ず強いランダム文字列**
- `FRONTEND_ORIGIN`: 例 `https://uiux-quamtumy.vercel.app`

#### Neon の `DATABASE_URL` について

- ダッシュボードの **完全な接続文字列**（パスワード入り）を `flyctl secrets set` にだけ渡す。**チャットや Git には貼らない。**
- 接続に失敗する場合は、URL 末尾の **`&channel_binding=require` を削除**して試す（一部の TLS スタックでは非対応のことがあります）。`sslmode=require` は残してよいです。

#### `JWT_SECRET` の例（PowerShell）

```powershell
# 48バイトを Base64（そのまま1行で fly secrets に渡せる）
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
```

### Fly.io（例）

事前に `flyctl` をインストールしてログインします。

**Windows で `flyctl` が認識されないとき（`Le terme «flyctl» n'est pas reconnu` 等）**

PowerShell を **管理者不要**で開き、公式インストーラを実行:

```powershell
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

完了後、**ターミナルをいったん閉じて開き直す**（PATH が通るまで）。確認: `flyctl version`  
（`fly` コマンドのみ入る環境もあるので、なければ `fly version` も試す。）

1) アプリ作成（初回のみ）

```bash
cd backend
flyctl auth login
flyctl apps create drcanvas-api
```

2) Secrets（本番環境変数）設定

**Bash:**

```bash
flyctl secrets set \
  DATABASE_URL="postgresql://neondb_owner:実パスワード@ep-....neon.tech/neondb?sslmode=require" \
  JWT_SECRET="（上記 PowerShell で生成）" \
  FRONTEND_ORIGIN="https://uiux-quamtumy.vercel.app"
```

**PowerShell（1行・引用符に注意）:**

```powershell
flyctl secrets set DATABASE_URL="postgresql://..." JWT_SECRET="..." FRONTEND_ORIGIN="https://uiux-quamtumy.vercel.app"
```

3) デプロイ

```bash
flyctl deploy
```

4) 疎通確認

```bash
curl -X POST "https://drcanvas-api.fly.dev/api/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"you@example.com\",\"password\":\"password1234\"}"
```

### 例: Docker でローカル起動

```powershell
cd backend
docker build -t drcanvas-api .
docker run --rm -p 3000:3000 `
  -e DATABASE_URL="postgres://quantumy:quantumy_secret@host.docker.internal:5432/quantumy" `
  -e JWT_SECRET="dev_change_me" `
  -e FRONTEND_ORIGIN="http://localhost:3001" `
  drcanvas-api
```

## セキュリティ方針（MVPでも落とさない）

- パスワード: `argon2id`（PHC文字列をDBに保存）
- レート制限: IP単位（`tower_governor`）
- CORS: allowlist（`FRONTEND_ORIGIN` を指定）
- 次のフェーズ:
  - Refresh Token を HttpOnly Cookie（localStorageから卒業）
  - メール検証（登録後に確認リンク）
  - login/register の更なる攻撃対策（より厳密なレート制限、監査ログ）

## エンドポイント

| メソッド | パス | 説明 |
|----------|------|------|
| POST | `/api/register` | 登録（メール・パスワード8文字以上） |
| POST | `/api/login` | ログイン |
| GET | `/api/works/:work_key/progress` | 進捗取得（要Bearer） |
| POST | `/api/works/:work_key/progress` | 進捗保存（要Bearer） |
| POST | `/api/ai/paper-outline` | 論文テキスト→漫画ネーム案（`OPENAI_API_KEY` 任意・未設定はモック） |
| POST | `/api/ai/pdf-text` | PDF→テキスト（multipart `file`、テキストレイヤー付きPDFのみ・最大8MB） |
| POST | `/api/checkout/session` | Stripe Checkout URL 発行（要 Bearer・`{ "artwork_id": "UUID" }`） |
| POST | `/api/webhooks/stripe` | Stripe Webhook（`checkout.session.completed` → `artwork_purchases` を `paid`） |

## プロジェクト構成

```
backend/
├── Cargo.toml
├── docker-compose.yml      # ローカル PostgreSQL
├── api.http                # 手動テスト用
├── docs/openapi.yaml       # API 仕様
├── migrations/             # sqlx マイグレーション
└── src/
    ├── main.rs
    ├── handlers.rs
    └── models.rs
```

## 次の拡張案

- JWT / セッションクッキー
- メール確認（検証リンク）
- レート制限（tower_governor 等）
