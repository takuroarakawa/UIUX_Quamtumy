# JWT / セッション強化ロードマップ（B: トークン）

## 現状（MVP）

- ログイン成功時に **JWT（アクセストークン）** を JSON で返却し、フロントが `localStorage` に保存。
- 同じ応答に **`expires_in_secs`**（秒）を載せ、`drcanvas:accessTokenExpMs` に期限の目安を保存（`#auth` で期限が近いとき注意表示）。
- 有効期限は環境変数 **`JWT_ACCESS_TTL_SECS`**（秒）で変更可能。未設定時は **24 時間**（`86400`）。長くしたい場合だけ `JWT_ACCESS_TTL_SECS=604800` などで上書き。
- 進捗 API は `Authorization: Bearer <token>` で認証。

## リスク（意識しておくこと）

- `localStorage` のトークンは **XSS** で読まれた場合に悪用されうる（CSP・入力エスケープ・依存ライブラリの更新が防波堤）。
- アクセストークンだけでは、**ログアウトの即時無効化**が難しい（ブラックリストか短寿命＋リフレッシュが必要）。

## 推奨の次ステップ

### 1. アクセストークン短寿命 + リフレッシュ

- アクセス: 15分〜1時間、`refresh_token`（またはセッション ID）を **HttpOnly + Secure + SameSite** の Cookie に格納。
- API: `POST /api/auth/refresh` でローテーション。

### 2. HttpOnly Cookie に一本化（理想系）

- ログイン応答で `Set-Cookie` のみ（JSON にトークンを載せない）。
- CORS は `credentials: true` と `Access-Control-Allow-Credentials`、オリジンは allowlist のまま厳格に。

### 3. サーバーサイドセッション（Redis / DB）

- トークンより **セッション ID** を Cookie に載せ、サーバーで失効管理。

## 運用

- **全員強制ログアウト**: `JWT_SECRET` をローテーション。
- **期限だけ短くしたい**: `JWT_ACCESS_TTL_SECS=86400`（1日）などを Fly secrets に設定して再デプロイ。
