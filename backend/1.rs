//! リクエスト・レスポンス用の型定義

use serde::{Deserialize, Serialize};

/// 登録 API のリクエストボディ
#[derive(Debug, Deserialize)]
pub struct RegisterRequest {
    pub email: String,
    pub password: String,
    pub display_name: Option<String>,
}

/// ログイン API のリクエストボディ
#[derive(Debug, Deserialize)]
pub struct LoginRequest {
    pub email: String,
    pub password: String,
}

/// 登録・ログイン成功時の共通レスポンス（JWT 等をのせたい場合はここに追加）
#[derive(Debug, Serialize)]
pub struct AuthResponse {
    pub ok: bool,
    pub message: String,
    pub user_id: Option<String>,
}

//! 認証 API のハンドラー（登録・ログイン）

use axum::{
    extract::State,
    Json,
};
use crate::models::{AuthResponse, LoginRequest, RegisterRequest};
use crate::AppState;

/// POST /api/register — ユーザー登録
pub async fn register(
    State(state): State<AppState>,
    Json(payload): Json<RegisterRequest>,
) -> Json<AuthResponse> {
    // TODO: メール重複チェック → bcrypt でハッシュ → DB に INSERT
    tracing::info!("register: email={}", payload.email);
    let _ = state;
    Json(AuthResponse {
        ok: true,
        message: "登録は未実装です。DB マイグレーションと INSERT を実装してください。".into(),
        user_id: None,
    })
}

/// POST /api/login — ログイン
pub async fn login(
    State(state): State<AppState>,
    Json(payload): Json<LoginRequest>,
) -> Json<AuthResponse> {
    // TODO: メールでユーザー取得 → bcrypt::verify → トークン発行 or セッション
    tracing::info!("login: email={}", payload.email);
    let _ = state;
    Json(AuthResponse {
        ok: true,
        message: "ログインは未実装です。照合と JWT/セッションを実装してください。".into(),
        user_id: None,
    })
}

# データベース（PostgreSQL の例）
DATABASE_URL=postgres://user:password@localhost:5432/quantumy

# SQLite の場合の例
# DATABASE_URL=sqlite://./data.db

# ログレベル（任意）
RUST_LOG=info,tower_http=debug
