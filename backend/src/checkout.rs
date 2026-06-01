//! Stripe Checkout セッション作成（要ログイン・作品は DB の `artworks`）

use axum::{extract::State, http::HeaderMap, response::IntoResponse, Json};
use serde::Deserialize;
use uuid::Uuid;

use crate::error::AppError;
use crate::handlers::user_id_from_auth;
use crate::models::{CheckoutSessionRequest, CheckoutSessionResponse};
use crate::AppState;

#[derive(Debug, Deserialize)]
struct StripeCheckoutSessionCreated {
    id: String,
    url: Option<String>,
}

#[derive(Debug, sqlx::FromRow)]
struct ArtworkCheckoutMeta {
    id: Uuid,
    title: String,
    price: i64,
    is_published: bool,
    author_id: Uuid,
}

/// POST /api/checkout/session — `Authorization: Bearer` 必須
pub async fn create_checkout_session(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(payload): Json<CheckoutSessionRequest>,
) -> Result<impl IntoResponse, AppError> {
    let buyer_id = user_id_from_auth(&headers)?;
    let sk = std::env::var("STRIPE_SECRET_KEY")
        .map_err(|_| AppError::Stripe("STRIPE_SECRET_KEY が未設定です".into()))?;
    if sk.trim().is_empty() {
        return Err(AppError::Stripe("STRIPE_SECRET_KEY が空です".into()));
    }

    let meta = sqlx::query_as::<_, ArtworkCheckoutMeta>(
        r#"
        SELECT id, title, price, is_published, author_id
        FROM artworks
        WHERE id = $1
        "#,
    )
    .bind(payload.artwork_id)
    .fetch_optional(&state.pool)
    .await?;

    let Some(meta) = meta else {
        return Err(AppError::NotFound("作品が見つかりません".into()));
    };
    if !meta.is_published {
        return Err(AppError::NotFound("この作品は現在購入できません".into()));
    }
    if meta.price <= 0 {
        return Err(AppError::BadRequest("無料作品です。決済は不要です。".into()));
    }
    if meta.author_id == buyer_id {
        return Err(AppError::Forbidden(
            "自分の作品は購入フローから除外されています（MVP）".into(),
        ));
    }

    let success_url = checkout_success_url()?;
    let cancel_url = checkout_cancel_url()?;

    let title_short: String = meta.title.chars().take(120).collect();
    let unit_amount = meta.price.to_string();
    let cref = format!("{}:{}", meta.id, buyer_id);
    let enc = |s: &str| urlencoding::encode(s).into_owned();
    let body = format!(
        "mode=payment&success_url={}&cancel_url={}&client_reference_id={}\
         &metadata[artwork_id]={}&metadata[buyer_user_id]={}\
         &line_items[0][quantity]=1\
         &line_items[0][price_data][currency]=jpy\
         &line_items[0][price_data][unit_amount]={}\
         &line_items[0][price_data][product_data][name]={}",
        enc(&success_url),
        enc(&cancel_url),
        enc(&cref),
        enc(&meta.id.to_string()),
        enc(&buyer_id.to_string()),
        enc(&unit_amount),
        enc(&title_short),
    );

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(45))
        .build()
        .map_err(|e| AppError::Internal(e.to_string()))?;

    let res = client
        .post("https://api.stripe.com/v1/checkout/sessions")
        .bearer_auth(&sk)
        .header(
            reqwest::header::CONTENT_TYPE,
            "application/x-www-form-urlencoded",
        )
        .body(body)
        .send()
        .await
        .map_err(|e| AppError::Stripe(format!("Stripe 通信失敗: {}", e)))?;

    if !res.status().is_success() {
        let status = res.status();
        let body = res.text().await.unwrap_or_default();
        tracing::warn!("stripe checkout error {}: {}", status, body);
        return Err(AppError::Stripe(
            "Checkout セッションの作成に失敗しました（Stripe の応答をログで確認）".into(),
        ));
    }

    let created: StripeCheckoutSessionCreated = res
        .json()
        .await
        .map_err(|e| AppError::Stripe(format!("Stripe 応答の解析に失敗: {}", e)))?;

    let checkout_url = created
        .url
        .ok_or_else(|| AppError::Stripe("Stripe が checkout URL を返しませんでした".into()))?;

    sqlx::query(
        r#"
        INSERT INTO artwork_purchases (artwork_id, buyer_user_id, stripe_checkout_session_id, status, amount, currency)
        VALUES ($1, $2, $3, 'pending', $4, 'jpy')
        "#,
    )
    .bind(meta.id)
    .bind(buyer_id)
    .bind(&created.id)
    .bind(meta.price)
    .execute(&state.pool)
    .await?;

    Ok(Json(CheckoutSessionResponse {
        ok: true,
        message: "redirect".into(),
        checkout_url: Some(checkout_url),
        session_id: Some(created.id),
    }))
}

fn checkout_success_url() -> Result<String, AppError> {
    if let Ok(u) = std::env::var("STRIPE_SUCCESS_URL") {
        let u = u.trim();
        if !u.is_empty() {
            return Ok(u.to_string());
        }
    }
    let base = std::env::var("FRONTEND_ORIGIN").map_err(|_| {
        AppError::Stripe("STRIPE_SUCCESS_URL または FRONTEND_ORIGIN を設定してください".into())
    })?;
    Ok(format!(
        "{}/?checkout=success",
        base.trim_end_matches('/')
    ))
}

fn checkout_cancel_url() -> Result<String, AppError> {
    if let Ok(u) = std::env::var("STRIPE_CANCEL_URL") {
        let u = u.trim();
        if !u.is_empty() {
            return Ok(u.to_string());
        }
    }
    let base = std::env::var("FRONTEND_ORIGIN").map_err(|_| {
        AppError::Stripe("STRIPE_CANCEL_URL または FRONTEND_ORIGIN を設定してください".into())
    })?;
    Ok(format!(
        "{}/?checkout=cancel",
        base.trim_end_matches('/')
    ))
}
