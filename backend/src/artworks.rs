//! 著者向け作品 CRUD と公開カタログ（`artworks` テーブル）

use axum::{
    extract::{Path, State},
    http::HeaderMap,
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde_json::json;
use uuid::Uuid;

use crate::error::AppError;
use crate::handlers::user_id_from_auth;
use crate::models::{
    ArtworkDetailResponse, ArtworkMineResponse, CatalogListResponse, CatalogWorkSummary,
    CreateArtworkRequest, PatchArtworkRequest,
};
use crate::AppState;

fn default_content() -> serde_json::Value {
    json!({
        "version": 1,
        "pages": [],
        "meta": {
            "researchField": "",
            "category": "",
            "academicMajor": "",
            "academicMinor": "",
            "coverImageUrl": ""
        }
    })
}

fn pages_len(content: &serde_json::Value) -> usize {
    content
        .get("pages")
        .and_then(|p| p.as_array())
        .map(|a| a.len())
        .unwrap_or(0)
}

/// POST /api/artworks — 下書き作成（著者）
pub async fn create_artwork(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(payload): Json<CreateArtworkRequest>,
) -> Result<impl IntoResponse, AppError> {
    let author_id = user_id_from_auth(&headers)?;

    let title = payload.title.trim();
    if title.is_empty() {
        return Err(AppError::BadRequest("タイトルを入力してください。".into()));
    }

    let mut content = payload.content_json.unwrap_or_else(default_content);
    if !content.is_object() {
        content = default_content();
    }
    if content.get("pages").is_none() {
        content["pages"] = json!([]);
    }
    if content.get("meta").is_none() {
        content["meta"] = json!({});
    }

    let price = payload.price.unwrap_or(0).max(0);

    let desc = payload
        .description
        .as_ref()
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string());
    let doi_v = payload
        .doi
        .as_ref()
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string());
    let thumb = payload
        .thumbnail_url
        .as_ref()
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string());

    let row: ArtworkRow = sqlx::query_as(
        r#"
        INSERT INTO artworks (author_id, title, description, doi, thumbnail_url, content_json, price, is_published)
        VALUES ($1, $2, $3, $4, $5, $6, $7, false)
        RETURNING id, author_id, title, description, doi, thumbnail_url, content_json, is_published, price, created_at
        "#,
    )
    .bind(author_id)
    .bind(title)
    .bind(&desc)
    .bind(&doi_v)
    .bind(&thumb)
    .bind(&content)
    .bind(price)
    .fetch_one(&state.pool)
    .await?;

    let mut artwork = catalog_detail_from_row(
        row.id,
        row.title,
        row.description,
        row.doi,
        row.thumbnail_url,
        row.price,
        row.is_published,
        row.content_json,
    );
    artwork.created_at = Some(row.created_at.to_rfc3339());

    Ok((StatusCode::CREATED, Json(ArtworkDetailResponse { ok: true, artwork })))
}

#[derive(Debug, sqlx::FromRow)]
struct ArtworkRow {
    id: Uuid,
    author_id: Uuid,
    title: String,
    description: Option<String>,
    doi: Option<String>,
    thumbnail_url: Option<String>,
    content_json: serde_json::Value,
    is_published: bool,
    price: i64,
    created_at: chrono::DateTime<chrono::Utc>,
}

fn catalog_detail_from_row(
    id: Uuid,
    title: String,
    description: Option<String>,
    doi: Option<String>,
    thumbnail_url: Option<String>,
    price: i64,
    is_published: bool,
    content_json: serde_json::Value,
) -> CatalogWorkSummary {
    let meta = content_json.get("meta").cloned().unwrap_or(json!({}));
    let research_field = meta
        .get("researchField")
        .and_then(|x| x.as_str())
        .unwrap_or("")
        .to_string();
    let category = meta
        .get("category")
        .and_then(|x| x.as_str())
        .unwrap_or("")
        .to_string();
    let academic_major = meta
        .get("academicMajor")
        .and_then(|x| x.as_str())
        .unwrap_or("")
        .to_string();
    let academic_minor = meta
        .get("academicMinor")
        .and_then(|x| x.as_str())
        .unwrap_or("")
        .to_string();

    let cover = meta
        .get("coverImageUrl")
        .and_then(|x| x.as_str())
        .map(|s| s.to_string())
        .or_else(|| thumbnail_url.clone());

    CatalogWorkSummary {
        id: id.to_string(),
        title,
        description,
        doi: doi.unwrap_or_default(),
        thumbnail_url,
        research_field,
        category,
        academic_major,
        academic_minor,
        cover_image_url: cover,
        price,
        is_published,
        content_json,
        created_at: None,
    }
}

