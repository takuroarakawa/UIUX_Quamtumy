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
    pub access_token: Option<String>,
}

/// 作品（公開取得）用のアセット表現
#[derive(Debug, Serialize)]
pub struct PublicWorkAsset {
    pub kind: String, // "image" | "text"
    pub sort_index: i32,
    pub url: Option<String>, // kind="image"
    pub text: Option<String>, // kind="text"
}

/// 作品（公開取得）用の表現（SEO向けの軽量スキーマ）
#[derive(Debug, Serialize)]
pub struct PublicWork {
    pub id: String,
    pub slug: String,
    pub title: String,
    pub research_field: String,
    pub doi: String,
    pub description: Option<String>,
    pub cover_image_url: Option<String>,
    pub created_at: String,
    pub assets: Vec<PublicWorkAsset>,
}

#[derive(Debug, Serialize)]
pub struct PublicWorkListItem {
    pub id: String,
    pub slug: String,
    pub title: String,
    pub research_field: String,
    pub cover_image_url: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct BillingSummaryResponse {
    pub ok: bool,
    pub message: String,
    pub currency: String,
    pub total_sales_cents: i64,
    pub period_start: Option<String>,
    pub period_end: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct BillingTransactionItem {
    pub id: String,
    pub work_id: Option<String>,
    pub amount_cents: i64,
    pub currency: String,
    pub created_at: String,
}

#[derive(Debug, Serialize)]
pub struct BillingTransactionsResponse {
    pub ok: bool,
    pub message: String,
    pub items: Vec<BillingTransactionItem>,
}
