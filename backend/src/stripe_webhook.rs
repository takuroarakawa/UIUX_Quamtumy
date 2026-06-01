//! Stripe Webhook — `checkout.session.completed` で `artwork_purchases.status` を `paid` に更新
//!
//! 署名検証: <https://stripe.com/docs/webhooks/signatures>

use axum::{
    body::Bytes,
    extract::State,
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
};
use hmac::{Hmac, Mac};
use sha2::Sha256;
use subtle::ConstantTimeEq;

use crate::AppState;

type HmacSha256 = Hmac<Sha256>;

/// `Stripe-Signature` を検証（`t` と `v1` を使用）
fn verify_stripe_signature(payload: &str, sig_header: &str, secret: &str) -> bool {
    let mut timestamp: Option<&str> = None;
    let mut v1_sigs: Vec<&str> = Vec::new();
    for part in sig_header.split(',') {
        let part = part.trim();
        let mut kv = part.splitn(2, '=');
        let k = kv.next().unwrap_or("").trim();
        let v = kv.next().unwrap_or("").trim();
        match k {
            "t" => timestamp = Some(v),
            "v1" => v1_sigs.push(v),
            _ => {}
        }
    }
    let Some(ts) = timestamp else {
        return false;
    };
    // リプレイ対策: 約5分より古いタイムスタンプは拒否
    if let Ok(t) = ts.parse::<i64>() {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0);
        if (now - t).abs() > 600 {
            tracing::warn!("stripe webhook timestamp skew too large");
            return false;
        }
    }
    let signed_payload = format!("{ts}.{payload}");
    let mut mac = match HmacSha256::new_from_slice(secret.as_bytes()) {
        Ok(m) => m,
        Err(_) => return false,
    };
    mac.update(signed_payload.as_bytes());
    let expected = mac.finalize().into_bytes();
    v1_sigs.iter().any(|sig_hex| {
        let Ok(sig_bytes) = hex::decode(sig_hex) else {
            return false;
        };
        expected.as_slice().ct_eq(sig_bytes.as_slice()).into()
    })
}

/// POST /api/webhooks/stripe — **生ボディ**で署名検証（JSON パースの前に raw が必要）
pub async fn stripe_webhook(
    State(state): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> impl IntoResponse {
    let secret = match std::env::var("STRIPE_WEBHOOK_SECRET") {
        Ok(s) if !s.trim().is_empty() => s,
        _ => {
            tracing::error!("STRIPE_WEBHOOK_SECRET が未設定です");
            return StatusCode::SERVICE_UNAVAILABLE;
        }
    };
    let sig_header = match headers.get("stripe-signature").and_then(|h| h.to_str().ok()) {
        Some(s) => s,
        None => {
            tracing::warn!("stripe webhook: Stripe-Signature なし");
            return StatusCode::BAD_REQUEST;
        }
    };
    let payload = match std::str::from_utf8(&body) {
        Ok(p) => p,
        Err(_) => return StatusCode::BAD_REQUEST,
    };
    if !verify_stripe_signature(payload, sig_header, &secret) {
        tracing::warn!("stripe webhook: 署名検証失敗");
        return StatusCode::BAD_REQUEST;
    }

    let event: serde_json::Value = match serde_json::from_str(payload) {
        Ok(v) => v,
        Err(e) => {
            tracing::warn!("stripe webhook json: {}", e);
            return StatusCode::BAD_REQUEST;
        }
    };

    let typ = event["type"].as_str().unwrap_or("");
    if typ != "checkout.session.completed" {
        // 他イベントも 200 で応答（Stripe の再送を止める）
        return StatusCode::OK;
    }

    let session = &event["data"]["object"];
    let Some(session_id) = session["id"].as_str() else {
        tracing::warn!("stripe webhook: session.id なし");
        return StatusCode::OK;
    };
    let payment_status = session["payment_status"].as_str().unwrap_or("");
    if payment_status != "paid" {
        tracing::info!(
            "checkout.session.completed だが payment_status={}（無視）",
            payment_status
        );
        return StatusCode::OK;
    }

    let res = sqlx::query(
        r#"
        UPDATE artwork_purchases
        SET status = 'paid', paid_at = NOW()
        WHERE stripe_checkout_session_id = $1 AND status = 'pending'
        "#,
    )
    .bind(session_id)
    .execute(&state.pool)
    .await;

    match res {
        Ok(r) => {
            tracing::info!(
                "stripe webhook: paid 更新 rows={} session={}",
                r.rows_affected(),
                session_id
            );
            StatusCode::OK
        }
        Err(e) => {
            tracing::error!("stripe webhook db: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        }
    }
}
