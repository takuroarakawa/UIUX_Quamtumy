//! コミュニティ機能: コメント・お気に入り・ダッシュボード

use axum::{
    extract::{Path, State},
    http::HeaderMap,
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use uuid::Uuid;

use crate::error::AppError;
use crate::handlers::user_id_from_auth;
use crate::models::{
    CommentItem, CommentsResponse, DashboardProgressItem, DashboardResponse, FavoriteItem,
    FavoriteResponse, FavoritesListResponse, PostCommentRequest, PostCommentResponse,
};
use crate::AppState;

/// GET /api/works/:work_key/comments — 直近50件（認証不要）
pub async fn get_comments(
    State(state): State<AppState>,
    Path(work_key): Path<String>,
) -> Result<impl IntoResponse, AppError> {
    let rows: Vec<(Uuid, Uuid, Option<String>, String, chrono::DateTime<chrono::Utc>)> =
        sqlx::query_as(
            r#"
            SELECT c.id, c.user_id, u.display_name, c.body, c.created_at
            FROM work_comments c
            JOIN users u ON u.id = c.user_id
            WHERE c.work_key = $1
            ORDER BY c.created_at DESC
            LIMIT 50
            "#,
        )
        .bind(&work_key)
        .fetch_all(&state.pool)
        .await?;

    let comments = rows
        .into_iter()
        .map(|(id, user_id, display_name, body, created_at)| CommentItem {
            id: id.to_string(),
            user_id: user_id.to_string(),
            display_name: display_name.unwrap_or_else(|| "Anonymous".into()),
            body,
            created_at: created_at.to_rfc3339(),
        })
        .collect();

    Ok(Json(CommentsResponse { ok: true, comments }))
}

/// POST /api/works/:work_key/comments — コメント投稿（要認証）
pub async fn post_comment(
    State(state): State<AppState>,
    Path(work_key): Path<String>,
    headers: HeaderMap,
    Json(payload): Json<PostCommentRequest>,
) -> Result<impl IntoResponse, AppError> {
    let user_id = user_id_from_auth(&headers)?;

    let body = payload.body.trim().to_string();
    if body.is_empty() {
        return Err(AppError::BadRequest("コメント本文を入力してください。".into()));
    }
    if body.chars().count() > 500 {
        return Err(AppError::BadRequest(
            "コメントは500文字以内で入力してください。".into(),
        ));
    }

    let id: Uuid = sqlx::query_scalar(
        r#"
        INSERT INTO work_comments (work_key, user_id, body)
        VALUES ($1, $2, $3)
        RETURNING id
        "#,
    )
    .bind(&work_key)
    .bind(user_id)
    .bind(&body)
    .fetch_one(&state.pool)
    .await?;

    Ok((
        StatusCode::CREATED,
        Json(PostCommentResponse {
            ok: true,
            id: id.to_string(),
        }),
    ))
}

/// POST /api/works/:work_key/favorite — お気に入りトグル（要認証）
pub async fn toggle_favorite(
    State(state): State<AppState>,
    Path(work_key): Path<String>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    let user_id = user_id_from_auth(&headers)?;

    // 既存チェック
    let exists: bool = sqlx::query_scalar(
        "SELECT EXISTS(SELECT 1 FROM work_favorites WHERE user_id = $1 AND work_key = $2)",
    )
    .bind(user_id)
    .bind(&work_key)
    .fetch_one(&state.pool)
    .await?;

    if exists {
        sqlx::query("DELETE FROM work_favorites WHERE user_id = $1 AND work_key = $2")
            .bind(user_id)
            .bind(&work_key)
            .execute(&state.pool)
            .await?;
        Ok(Json(FavoriteResponse {
            ok: true,
            favorited: false,
        }))
    } else {
        sqlx::query(
            "INSERT INTO work_favorites (user_id, work_key) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        )
        .bind(user_id)
        .bind(&work_key)
        .execute(&state.pool)
        .await?;
        Ok(Json(FavoriteResponse {
            ok: true,
            favorited: true,
        }))
    }
}

/// GET /api/works/:work_key/favorite — お気に入り状態確認（要認証）
pub async fn get_favorite_status(
    State(state): State<AppState>,
    Path(work_key): Path<String>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    let user_id = user_id_from_auth(&headers)?;

    let favorited: bool = sqlx::query_scalar(
        "SELECT EXISTS(SELECT 1 FROM work_favorites WHERE user_id = $1 AND work_key = $2)",
    )
    .bind(user_id)
    .bind(&work_key)
    .fetch_one(&state.pool)
    .await?;

    Ok(Json(FavoriteResponse { ok: true, favorited }))
}

/// GET /api/users/me/favorites — お気に入り一覧（要認証）
pub async fn get_my_favorites(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    let user_id = user_id_from_auth(&headers)?;

    let rows: Vec<(String, chrono::DateTime<chrono::Utc>)> = sqlx::query_as(
        r#"
        SELECT work_key, created_at
        FROM work_favorites
        WHERE user_id = $1
        ORDER BY created_at DESC
        "#,
    )
    .bind(user_id)
    .fetch_all(&state.pool)
    .await?;

    let favorites = rows
        .into_iter()
        .map(|(work_key, created_at)| FavoriteItem {
            work_key,
            created_at: created_at.to_rfc3339(),
        })
        .collect();

    Ok(Json(FavoritesListResponse {
        ok: true,
        favorites,
    }))
}

/// GET /api/users/me/dashboard — 読書サマリー（要認証）
pub async fn get_dashboard(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    let user_id = user_id_from_auth(&headers)?;

    let progress_rows: Vec<(String, i32, chrono::DateTime<chrono::Utc>)> = sqlx::query_as(
        r#"
        SELECT work_key, last_spread_index, updated_at
        FROM work_progress
        WHERE user_id = $1
        ORDER BY updated_at DESC
        "#,
    )
    .bind(user_id)
    .fetch_all(&state.pool)
    .await?;

    let total_works_read = progress_rows.len() as i64;

    let favorite_rows: Vec<(String, chrono::DateTime<chrono::Utc>)> = sqlx::query_as(
        r#"
        SELECT work_key, created_at
        FROM work_favorites
        WHERE user_id = $1
        ORDER BY created_at DESC
        "#,
    )
    .bind(user_id)
    .fetch_all(&state.pool)
    .await?;

    let total_favorites = favorite_rows.len() as i64;

    let progress = progress_rows
        .into_iter()
        .map(|(work_key, last_spread_index, updated_at)| DashboardProgressItem {
            work_key,
            last_spread_index,
            updated_at: updated_at.to_rfc3339(),
        })
        .collect();

    let favorites = favorite_rows
        .into_iter()
        .map(|(work_key, created_at)| FavoriteItem {
            work_key,
            created_at: created_at.to_rfc3339(),
        })
        .collect();

    Ok(Json(DashboardResponse {
        ok: true,
        progress,
        favorites,
        total_works_read,
        total_favorites,
    }))
}
