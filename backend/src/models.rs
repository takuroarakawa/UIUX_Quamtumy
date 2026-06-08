//! リクエスト・レスポンス用の型定義

use serde::{Deserialize, Serialize};
use uuid::Uuid;

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
    /// ログイン成功時のみ。`JWT_ACCESS_TTL_SECS` に一致。
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expires_in_secs: Option<u64>,
}

/// 作品進捗（最後のスプレッド位置）
#[derive(Debug, Deserialize)]
pub struct WorkProgressUpdateRequest {
    pub last_spread_index: i32,
}

#[derive(Debug, Serialize)]
pub struct WorkProgressResponse {
    pub ok: bool,
    pub work_key: String,
    pub last_spread_index: i32,
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

/// POST /api/ai/paper-outline — 論文テキストから漫画ネーム案（MVP）
#[derive(Debug, Deserialize)]
pub struct PaperOutlineRequest {
    pub text: String,
    pub title: Option<String>,
}

/// 漫画キャラクター（C1/C2 ステージで生成）
#[derive(Debug, Serialize, serde::Deserialize, Clone, Default)]
pub struct MangaCharacter {
    pub name: String,
    pub role: String,
    pub description: String,
}

#[derive(Debug, Serialize)]
pub struct PaperOutlineResponse {
    pub ok: bool,
    pub message: String,
    pub source: String,
    pub outline_markdown: String,
    pub panel_beats: Vec<String>,
    /// 漫画テーマ一行（C1）
    #[serde(skip_serializing_if = "Option::is_none")]
    pub theme_line: Option<String>,
    /// 登場キャラクター（C2）
    #[serde(skip_serializing_if = "Vec::is_empty", default)]
    pub characters: Vec<MangaCharacter>,
    /// 粗筋3幕（C2）
    #[serde(skip_serializing_if = "Option::is_none")]
    pub synopsis: Option<String>,
    /// 使用した漫画トーン
    #[serde(skip_serializing_if = "Option::is_none")]
    pub manga_tone: Option<String>,
}

/// POST /api/checkout/session — Stripe Checkout（要ログイン）
#[derive(Debug, Deserialize)]
pub struct CheckoutSessionRequest {
    pub artwork_id: Uuid,
}

#[derive(Debug, Serialize)]
pub struct CheckoutSessionResponse {
    pub ok: bool,
    pub message: String,
    pub checkout_url: Option<String>,
    pub session_id: Option<String>,
}

/// POST /api/ai/pdf-text — multipart file=PDF
#[derive(Debug, Serialize)]
pub struct PdfTextResponse {
    pub ok: bool,
    pub message: String,
    pub text: String,
    pub truncated: bool,
}

// ── コミュニティ ──────────────────────────────────────────────

/// GET /api/works/:work_key/comments — コメント一覧
#[derive(Debug, Serialize)]
pub struct CommentItem {
    pub id: String,
    pub user_id: String,
    pub display_name: String,
    pub body: String,
    pub created_at: String,
}

#[derive(Debug, Serialize)]
pub struct CommentsResponse {
    pub ok: bool,
    pub comments: Vec<CommentItem>,
}

/// POST /api/works/:work_key/comments — コメント投稿
#[derive(Debug, Deserialize)]
pub struct PostCommentRequest {
    pub body: String,
}

#[derive(Debug, Serialize)]
pub struct PostCommentResponse {
    pub ok: bool,
    pub id: String,
}

/// POST /api/works/:work_key/favorite — お気に入りトグル
#[derive(Debug, Serialize)]
pub struct FavoriteResponse {
    pub ok: bool,
    pub favorited: bool,
}

/// GET /api/users/me/favorites — お気に入り一覧
#[derive(Debug, Serialize)]
pub struct FavoriteItem {
    pub work_key: String,
    pub created_at: String,
}

#[derive(Debug, Serialize)]
pub struct FavoritesListResponse {
    pub ok: bool,
    pub favorites: Vec<FavoriteItem>,
}

/// GET /api/users/me/dashboard — 読書サマリー
#[derive(Debug, Serialize)]
pub struct DashboardProgressItem {
    pub work_key: String,
    pub last_spread_index: i32,
    pub updated_at: String,
}

#[derive(Debug, Serialize)]
pub struct DashboardResponse {
    pub ok: bool,
    pub progress: Vec<DashboardProgressItem>,
    pub favorites: Vec<FavoriteItem>,
    pub total_works_read: i64,
    pub total_favorites: i64,
}

// ── 著者・公開カタログ（artworks） ────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct CreateArtworkRequest {
    pub title: String,
    pub description: Option<String>,
    pub doi: Option<String>,
    pub thumbnail_url: Option<String>,
    #[serde(default)]
    pub price: Option<i64>,
    pub content_json: Option<serde_json::Value>,
}

