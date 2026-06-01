# 運用メモ（Doctor Canvas / Quantumy）

社内・自分用の**非公開**運用チェックリスト。秘密情報はここに書かず、パスワードマネージャや Fly / Neon のダッシュボードに置く。

## 本番疎通チェックリスト（順番どおり）

1. **DNS / アプリ名** — `flyctl apps list` で実アプリ名を確認する。`fly.toml` の `app =` と一致させ、HTTPS は `https://（アプリ名）.fly.dev`。
2. **生存確認** — デプロイ後に `GET /health` を叩く（認証不要）。例: `curl -sS https://（アプリ名）.fly.dev/health` → JSON で `"status":"ok"`。
3. **シークレット** — `flyctl secrets list` に `DATABASE_URL`・`JWT_SECRET`・`FRONTEND_ORIGIN` があること。Neon URL に `channel_binding=require` が付いていて接続失敗する場合は [backend README](../backend/README.md) のメモどおり末尾を調整。
4. **DB** — `flyctl logs` で起動直後にマイグレーション成功・DB 接続ログが出ること。
5. **フロント** — 本番またはローカル UI の「API 接続先」に **手順 1 と同じ HTTPS のオリジン**（末尾スラッシュなし）を保存し、登録 → ログインまで試す。
6. **CORS** — ブラウザコンソールに CORS エラーが出る場合は `FRONTEND_ORIGIN` が**実際にページを開いている URL のオリジン**（スキーム・ホスト・ポートまで一致）と一致しているか確認する。

手順 2 で失敗し手順 4 で DB エラーが出る場合は、シークレットと Neon のプロジェクト／ブランチを優先して切り分ける。

## 本番の目安構成

| 層 | サービス例 | 役割 |
|----|------------|------|
| フロント | Vercel | 静的 `index.html` |
| API | Fly.io (`drcanvas-api` 等) | Rust / Axum |
| DB | Neon | PostgreSQL |

## Render デプロイ手順（無料・クレジットカード不要）

Render は `backend/render.yaml` があればそのまま使えます。

1. [render.com](https://render.com) でサインアップ（GitHub 連携推奨）
2. **New → Web Service → Connect a repository** でこのリポジトリを選ぶ
3. Root Directory に `backend` を指定（または `backend/render.yaml` が自動検出される）
4. **Environment Variables** を Render ダッシュボードで入力:
   - `DATABASE_URL` — Neon の接続文字列
   - `JWT_SECRET` — 本番用ランダム文字列（下記で生成可）
   - `FRONTEND_ORIGIN` — 例: `https://uiux-quamtumy.vercel.app`
5. **Deploy** → 完了後、`https://drcanvas-api.onrender.com/health` で確認

**JWT_SECRET 生成例（PowerShell）:**
```powershell
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
```

> 注意: 無料プランは **15分アクセスなしでスリープ**します。  
> 初回アクセスは30秒ほど遅延します（許容できない場合は $7/月 の Starter プランへ）。

## Fly.io デプロイ手順（初回・課金登録後）

```powershell
# 1. 課金登録が完了していることを確認
# https://fly.io/dashboard/<org>/billing

cd backend

# 2. アプリ作成（初回のみ）
flyctl apps create drcanvas-api

# 3. 本番 JWT_SECRET を生成して secrets にセット
$jwt = [Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
flyctl secrets set JWT_SECRET="$jwt" `
  DATABASE_URL="<Neon の接続文字列>" `
  FRONTEND_ORIGIN="http://127.0.0.1:5173"   # 本番 Vercel URL に合わせる

# 4. デプロイ
flyctl deploy

# 5. /health で確認
curl -sS https://drcanvas-api.fly.dev/health
# → {"status":"ok","service":"quantumy-api"}
```

## よく使うコマンド（API）

```powershell
cd backend
flyctl status
flyctl logs
flyctl secrets list
```

- **シークレット更新後**は再デプロイが必要な場合があります: `flyctl deploy`
- **JWT を無効化したい**（全員再ログイン）: `JWT_SECRET` を変更して再デプロイ

## フロント側

- ユーザーは **ログイン画面の「API 接続先」** に Fly の HTTPS URL を保存する（`localStorage`）。
- デプロイ後は **ハードリロード** でキャッシュを避ける。

## 障害時の切り分け

1. ブラザコンソールに CORS エラー → `FRONTEND_ORIGIN` と実際のサイト URL が一致しているか
2. `401` → トークン期限切れ・`JWT_SECRET` 変更済み → 再ログイン
3. 進捗だけ失敗 → `DATABASE_URL` / マイグレーション / ログで DB 接続を確認
4. 論文 AI が常にモック → `OPENAI_API_KEY` が Fly secrets に入っているか・課金・レート

## バックアップ

- Neon はスナップショット／ブランチ機能を活用（Neon ドキュメント参照）。
- コードは Git リモート必須。
