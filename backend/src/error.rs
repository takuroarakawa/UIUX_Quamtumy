//! アプリ共通エラー（`Result<impl IntoResponse, AppError>` の Err 側）

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde::Serialize;

#[derive(Debug)]
pub enum AppError {
    BadRequest(String),
    Unauthorized(String),
    Forbidden(String),
    NotFound(String),
    Conflict(String),
    Stripe(String),
    Db(sqlx::Error),
    Internal(String),
}

#[derive(Serialize)]
struct ErrorBody {
    error: String,
    code: &'static str,
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, code, msg) = match &self {
            AppError::BadRequest(m) => (StatusCode::BAD_REQUEST, "bad_request", m.clone()),
            AppError::Unauthorized(m) => (StatusCode::UNAUTHORIZED, "unauthorized", m.clone()),
            AppError::Forbidden(m) => (StatusCode::FORBIDDEN, "forbidden", m.clone()),
            AppError::NotFound(m) => (StatusCode::NOT_FOUND, "not_found", m.clone()),
            AppError::Conflict(m) => (StatusCode::CONFLICT, "conflict", m.clone()),
            AppError::Stripe(m) => (StatusCode::BAD_GATEWAY, "stripe", m.clone()),
            AppError::Db(e) => {
                tracing::error!("db: {}", e);
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "db",
                    "データベースエラー".into(),
                )
            }
            AppError::Internal(m) => {
                tracing::error!("internal: {}", m);
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "internal",
                    "内部エラー".into(),
                )
            }
        };
        (status, Json(ErrorBody { error: msg, code })).into_response()
    }
}

impl From<sqlx::Error> for AppError {
    fn from(e: sqlx::Error) -> Self {
        AppError::Db(e)
    }
}