/// PATCH /api/artworks/:id — 著者のみ
pub async fn patch_artwork(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
    headers: HeaderMap,
    Json(payload): Json<PatchArtworkRequest>,
) -> Result<impl IntoResponse, AppError> {
    let user_id = user_id_from_auth(&headers)?;

    let row: Option<ArtworkRow> = sqlx::query_as(
        r#"SELECT id, author_id, title, description, doi, thumbnail_url, content_json, is_published, price, created_at FROM artworks WHERE id = $1"#,
    )
    .bind(id)
    .fetch_optional(&state.pool)
    .await?;

    let Some(mut row) = row else {
        return Err(AppError::NotFound("作品が見つかりません".into()));
    };

    if row.author_id != user_id {
        return Err(AppError::Forbidden("この作品を編集する権限がありません".into()));
    }

    if let Some(ref t) = payload.title {
        let t = t.trim();
        if t.is_empty() {
            return Err(AppError::BadRequest("タイトルが空です。".into()));
        }
        row.title = t.to_string();
    }

    if payload.description.is_some() {
        row.description = payload.description.as_ref().and_then(|s| {
            let t = s.trim();
            if t.is_empty() {
                None
            } else {
                Some(t.to_string())
            }
        });
    }

    if payload.doi.is_some() {
        row.doi = payload.doi.as_ref().and_then(|s| {
            let t = s.trim();
            if t.is_empty() {
                None
            } else {
                Some(t.to_string())
            }
        });
    }

    if payload.thumbnail_url.is_some() {
        row.thumbnail_url = payload.thumbnail_url.as_ref().and_then(|s| {
            let t = s.trim();
            if t.is_empty() {
                None
            } else {
                Some(t.to_string())
            }
        });
    }

    if let Some(p) = payload.price {
        row.price = p.max(0);
    }

    if let Some(ref cj) = payload.content_json {
        if !cj.is_object() {
            return Err(AppError::BadRequest("content_json はオブジェクトである必要があります".into()));
        }
        row.content_json = cj.clone();
        if row.content_json.get("pages").is_none() {
            row.content_json["pages"] = json!([]);
        }
        if row.content_json.get("meta").is_none() {
            row.content_json["meta"] = json!({});
        }
    }

    if let Some(pub_flag) = payload.is_published {
        if pub_flag && pages_len(&row.content_json) == 0 {
            return Err(AppError::BadRequest(
                "ページ画像が1枚以上あるときのみ公開できます。".into(),
            ));
        }
        row.is_published = pub_flag;
    }

    sqlx::query(
        r#"
        UPDATE artworks SET
          title = $2,
          description = $3,
          doi = $4,
          thumbnail_url = $5,
          content_json = $6,
          is_published = $7,
          price = $8
        WHERE id = $1 AND author_id = $9
        "#,
    )
    .bind(id)
    .bind(&row.title)
    .bind(&row.description)
    .bind(&row.doi)
    .bind(&row.thumbnail_url)
    .bind(&row.content_json)
    .bind(row.is_published)
    .bind(row.price)
    .bind(user_id)
    .execute(&state.pool)
    .await?;

    let mut artwork = catalog_detail_from_row(
        row.id,
        row.title,
        row.description,
        row.doi,
        row.thumbnail_url,
        row.price,
        row.is_published,
        row.content_json,
    );
    artwork.created_at = Some(row.created_at.to_rfc3339());

    Ok(Json(ArtworkDetailResponse { ok: true, artwork }))
}

/// GET /api/artworks/mine — 自分の作品一覧（著者）
pub async fn list_my_artworks(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    let user_id = user_id_from_auth(&headers)?;

    let rows: Vec<ArtworkRow> = sqlx::query_as(
        r#"SELECT id, author_id, title, description, doi, thumbnail_url, content_json, is_published, price, created_at
           FROM artworks WHERE author_id = $1 ORDER BY created_at DESC"#,
    )
    .bind(user_id)
    .fetch_all(&state.pool)
    .await?;

    let mut items = Vec::with_capacity(rows.len());
    for row in rows {
        let mut s = catalog_detail_from_row(
            row.id,
            row.title,
            row.description,
            row.doi,
            row.thumbnail_url,
            row.price,
            row.is_published,
            row.content_json,
        );
        s.created_at = Some(row.created_at.to_rfc3339());
        items.push(s);
    }

    Ok(Json(ArtworkMineResponse { ok: true, items }))
}

/// GET /api/catalog/works — 公開カタログ（ページ画像は含む）
pub async fn catalog_list(State(state): State<AppState>) -> Result<impl IntoResponse, AppError> {
    let rows: Vec<ArtworkRow> = sqlx::query_as(
        r#"SELECT id, author_id, title, description, doi, thumbnail_url, content_json, is_published, price, created_at
           FROM artworks WHERE is_published = true ORDER BY created_at DESC"#,
    )
    .fetch_all(&state.pool)
    .await?;

    let mut items = Vec::with_capacity(rows.len());
    for row in rows {
        let mut s = catalog_detail_from_row(
            row.id,
            row.title,
            row.description,
            row.doi,
            row.thumbnail_url,
            row.price,
            row.is_published,
            row.content_json,
        );
        s.created_at = Some(row.created_at.to_rfc3339());
        items.push(s);
    }

    Ok(Json(CatalogListResponse { ok: true, items }))
}

/// GET /api/catalog/works/:id — 公開作品の詳細（ディープリンク用）
pub async fn catalog_get(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<impl IntoResponse, AppError> {
    let row: Option<ArtworkRow> = sqlx::query_as(
        r#"SELECT id, author_id, title, description, doi, thumbnail_url, content_json, is_published, price, created_at
           FROM artworks WHERE id = $1 AND is_published = true"#,
    )
    .bind(id)
    .fetch_optional(&state.pool)
    .await?;

    let Some(row) = row else {
        return Err(AppError::NotFound("作品が見つかりません".into()));
    };

    let mut artwork = catalog_detail_from_row(
        row.id,
        row.title,
        row.description,
        row.doi,
        row.thumbnail_url,
        row.price,
        row.is_published,
        row.content_json,
    );
    artwork.created_at = Some(row.created_at.to_rfc3339());

    Ok(Json(ArtworkDetailResponse { ok: true, artwork }))
}
