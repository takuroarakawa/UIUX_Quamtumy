//! PDF アップロード → テキスト抽出（テキストレイヤーのある PDF のみ。スキャンは OCR 未対応）
//!
//! フロントエンドは `Content-Type: application/pdf` で生バイナリ POST する。
//! multipart を使わないことで multer の解析問題を完全に回避する。

use axum::{body::Bytes, response::IntoResponse, Json};

use crate::error::AppError;
use crate::models::PdfTextResponse;

const MAX_PDF_BYTES: usize = 20 * 1024 * 1024; // 20MB

/// POST /api/ai/pdf-text
///
/// リクエスト: `Content-Type: application/pdf` + 生バイナリボディ
pub async fn pdf_text_extract(body: Bytes) -> Result<impl IntoResponse, AppError> {
    tracing::info!("PDF アップロード開始: {} bytes", body.len());

    if body.is_empty() {
        return Err(AppError::BadRequest("空のファイルです".into()));
    }
    if body.len() > MAX_PDF_BYTES {
        return Err(AppError::BadRequest(format!(
            "PDF は {}MB 以下にしてください（現在: {}MB）",
            MAX_PDF_BYTES / 1024 / 1024,
            body.len() / 1024 / 1024
        )));
    }
    // PDF マジックバイト確認（%PDF）
    if !body.starts_with(b"%PDF") {
        return Err(AppError::BadRequest(
            "PDF ファイルではありません（%PDF ヘッダーが見つかりません）".into(),
        ));
    }

    let text = pdf_extract::extract_text_from_mem(&body).map_err(|e| {
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
    tracing::info!("PDF テキスト抽出成功: {} 文字", s.len());
    Ok(Json(PdfTextResponse {
        ok: true,
        message: "ok".into(),
        text: s,
        truncated,
    }))
}
