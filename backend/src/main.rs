//! Quantumy Auth API — ユーザー登録・ログイン API のエントリポイント
//!
//! 起動後:
//! - POST /api/register — ユーザー登録
//! - POST /api/login    — ログイン
//! - POST /api/ai/paper-outline — 論文テキスト→ネーム案（OpenAI 任意）
//! - POST /api/ai/pdf-text — PDF アップロード→テキスト抽出
//! - POST /api/checkout/session — Stripe Checkout（要 JWT）
//! - POST /api/webhooks/stripe — Stripe Webhook（`checkout.session.completed` → paid）
//! - GET /health — 生存確認（認証不要・DB 非依存）
//! - GET /api/catalog/works — 公開カタログ
//! - GET /api/catalog/works/:id — 公開作品詳細
//! - POST /api/artworks / PATCH /api/artworks/:id / GET /api/artworks/mine — 著者向け（要 JWT）

use axum::{
    extract::DefaultBodyLimit,
    routing::{get, patch, post},
    Router,
};
use artworks::{
    catalog_get, catalog_list, create_artwork, list_my_artworks, patch_artwork,
};
use community::{get_comments, get_dashboard, get_favorite_status, get_my_favorites, post_comment, toggle_favorite};
use std::net::SocketAddr;
use std::sync::Arc;
use tower_governor::{governor::GovernorConfigBuilder, GovernorLayer};
use tower_http::cors::CorsLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};
use axum::http::{HeaderValue, Method};

mod auth;
mod artworks;
mod checkout;
mod community;
mod error;
mod handlers;
mod models;
mod pdf_upload;
mod stripe_webhook;

/// アプリ全体で共有する状態（DB プール等）
#[derive(Clone)]
pub struct AppState {
    pub pool: sqlx::PgPool,
    // SQLite を使う場合は: pub pool: sqlx::SqlitePool,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // ログ初期化
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info,tower_http=debug".into()),
        ))
        .with(tracing_subscriber::fmt::layer())
        .init();

    // .env を読み込み（DATABASE_URL 等）
    dotenvy::dotenv().ok();

    let database_url = std::env::var("DATABASE_URL")
        .expect("DATABASE_URL を設定してください（例: postgres://user:pass@localhost/quantumy）");

    // PostgreSQL プール（SQLite の場合は sqlx::SqlitePool::connect(&database_url).await?）
    let pool = sqlx::postgres::PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await?;

    tracing::info!("DB 接続済み: {}", database_url.split('@').last().unwrap_or("***"));

    sqlx::migrate!("./migrations")
        .run(&pool)
        .await?;
    tracing::info!("マイグレーション完了");

    let state = AppState { pool };

    // Webhook は Stripe サーバーからの POST のみ（レート制限の外に置く）
    let webhook_router = Router::new()
        .route(
            "/api/webhooks/stripe",
            post(stripe_webhook::stripe_webhook),
        )
        .with_state(state.clone());

    // CORS: FRONTEND_ORIGIN をカンマ区切りで複数指定可能
    // 例: "http://127.0.0.1:5173,http://localhost:5173"
    // ローカルは 127.0.0.1/localhost 両方、本番は https://xxxx.vercel.app のみ
    let cors = {
        use tower_http::cors::AllowOrigin;
        let raw = std::env::var("FRONTEND_ORIGIN").unwrap_or_default();
        let origins: Vec<HeaderValue> = raw
            .split(',')
            .map(|s| s.trim())
            .filter(|s| !s.is_empty())
            .filter_map(|s| s.parse::<HeaderValue>().ok())
            .collect();

        let allow_origin = if origins.is_empty() {
            // FRONTEND_ORIGIN 未設定 → ローカル開発のデフォルト許可
            tracing::warn!("FRONTEND_ORIGIN 未設定: localhost/127.0.0.1:5173 を許可します（本番では必ず設定してください）");
            AllowOrigin::list([
                "http://localhost:5173".parse::<HeaderValue>().unwrap(),
                "http://127.0.0.1:5173".parse::<HeaderValue>().unwrap(),
            ])
        } else {
            AllowOrigin::list(origins)
        };

        CorsLayer::new()
            .allow_origin(allow_origin)
            .allow_methods([Method::GET, Method::POST, Method::PATCH, Method::DELETE, Method::OPTIONS])
            .allow_headers([axum::http::header::AUTHORIZATION, axum::http::header::CONTENT_TYPE])
    };

    // レート制限（IP単位、認証/進捗含め全体に適用）
    let governor_conf = Arc::new(
        GovernorConfigBuilder::default()
            .per_second(5)
            .burst_size(20)
            .finish()
            .expect("governor config"),
    );

    let health_router = Router::new()
        .route("/health", get(handlers::health_check))
        .layer(cors.clone());

    let app = Router::new()
        .merge(health_router)
        .merge(webhook_router)
        .merge(
            Router::new()
                .route("/api/register", post(handlers::register))
                .route("/api/login", post(handlers::login))
                .route(
                    "/api/works/:work_key/progress",
                    get(handlers::get_work_progress).post(handlers::set_work_progress),
                )
                // コメント
                .route(
                    "/api/works/:work_key/comments",
                    get(get_comments).post(post_comment),
                )
                // お気に入り
                .route(
                    "/api/works/:work_key/favorite",
                    get(get_favorite_status).post(toggle_favorite),
                )
                // ユーザー自身のデータ
                .route("/api/users/me/favorites", get(get_my_favorites))
                .route("/api/users/me/dashboard", get(get_dashboard))
                // 著者・カタログ
                .route("/api/artworks", post(create_artwork))
                .route("/api/artworks/mine", get(list_my_artworks))
                .route("/api/artworks/:id", patch(patch_artwork))
                .route("/api/catalog/works", get(catalog_list))
                .route("/api/catalog/works/:id", get(catalog_get))
                .route("/api/ai/paper-outline", post(handlers::paper_outline))
                .route("/api/ai/pdf-text", post(pdf_upload::pdf_text_extract))
                // AI パイプライン（Job 非同期処理）
                .route("/api/ai/ingest", post(handlers::ingest_job))
                .route("/api/ai/jobs/:id", get(handlers::get_job_status))
                .route(
                    "/api/checkout/session",
                    post(checkout::create_checkout_session),
                )
                .layer(DefaultBodyLimit::max(12 * 1024 * 1024))
                .layer(GovernorLayer { config: governor_conf })
                .layer(cors)
                .with_state(state),
        );

    let addr = SocketAddr::from(([0, 0, 0, 0], 3000));
    tracing::info!("listening on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(
        listener,
        app.into_make_service_with_connect_info::<SocketAddr>(),
    )
    .await?;

    Ok(())
}
