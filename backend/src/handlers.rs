//! 認証 API（登録・ログイン）

use axum::{
    extract::State,
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use uuid::Uuid;

use crate::models::{AuthResponse, LoginRequest, RegisterRequest};
use crate::AppState;

fn json_response(status: StatusCode, body: AuthResponse) -> impl IntoResponse {
    (status, Json(body))
}

/// POST /api/register
pub async fn register(
    State(state): State<AppState>,
    Json(payload): Json<RegisterRequest>,
) -> impl IntoResponse {
    let email = payload.email.trim().to_lowercase();
    if email.is_empty() || !email.contains('@') {
        return json_response(
            StatusCode::BAD_REQUEST,
            AuthResponse {
                ok: false,
                message: "有効なメールアドレスを入力してください。".into(),
                user_id: None,
            },
        )
        .into_response();
    }
    if payload.password.len() < 8 {
        return json_response(
            StatusCode::BAD_REQUEST,
            AuthResponse {
                ok: false,
                message: "パスワードは8文字以上にしてください。".into(),
                user_id: None,
            },
        )
        .into_response();
    }

    let password_hash = match bcrypt::hash(&payload.password, bcrypt::DEFAULT_COST) {
        Ok(h) => h,
        Err(e) => {
            tracing::error!("bcrypt hash: {}", e);
            return json_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                AuthResponse {
                    ok: false,
                    message: "サーバーエラーです。".into(),
                    user_id: None,
                },
            )
            .into_response();
        }
    };

    let display_name = payload
        .display_name
        .as_ref()
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string());

    let result = sqlx::query_scalar::<_, Uuid>(
        "INSERT INTO users (email, password_hash, display_name) VALUES ($1, $2, $3) RETURNING id",
    )
    .bind(&email)
    .bind(&password_hash)
    .bind(display_name.as_deref())
    .fetch_one(&state.pool)
    .await;

    match result {
        Ok(id) => json_response(
            StatusCode::CREATED,
            AuthResponse {
                ok: true,
                message: "登録しました。".into(),
                user_id: Some(id.to_string()),
            },
        )
        .into_response(),
        Err(e) => {
            if let sqlx::Error::Database(ref db) = e {
                if db.code().as_deref() == Some("23505") {
                    return json_response(
                        StatusCode::CONFLICT,
                        AuthResponse {
                            ok: false,
                            message: "このメールアドレスは既に登録されています。".into(),
                            user_id: None,
                        },
                    )
                    .into_response();
                }
            }
            tracing::error!("register: {}", e);
            json_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                AuthResponse {
                    ok: false,
                    message: "登録に失敗しました。".into(),
                    user_id: None,
                },
            )
            .into_response()
        }
    }
}

/// POST /api/login
pub async fn login(
    State(state): State<AppState>,
    Json(payload): Json<LoginRequest>,
) -> impl IntoResponse {
    let email = payload.email.trim().to_lowercase();

    let row: Result<Option<(Uuid, String)>, sqlx::Error> = sqlx::query_as(
        "SELECT id, password_hash FROM users WHERE email = $1",
    )
    .bind(&email)
    .fetch_optional(&state.pool)
    .await;

    let row = match row {
        Ok(r) => r,
        Err(e) => {
            tracing::error!("login: {}", e);
            return json_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                AuthResponse {
                    ok: false,
                    message: "サーバーエラーです。".into(),
                    user_id: None,
                },
            )
            .into_response();
        }
    };

    let Some((id, hash)) = row else {
        return json_response(
            StatusCode::UNAUTHORIZED,
            AuthResponse {
                ok: false,
                message: "メールまたはパスワードが正しくありません。".into(),
                user_id: None,
            },
        )
        .into_response();
    };

    let ok = bcrypt::verify(&payload.password, &hash).unwrap_or(false);
    if !ok {
        return json_response(
            StatusCode::UNAUTHORIZED,
            AuthResponse {
                ok: false,
                message: "メールまたはパスワードが正しくありません。".into(),
                user_id: None,
            },
        )
        .into_response();
    }

    json_response(
        StatusCode::OK,
        AuthResponse {
            ok: true,
            message: "ログインに成功しました。".into(),
            user_id: Some(id.to_string()),
        },
    )
    .into_response()
}
