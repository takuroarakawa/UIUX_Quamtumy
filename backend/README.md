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

## エンドポイント

| メソッド | パス | 説明 |
|----------|------|------|
| POST | `/api/register` | 登録（メール・パスワード8文字以上） |
| POST | `/api/login` | ログイン |

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