#[derive(Debug, Deserialize)]
pub struct PatchArtworkRequest {
    pub title: Option<String>,
    pub description: Option<String>,
    pub doi: Option<String>,
    pub thumbnail_url: Option<String>,
    pub price: Option<i64>,
    pub content_json: Option<serde_json::Value>,
    pub is_published: Option<bool>,
}

/// カタログ・スタジオ共通の作品表現（フロントは content_json.pages で画像URLを取得）
#[derive(Debug, Serialize)]
pub struct CatalogWorkSummary {
    pub id: String,
    pub title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    pub doi: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub thumbnail_url: Option<String>,
    pub research_field: String,
    pub category: String,
    pub academic_major: String,
    pub academic_minor: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cover_image_url: Option<String>,
    pub price: i64,
    pub is_published: bool,
    pub content_json: serde_json::Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub created_at: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct ArtworkDetailResponse {
    pub ok: bool,
    pub artwork: CatalogWorkSummary,
}

#[derive(Debug, Serialize)]
pub struct CatalogListResponse {
    pub ok: bool,
    pub items: Vec<CatalogWorkSummary>,
}

#[derive(Debug, Serialize)]
pub struct ArtworkMineResponse {
    pub ok: bool,
    pub items: Vec<CatalogWorkSummary>,
}

// ── AI パイプライン Jobs ───────────────────────────────────────────

/// POST /api/ai/ingest — PDF or テキストを受け取りジョブを作成
#[derive(Debug, Deserialize)]
pub struct IngestRequest {
    /// 貼り付けテキスト（`input_source = "text_paste"` の場合）
    pub text: Option<String>,
    pub title: Option<String>,
    pub doi: Option<String>,
    /// 漫画化トーン: "少年マンガ" | "SF" | "社会派" | "ホラー" | "恋愛"
    #[serde(default)]
    pub manga_tone: Option<String>,
}

/// POST /api/ai/ingest レスポンス — job_id を即返す
#[derive(Debug, Serialize)]
pub struct IngestResponse {
    pub ok: bool,
    pub job_id: Uuid,
    pub message: String,
}

/// ai_jobs テーブルの行表現（DB 読み取り用）
#[derive(Debug, sqlx::FromRow)]
pub struct AiJob {
    pub id: Uuid,
    pub user_id: Option<Uuid>,
    pub input_source: String,
    pub input_ref: Option<String>,
    pub input_text_hash: Option<String>,
    pub paper_title: Option<String>,
    pub doi: Option<String>,
    pub status: String,
    pub current_stage: Option<String>,
    pub retry_count: i16,
    pub error_message: Option<String>,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub updated_at: chrono::DateTime<chrono::Utc>,
    pub started_at: Option<chrono::DateTime<chrono::Utc>>,
    pub completed_at: Option<chrono::DateTime<chrono::Utc>>,
}

/// ai_artifacts テーブルの行表現（DB 読み取り用）
#[derive(Debug, sqlx::FromRow)]
pub struct AiArtifact {
    pub id: Uuid,
    pub job_id: Uuid,
    pub stage: String,
    pub artifact_type: String,
    pub artifact_inline: Option<serde_json::Value>,
    pub artifact_key: Option<String>,
    pub size_bytes: Option<i64>,
    pub schema_version: String,
    pub model_used: Option<String>,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

/// GET /api/ai/jobs/:id — ポーリング用レスポンス
#[derive(Debug, Serialize)]
pub struct JobStatusResponse {
    pub ok: bool,
    pub job_id: Uuid,
    pub status: String,
    /// 現在処理中のステージ（A1_extract … C3_name_generate）
    #[serde(skip_serializing_if = "Option::is_none")]
    pub current_stage: Option<String>,
    /// エラー時のメッセージ
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error_message: Option<String>,
    /// 完了時: 最終 MangaNameStory（インライン成果物）
    #[serde(skip_serializing_if = "Option::is_none")]
    pub story_json: Option<serde_json::Value>,
    /// 完了時: Object Store キー（story_json が None の場合に使う）
    #[serde(skip_serializing_if = "Option::is_none")]
    pub story_key: Option<String>,
    /// 利用した LLM プロバイダ + モデル名
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model_used: Option<String>,
}
