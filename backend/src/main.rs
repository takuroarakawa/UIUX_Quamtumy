//! Quantumy Auth API — ユーザー登録・ログイン API のエントリポイント
//!
//! 起動後:
//! - POST /api/register — ユーザー登録
//! - POST /api/login    — ログイン

use axum::{
    routing::post,
    Router,
};
use std::net::SocketAddr;
use tower_http::cors::{Any, CorsLayer};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod handlers;
mod models;

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

    let app = Router::new()
        .route("/api/register", post(handlers::register))
        .route("/api/login", post(handlers::login))
        .layer(
            CorsLayer::new()
                .allow_origin(Any)
                .allow_methods(Any)
                .allow_headers(Any),
        )
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], 3000));
    tracing::info!("listening on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
