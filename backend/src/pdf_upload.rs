//! PDF アップロード → テキスト抽出（テキストレイヤーのある PDF のみ。スキャンは OCR 未対応）

use axum::{extract::Multipart, response::IntoResponse, Json};

use crate::error::AppError;
use crate::models::PdfTextResponse;

const MAX_PDF_BYTES: usize = 20 * 1024 * 1024; // 20MB（router 側は 30MB 許容）

/// POST /api/ai/pdf-text — `multipart/form-data` フィールド名 `file`
pub async fn pdf_text_extract(mut multipart: Multipart) -> Result<impl IntoResponse, AppError> {
    tracing::info!("PDF アップロード開始");
    let mut file_bytes: Option<Vec<u8>> = None;
    while let Some(field) = multipart
        .next_field()
        .await
        .map_err(|e| AppError::BadRequest(format!("multipart 読取エラー: {}", e)))?
    {
        let field_name = field.name().unwrap_or("").to_string();
        let file_name = field.file_name().unwrap_or("").to_string();
        tracing::info!("multipart フィールド: name={} filename={}", field_name, file_name);
        if field_name != "file" {
            continue;
        }
        let data = field
            .bytes()
            .await
            .map_err(|e| AppError::BadRequest(format!("ファイル読取エラー: {}", e)))?;
        tracing::info!("PDF バイト数: {}", data.len());
        if data.is_empty() {
            return Err(AppError::BadRequest("空のファイルです".into()));
        }
        if data.len() > MAX_PDF_BYTES {
            return Err(AppError::BadRequest(format!(
                "PDF は {}MB 以下にしてください（現在: {}MB）",
                MAX_PDF_BYTES / 1024 / 1024,
                data.len() / 1024 / 1024
            )));
        }
        file_bytes = Some(data.to_vec());
        break;
    }
    let buf = file_bytes.ok_or_else(|| {
        AppError::BadRequest("multipart に `file` フィールド（PDF）が必要です".into())
    })?;

    let text = pdf_extract::extract_text_from_mem(&buf).map_err(|e| {
        AppError::BadRequest(format!(
            "PDF からテキストを抽出できません: {}（画像のみのスキャンPDFは未対応）",
            e
        ))
    })?;

    let trimmed = text.trim();
    if trimmed.is_empty() {
        return Err(AppError::BadRequest(
            "抽出結果が空です。スキャンPDFの場合は OCR 連携が必要です。".into(),
        ));
    }
    let truncated = trimmed.len() > 80_000;
    let s: String = if truncated {
        trimmed.chars().take(80_000).collect()
    } else {
        trimmed.to_string()
    };
    Ok(Json(PdfTextResponse {
        ok: true,
        message: "ok".into(),
        text: s,
        truncated,
    }))
}
