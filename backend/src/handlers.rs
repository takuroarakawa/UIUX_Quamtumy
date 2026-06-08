//! 認証 API（登録・ログイン）

use axum::{
    extract::{Path, State},
    http::StatusCode,
    http::HeaderMap,
    response::IntoResponse,
    Json,
};
use sha2::{Digest, Sha256};
use uuid::Uuid;

use argon2::{
    password_hash::{PasswordHash, PasswordHasher, PasswordVerifier, SaltString},
    Argon2,
};
use rand::rngs::OsRng;

use crate::auth::issue_token;
use crate::error::AppError;
use crate::models::{
    AuthResponse, IngestRequest, IngestResponse, JobStatusResponse,
    LoginRequest, PaperOutlineRequest, PaperOutlineResponse, RegisterRequest,
    WorkProgressResponse, WorkProgressUpdateRequest,
};
use crate::AppState;

/// GET /health — 本番・監視用（DB 非依存）
pub async fn health_check() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "status": "ok",
        "service": "quantumy-api"
    }))
}

fn json_response(status: StatusCode, body: AuthResponse) -> impl IntoResponse {
    (status, Json(body))
}

fn jwt_secret() -> String {
    // MVP: 未設定ならデフォルトで動かす（本番では必ず差し替えてください）
    std::env::var("JWT_SECRET").unwrap_or_else(|_| "dev_change_me".into())
}

pub(crate) fn user_id_from_auth(headers: &HeaderMap) -> Result<Uuid, AppError> {
    let Some(raw) = headers.get("authorization") else {
        return Err(AppError::Unauthorized("Authorizationヘッダが必要です".into()));
    };
    let raw = raw.to_str().map_err(|_| AppError::Unauthorized("無効なAuthorizationです".into()))?;
    let Some(token) = raw.strip_prefix("Bearer ") else {
        return Err(AppError::Unauthorized("Bearerトークンが必要です".into()));
    };
    crate::auth::verify_token(token, &jwt_secret())
}

/// POST /api/register
pub async fn register(
    State(state): State<AppState>,
    Json(payload): Json<RegisterRequest>,
) -> impl IntoResponse {
    let email = payload.email.trim().to_lowercase();
    if email.is_empty() || !email.contains('@') {
        return json_response(
            StatusCode::BAD_REQUEST,
            AuthResponse {
                ok: false,
                message: "有効なメールアドレスを入力してください。".into(),
                user_id: None,
                access_token: None,
                expires_in_secs: None,
            },
        )
        .into_response();
    }
    if payload.password.len() < 8 {
        return json_response(
            StatusCode::BAD_REQUEST,
            AuthResponse {
                ok: false,
                message: "パスワードは8文字以上にしてください。".into(),
                user_id: None,
                access_token: None,
                expires_in_secs: None,
            },
        )
        .into_response();
    }

    let password_hash = {
        let salt = SaltString::generate(&mut OsRng);
        let argon2 = Argon2::default(); // Argon2id
        match argon2.hash_password(payload.password.as_bytes(), &salt) {
            Ok(hash) => hash.to_string(),
            Err(e) => {
                tracing::error!("argon2 hash: {}", e);
                return json_response(
                    StatusCode::INTERNAL_SERVER_ERROR,
                    AuthResponse {
                        ok: false,
                        message: "サーバーエラーです。".into(),
                        user_id: None,
                        access_token: None,
                        expires_in_secs: None,
                    },
                )
                .into_response();
            }
        }
    };

    let display_name = payload
        .display_name
        .as_ref()
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string());

    let result = sqlx::query_scalar::<_, Uuid>(
        "INSERT INTO users (email, password_hash, display_name) VALUES ($1, $2, $3) RETURNING id",
    )
    .bind(&email)
    .bind(&password_hash)
    .bind(display_name.as_deref())
    .fetch_one(&state.pool)
    .await;

    match result {
        Ok(id) => json_response(
            StatusCode::CREATED,
            AuthResponse {
                ok: true,
                message: "登録しました。".into(),
                user_id: Some(id.to_string()),
                access_token: None,
                expires_in_secs: None,
            },
        )
        .into_response(),
        Err(e) => {
            if let sqlx::Error::Database(ref db) = e {
                if db.code().as_deref() == Some("23505") {
                    return json_response(
                        StatusCode::CONFLICT,
                        AuthResponse {
                            ok: false,
                            message: "このメールアドレスは既に登録されています。".into(),
                            user_id: None,
                            access_token: None,
                            expires_in_secs: None,
                        },
                    )
                    .into_response();
                }
            }
            tracing::error!("register: {}", e);
            json_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                AuthResponse {
                    ok: false,
                    message: "登録に失敗しました。".into(),
                    user_id: None,
                    access_token: None,
                    expires_in_secs: None,
                },
            )
            .into_response()
        }
    }
}

/// POST /api/login
pub async fn login(
    State(state): State<AppState>,
    Json(payload): Json<LoginRequest>,
) -> impl IntoResponse {
    let email = payload.email.trim().to_lowercase();

    let row: Result<Option<(Uuid, String)>, sqlx::Error> = sqlx::query_as(
        "SELECT id, password_hash FROM users WHERE email = $1",
    )
    .bind(&email)
    .fetch_optional(&state.pool)
    .await;

    let row = match row {
        Ok(r) => r,
        Err(e) => {
            tracing::error!("login: {}", e);
            return json_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                AuthResponse {
                    ok: false,
                    message: "サーバーエラーです。".into(),
                    user_id: None,
                    access_token: None,
                    expires_in_secs: None,
                },
            )
            .into_response();
        }
    };

    let Some((id, hash)) = row else {
        return json_response(
            StatusCode::UNAUTHORIZED,
            AuthResponse {
                ok: false,
                message: "メールまたはパスワードが正しくありません。".into(),
                user_id: None,
                access_token: None,
                expires_in_secs: None,
            },
        )
        .into_response();
    };

    let ok = (|| {
        let parsed = PasswordHash::new(&hash).ok()?;
        Argon2::default()
            .verify_password(payload.password.as_bytes(), &parsed)
            .ok()?;
        Some(true)
    })()
    .unwrap_or(false);
    if !ok {
        return json_response(
            StatusCode::UNAUTHORIZED,
            AuthResponse {
                ok: false,
                message: "メールまたはパスワードが正しくありません。".into(),
                user_id: None,
                access_token: None,
                expires_in_secs: None,
            },
        )
        .into_response();
    }

    let secret = jwt_secret();
    let ttl_secs: u64 = std::env::var("JWT_ACCESS_TTL_SECS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(60 * 60 * 24); // 既定: 24時間（長くしたい場合は JWT_ACCESS_TTL_SECS で上書き）
    let access_token = match issue_token(id, &secret, ttl_secs) {
        Ok(t) => Some(t),
        Err(e) => {
            tracing::error!("issue_token: {}", e);
            return json_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                AuthResponse {
                    ok: false,
                    message: "サーバーエラーです。".into(),
                    user_id: None,
                    access_token: None,
                    expires_in_secs: None,
                },
            )
            .into_response();
        }
    };

    json_response(
        StatusCode::OK,
        AuthResponse {
            ok: true,
            message: "ログインに成功しました。".into(),
            user_id: Some(id.to_string()),
            access_token,
            expires_in_secs: Some(ttl_secs),
        },
    )
    .into_response()
}

/// GET /api/works/:work_key/progress
pub async fn get_work_progress(
    State(state): State<AppState>,
    Path(work_key): Path<String>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, AppError> {
    let user_id = user_id_from_auth(&headers)?;

    let last_spread_index = sqlx::query_scalar::<_, i32>(
        r#"
        SELECT last_spread_index
        FROM work_progress
        WHERE user_id = $1 AND work_key = $2
        "#,
    )
    .bind(user_id)
    .bind(&work_key)
    .fetch_optional(&state.pool)
    .await?
    .unwrap_or(0);

    Ok(Json(WorkProgressResponse {
        ok: true,
        work_key,
        last_spread_index,
    }))
}

/// POST /api/works/:work_key/progress
pub async fn set_work_progress(
    State(state): State<AppState>,
    Path(work_key): Path<String>,
    headers: HeaderMap,
    Json(payload): Json<WorkProgressUpdateRequest>,
) -> Result<impl IntoResponse, AppError> {
    let user_id = user_id_from_auth(&headers)?;

    if payload.last_spread_index < 0 {
        return Err(AppError::BadRequest("last_spread_index は0以上で指定してください".into()));
    }

    sqlx::query(
        r#"
        INSERT INTO work_progress (user_id, work_key, last_spread_index)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, work_key)
        DO UPDATE SET
          last_spread_index = EXCLUDED.last_spread_index,
          updated_at = NOW()
        "#,
    )
    .bind(user_id)
    .bind(&work_key)
    .bind(payload.last_spread_index)
    .execute(&state.pool)
    .await?;

    Ok(Json(WorkProgressResponse {
        ok: true,
        work_key,
        last_spread_index: payload.last_spread_index,
    }))
}

fn mock_paper_outline(text: &str) -> PaperOutlineResponse {
    let excerpt: String = text.chars().take(500).collect();
    PaperOutlineResponse {
        ok: true,
        message: "ok".into(),
        source: "mock".into(),
        outline_markdown: format!(
            "## 論文→漫画ネーム（モック・ルールベース）\n\n> {}\n\n\
             1. **導入コマ** — 何がわからないか／なぜ面白いか\n\
             2. **対比コマ** — 既研究・常識とのズレ\n\
             3. **核コマ** — 方法・結果・主張の見せ場\n\
             4. **余韻コマ** — 未解決の問い・読者への招待\n\n\
             `OPENAI_API_KEY` を Fly の secrets に入れると、同エンドポイントが LLM 案に切り替わります。",
            excerpt
        ),
        panel_beats: vec![
            "導入: 問題の提示".into(),
            "対比: ギャップの明示".into(),
            "核: 方法と結果".into(),
            "余韻: 次の問い".into(),
        ],
        theme_line: None,
        characters: vec![],
        synopsis: None,
        manga_tone: None,
    }
}

#[derive(serde::Deserialize)]
struct OpenAiChatResponse {
    choices: Vec<OpenAiChoice>,
}

#[derive(serde::Deserialize)]
struct OpenAiChoice {
    message: OpenAiMessage,
}

#[derive(serde::Deserialize)]
struct OpenAiMessage {
    content: String,
}

// ── Gemini API レスポンス構造体 ──────────────────────────────────────────────
#[derive(serde::Deserialize)]
struct GeminiResponse {
    candidates: Vec<GeminiCandidate>,
}
#[derive(serde::Deserialize)]
struct GeminiCandidate {
    content: GeminiContent,
}
#[derive(serde::Deserialize)]
struct GeminiContent {
    parts: Vec<GeminiPart>,
}
#[derive(serde::Deserialize)]
struct GeminiPart {
    text: String,
}

impl GeminiResponse {
    fn text(&self) -> Option<&str> {
        self.candidates.first()?.content.parts.first().map(|p| p.text.as_str())
    }
}

#[derive(serde::Deserialize, Default)]
struct OutlineJson {
    #[serde(default)]
    outline_markdown: String,
    #[serde(default)]
    panel_beats: Vec<String>,
    // C1/C2 拡張フィールド
    #[serde(default)]
    theme_line: Option<String>,
    #[serde(default)]
    characters: Vec<crate::models::MangaCharacter>,
    #[serde(default)]
    synopsis: Option<String>,
}

async fn try_openai_outline(title: Option<&str>, text: &str) -> Option<PaperOutlineResponse> {
    let key = std::env::var("OPENAI_API_KEY").ok()?;
    if key.trim().is_empty() {
        return None;
    }
    let model = std::env::var("OPENAI_MODEL").unwrap_or_else(|_| "gpt-4o-mini".into());

    let title_line = title
        .filter(|t| !t.trim().is_empty())
        .map(|t| format!("論文タイトル（参考）: {}\n\n", t))
        .unwrap_or_default();

    let prompt = format!(
        r#"{}以下は論文の抜粋です。日本語で「研究マンガ」のネーム案を返してください。
厳密なJSONのみを出力してください（前後に説明文を付けない）。キーは次の2つ:
- "outline_markdown": string（Markdown。見出しと箇条書きで4〜8行程度）
- "panel_beats": string の配列（ちょうど4要素。各要素は1コマ分の演出指示。順は 導入→対比→核→余韻）

【抜粋】
{}"#,
        title_line, text
    );

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .ok()?;

    let body = serde_json::json!({
        "model": model,
        "messages": [{ "role": "user", "content": prompt }],
        "response_format": { "type": "json_object" }
    });

    let res = match client
        .post("https://api.openai.com/v1/chat/completions")
        .header("Authorization", format!("Bearer {}", key))
        .header("Content-Type", "application/json")
        .json(&body)
        .send()
        .await
    {
        Ok(r) => r,
        Err(e) => {
            tracing::warn!("openai request: {}", e);
            return None;
        }
    };

    if !res.status().is_success() {
        let status = res.status();
        let err_body = res.text().await.unwrap_or_default();
        tracing::warn!("openai http {}: {}", status, err_body);
        return None;
    }

    let parsed: OpenAiChatResponse = res.json().await.ok()?;
    let content = parsed.choices.first()?.message.content.trim();
    let outline: OutlineJson = serde_json::from_str(content).map_err(|e| tracing::warn!("openai json parse: {}", e)).ok()?;

    if outline.panel_beats.is_empty() {
        return None;
    }

    Some(PaperOutlineResponse {
        ok: true,
        message: "ok".into(),
        source: "openai".into(),
        outline_markdown: outline.outline_markdown,
        panel_beats: outline.panel_beats,
        theme_line: None, characters: vec![], synopsis: None, manga_tone: None,
    })
}

/// POST /api/ai/paper-outline — 認証不要（MVP）。レート制限はグローバル governor に依存。
pub async fn paper_outline(
    State(_state): State<AppState>,
    Json(payload): Json<PaperOutlineRequest>,
) -> impl IntoResponse {
    let text = payload.text.trim();
    if text.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(PaperOutlineResponse {
                ok: false,
                message: "text が空です。抄録や段落を貼り付けてください。".into(),
                source: "none".into(),
                outline_markdown: String::new(),
                panel_beats: vec![],
                theme_line: None, characters: vec![], synopsis: None, manga_tone: None,
            }),
        )
            .into_response();
    }
    if text.len() > 80_000 {
        return (
            StatusCode::BAD_REQUEST,
            Json(PaperOutlineResponse {
                ok: false,
                message: "text が長すぎます（上限 80000 文字）。".into(),
                source: "none".into(),
                outline_markdown: String::new(),
                panel_beats: vec![],
                theme_line: None, characters: vec![], synopsis: None, manga_tone: None,
            }),
        )
            .into_response();
    }

    if let Some(resp) = try_openai_outline(payload.title.as_deref(), text).await {
        return (StatusCode::OK, Json(resp)).into_response();
    }

    (StatusCode::OK, Json(mock_paper_outline(text))).into_response()
}

// ─────────────────────────────────────────────────────────────────────────────
// AI パイプライン — Job 非同期処理
//
// 【なぜ Job 化するか】
//   PDF→構造化→物語化は数十秒〜数分かかる。HTTP リクエストを1本で待つと
//   タイムアウト・ユーザー体験・コストの三つが同時に壊れる。
//   「ジョブを作成して id を即返す → ポーリングで状態を取得」という
//   一般的な非同期ジョブパターンを採用する。
//
// 【MVP の実装方針】
//   本番品質のキュー（Redis/SQS）は Phase 2 以降。MVP では tokio::spawn で
//   バックグラウンドタスクを起動し、ai_jobs / ai_artifacts テーブルに結果を書く。
//   FOR UPDATE SKIP LOCKED を使うクラシックな Postgres ジョブキューへの
//   移行は、ワーカー数が増えたタイミングで差し替える（インターフェースは変わらない）。
// ─────────────────────────────────────────────────────────────────────────────

/// POST /api/ai/ingest — テキスト貼り付けを受け取りジョブを作成して即返す
///
/// 【認証】任意（非ログインでも「お試し」を受け入れる MVP 方針）
/// 【フロー】
///   1. 入力バリデーション
///   2. SHA-256 で重複排除チェック（同一テキストの完了ジョブがあれば再利用）
///   3. ai_jobs INSERT → job_id を返却
///   4. tokio::spawn でバックグラウンド処理（既存の outline ロジックを流用）
pub async fn ingest_job(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(payload): Json<IngestRequest>,
) -> impl IntoResponse {
    // ── 入力バリデーション ───────────────────────────────────────────────────
    let text = match &payload.text {
        Some(t) => t.trim().to_string(),
        None => {
            return (
                StatusCode::BAD_REQUEST,
                Json(IngestResponse {
                    ok: false,
                    job_id: Uuid::nil(),
                    message: "text フィールドが必要です（pdf_upload は Phase2 以降）。".into(),
                }),
            )
                .into_response();
        }
    };

    if text.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(IngestResponse {
                ok: false,
                job_id: Uuid::nil(),
                message: "text が空です。抄録や段落を貼り付けてください。".into(),
            }),
        )
            .into_response();
    }
    // バイト数ではなく文字数で比較（Unicode 多バイト文字対応）
    if text.chars().count() > 120_000 {
        return (
            StatusCode::BAD_REQUEST,
            Json(IngestResponse {
                ok: false,
                job_id: Uuid::nil(),
                message: "text が長すぎます（上限 120,000 文字）。フロントで短くしてから送信してください。".into(),
            }),
        )
            .into_response();
    }

    // ── ログインユーザーを取得（失敗しても処理続行） ─────────────────────────
    let user_id: Option<Uuid> = user_id_from_auth(&headers).ok();

    // ── 重複排除: 同一テキストの完了済みジョブを再利用 ─────────────────────
    // 【なぜハッシュか】テキスト本文（最大80k文字）を毎回 DB 比較するのはコスト大。
    // SHA-256 の 64 文字で高速に一致検索できる。
    // トーンが異なれば別ジョブとして扱う（同一テキスト×別トーン = 別結果）
    let hash_input = format!("{}:{}", text, payload.manga_tone.as_deref().unwrap_or("default"));
    let hash = format!("{:x}", Sha256::digest(hash_input.as_bytes()));

    let existing: Option<Uuid> = sqlx::query_scalar(
        r#"SELECT j.id FROM ai_jobs j
           JOIN ai_artifacts a ON a.job_id = j.id AND a.stage = 'C3_name_generate'
           WHERE j.input_text_hash = $1 AND j.status = 'completed' AND a.model_used != 'mock'
           ORDER BY j.completed_at DESC LIMIT 1"#
    )
    .bind(&hash)
    .fetch_optional(&state.pool)
    .await
    .unwrap_or(None);

    if let Some(cached_id) = existing {
        return (
            StatusCode::OK,
            Json(IngestResponse {
                ok: true,
                job_id: cached_id,
                message: "同一テキストの完了済みジョブを再利用します。".into(),
            }),
        )
            .into_response();
    }

    // ── ジョブ作成 ──────────────────────────────────────────────────────────
    // 【なぜ DB INSERT を先にするか】
    // tokio::spawn はメモリ内の非同期タスクなので、API サーバーが再起動すると消える。
    // DB に先に記録することで「作成したが結果がない」状態を追跡でき、
    // 将来のワーカー型キューへの移行も同じ ai_jobs テーブルをそのまま使える。
    let job_id: Uuid = match sqlx::query_scalar(
        r#"INSERT INTO ai_jobs
            (user_id, input_source, input_text, input_text_hash, paper_title, doi, status)
           VALUES ($1, 'text_paste', $2, $3, $4, $5, 'pending')
           RETURNING id"#,
    )
    .bind(user_id)
    .bind(&text)
    .bind(&hash)
    .bind(payload.title.as_deref())
    .bind(payload.doi.as_deref())
    .fetch_one(&state.pool)
    .await
    {
        Ok(id) => id,
        Err(e) => {
            tracing::error!("ai_jobs insert: {}", e);
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(IngestResponse {
                    ok: false,
                    job_id: Uuid::nil(),
                    message: "ジョブの作成に失敗しました。".into(),
                }),
            )
                .into_response();
        }
    };

    // ── バックグラウンドワーカー起動 ────────────────────────────────────────
    // 【なぜ tokio::spawn か（MVP）】
    // Phase2 で Postgres SKIP LOCKED ワーカーや Redis キューに差し替えるまでの
    // 「最短の縦スライス」として採用。レスポンスを待たせない点は本番と同じ。
    let pool = state.pool.clone();
    let title = payload.title.clone();
    let manga_tone = payload.manga_tone.clone();
    tokio::spawn(async move {
        run_pipeline(pool, job_id, text, title, manga_tone).await;
    });

    (
        StatusCode::ACCEPTED,
        Json(IngestResponse {
            ok: true,
            job_id,
            message: "ジョブを受け付けました。GET /api/ai/jobs/:id で進捗を確認してください。".into(),
        }),
    )
        .into_response()
}

// ─────────────────────────────────────────────────────────────────────────────
// B1 Segment — セクション分割
//
// 【なぜ正規表現ヒューリスティックか】
//   GROBID 等の本格的な論文パーサは外部プロセスが必要でデプロイが複雑になる。
//   IMRaD（Abstract/Intro/Methods/Results/Discussion）の見出しは
//   8割以上の論文で英数字の大文字パターンとして現れるため、
//   まず regex で十分な品質が得られる。Phase2 で GROBID に差し替え可能。
// ─────────────────────────────────────────────────────────────────────────────

/// 論文テキストから検出したセクション
struct Section {
    heading: String,
    body: String,
}

/// B1: テキストをセクションに分割する
///
/// 見出し候補: 行頭が大文字の単語のみで構成される行（例: "Abstract", "1. Introduction"）
fn b1_segment(text: &str) -> Vec<Section> {
    // よく使われる IMRaD + 追加セクション見出しパターン
    let heading_re = regex_lite::Regex::new(
        r"(?m)^[ \t]{0,4}(\d{0,2}\.?\s*)?(ABSTRACT|INTRODUCTION|RELATED WORK|BACKGROUND|METHODOLOGY|METHODS?|MATERIALS?(?: AND METHODS?)?|EXPERIMENTS?|RESULTS?|DISCUSSION|CONCLUSION|FUTURE WORK|REFERENCES?|ACKNOWLEDGMENTS?|APPENDIX)[^\n]*$"
    ).unwrap();

    let mut sections: Vec<Section> = Vec::new();
    let mut last_end = 0usize;
    let mut last_heading = "PREAMBLE".to_string();

    for m in heading_re.find_iter(text) {
        let body = text[last_end..m.start()].trim().to_string();
        if !body.is_empty() || !sections.is_empty() {
            sections.push(Section { heading: last_heading.clone(), body });
        }
        last_heading = m.as_str().trim().to_uppercase();
        last_end = m.end();
    }
    // 末尾セクション
    let tail = text[last_end..].trim().to_string();
    if !tail.is_empty() {
        sections.push(Section { heading: last_heading, body: tail });
    }

    // セクションが検出できなかった場合は全文を1セクションとして扱う
    if sections.is_empty() {
        sections.push(Section {
            heading: "FULL_TEXT".into(),
            body: text.trim().to_string(),
        });
    }

    sections
}

// ─────────────────────────────────────────────────────────────────────────────
// B2 Chunk — トークン上限チャンク分割
//
// 【なぜチャンクか】
//   長文論文（20〜80k 文字）をそのまま LLM に渡すとコンテキスト超過・
//   コスト急増・品質劣化の三つが同時に発生する。
//   セクション境界を優先しつつ、最大 CHUNK_SIZE 文字で切ることで
//   各 LLM 呼び出しを予測可能なサイズに抑える。
// ─────────────────────────────────────────────────────────────────────────────

/// 文字数ベースのチャンクサイズ（≒ 750〜1000 tokens）
const CHUNK_SIZE: usize = 3_000;
/// 前チャンクとの重複文字数（文脈の断絶を防ぐ）
const CHUNK_OVERLAP: usize = 200;

/// B2: セクションリストをチャンク配列に変換する
fn b2_chunk(sections: &[Section]) -> Vec<String> {
    let mut chunks: Vec<String> = Vec::new();

    for sec in sections {
        // REFERENCES 等は要約不要なのでスキップ
        if sec.heading.contains("REFERENCE") || sec.heading.contains("ACKNOWLEDGMENT") {
            continue;
        }
        let labeled = format!("[{}]\n{}", sec.heading, sec.body);
        let chars: Vec<char> = labeled.chars().collect();
        let len = chars.len();

        if len <= CHUNK_SIZE {
            chunks.push(labeled);
        } else {
            // CHUNK_SIZE 文字ずつスライドして分割
            let mut pos = 0;
            while pos < len {
                let end = (pos + CHUNK_SIZE).min(len);
                let chunk: String = chars[pos..end].iter().collect();
                chunks.push(chunk);
                if end == len {
                    break;
                }
                pos += CHUNK_SIZE - CHUNK_OVERLAP;
            }
        }
    }

    chunks
}

// ─────────────────────────────────────────────────────────────────────────────
// B3 Summarize — Map-Reduce 要約
//
// 【なぜ Map-Reduce か】
//   チャンクを並列に要約（Map）し、その要約を集約（Reduce）することで
//   長文を確実にコンテキスト内に収める。
//   OpenAI 未設定のモックでは「各セクションの冒頭2文」を抽出することで
//   同じ構造の `paper_brief` を生成し、C3 のプロンプトを共通化する。
// ─────────────────────────────────────────────────────────────────────────────

/// B3 の出力構造（= C3 の入力）
#[derive(serde::Serialize, serde::Deserialize, Clone)]
struct PaperBrief {
    /// 論文が解こうとしている問題・ギャップ
    problem: String,
    /// 採用した手法・アプローチ
    method: String,
    /// 主要な結果・発見
    key_result: String,
    /// 限界・今後の課題
    limitation: String,
    /// 上記4要素を1段落にまとめた総合要約
    summary: String,
    /// LLM ソース（"openai" | "mock"）
    source: String,
}

/// B3: チャンク配列からPaperBriefを生成する（Gemini → OpenAI → mock の優先順）
async fn b3_summarize(chunks: &[String], title: Option<&str>) -> PaperBrief {
    match try_gemini_summarize(chunks, title).await {
        Some(brief) => { tracing::info!("B3: gemini 成功"); return brief; }
        None => tracing::warn!("B3: gemini 失敗 → openai/mock にフォールバック"),
    }
    if let Some(brief) = try_openai_summarize(chunks, title).await {
        tracing::info!("B3: openai 成功");
        return brief;
    }
    tracing::warn!("B3: openai も失敗 → mock");
    mock_summarize(chunks, title)
}

/// B3 モック実装 — 各チャンクの冒頭文を抽出して構造化する
fn mock_summarize(chunks: &[String], title: Option<&str>) -> PaperBrief {
    // チャンクから最初の非空行を最大 N 文字まで抽出するヘルパー
    let extract_head = |chunk: &str, max: usize| -> String {
        chunk
            .lines()
            .find(|l| l.len() > 20)
            .unwrap_or(chunk)
            .chars()
            .take(max)
            .collect::<String>()
    };

    let problem = chunks
        .iter()
        .find(|c| c.contains("INTRODUCTION") || c.contains("BACKGROUND"))
        .map(|c| extract_head(c, 200))
        .unwrap_or_else(|| extract_head(chunks.first().map(String::as_str).unwrap_or(""), 200));

    let method = chunks
        .iter()
        .find(|c| c.contains("METHOD") || c.contains("APPROACH") || c.contains("EXPERIMENT"))
        .map(|c| extract_head(c, 200))
        .unwrap_or_else(|| "手法の記述が見つかりませんでした。".into());

    let key_result = chunks
        .iter()
        .find(|c| c.contains("RESULT") || c.contains("FINDING"))
        .map(|c| extract_head(c, 200))
        .unwrap_or_else(|| "結果の記述が見つかりませんでした。".into());

    let limitation = chunks
        .iter()
        .find(|c| c.contains("DISCUSSION") || c.contains("CONCLUSION") || c.contains("LIMITATION"))
        .map(|c| extract_head(c, 200))
        .unwrap_or_else(|| "考察・限界の記述が見つかりませんでした。".into());

    let title_str = title.unwrap_or("（無題）");
    let summary = format!(
        "「{}」の概要（モック）: {} / 手法: {} / 結果: {}",
        title_str,
        &problem.chars().take(80).collect::<String>(),
        &method.chars().take(80).collect::<String>(),
        &key_result.chars().take(80).collect::<String>(),
    );

    PaperBrief { problem, method, key_result, limitation, summary, source: "mock".into() }
}

/// Gemini API への共通ヘルパー（テキスト入力 → テキスト出力）
async fn gemini_generate(client: &reqwest::Client, key: &str, model: &str, prompt: &str, json_mode: bool) -> Option<String> {
    let url = format!(
        "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}",
        model, key
    );
    let mut config = serde_json::json!({});
    if json_mode {
        config = serde_json::json!({ "responseMimeType": "application/json" });
    }
    let body = serde_json::json!({
        "contents": [{ "parts": [{ "text": prompt }] }],
        "generationConfig": config,
    });
    let res = client.post(&url).json(&body).send().await.ok()?;
    if !res.status().is_success() {
        tracing::warn!("Gemini http {}", res.status());
        return None;
    }
    let parsed: GeminiResponse = res.json().await.ok()?;
    parsed.text().map(|s| s.trim().to_string())
}

/// B3 Gemini 実装 — Map → Reduce
async fn try_gemini_summarize(chunks: &[String], title: Option<&str>) -> Option<PaperBrief> {
    let key = std::env::var("GEMINI_API_KEY").ok()?;
    if key.trim().is_empty() { return None; }
    let model = std::env::var("GEMINI_MODEL").unwrap_or_else(|_| "gemini-2.5-flash".into());
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build().ok()?;

    // Map: 各チャンクを要約
    let mut chunk_summaries: Vec<String> = Vec::new();
    for chunk in chunks.iter().take(8) {
        let prompt = format!(
            "以下の論文抜粋から、問題・手法・結果・限界の要点を日本語で2〜4文で抽出してください。\
            マークダウンや説明文は不要。要点のみ箇条書きで。\n\n{}", chunk
        );
        if let Some(text) = gemini_generate(&client, &key, &model, &prompt, false).await {
            chunk_summaries.push(text);
        }
    }
    if chunk_summaries.is_empty() { return None; }

    // Reduce: 構造化 brief に集約
    let combined = chunk_summaries.join("\n\n---\n\n");
    let title_line = title.map(|t| format!("論文タイトル: {}\n\n", t)).unwrap_or_default();
    let reduce_prompt = format!(
        r#"{}以下は論文各部の要約です。これを統合し、厳密なJSONのみを出力してください。
キーは次の5つ（すべて日本語で）:
- "problem": 解こうとしている問題・ギャップ（1〜2文）
- "method": 採用した手法・アプローチ（1〜2文）
- "key_result": 主要な結果・発見（1〜2文）
- "limitation": 限界・今後の課題（1〜2文）
- "summary": 上記4つを1段落にまとめた総合要約（3〜5文）

【各部の要約】
{}"#,
        title_line, combined
    );
    let content = gemini_generate(&client, &key, &model, &reduce_prompt, true).await?;

    #[derive(serde::Deserialize)]
    struct BriefJson {
        #[serde(default)] problem: String,
        #[serde(default)] method: String,
        #[serde(default)] key_result: String,
        #[serde(default)] limitation: String,
        #[serde(default)] summary: String,
    }
    let bj: BriefJson = serde_json::from_str(&content).ok()?;
    if bj.summary.is_empty() { return None; }

    Some(PaperBrief {
        problem: bj.problem,
        method: bj.method,
        key_result: bj.key_result,
        limitation: bj.limitation,
        summary: bj.summary,
        source: "gemini".into(),
    })
}

/// トーン別の創作指示文を返す
fn tone_instruction(tone: &str) -> &'static str {
    match tone {
        "少年マンガ" => "熱血・友情・努力・成長のトーンで描く。研究者を若き天才ライバルとして設定し、台詞は短く感情的に。「諦めるな！」「これが俺たちの答えだ！」のような熱い表現を使う。",
        "SF" => "SF 的・宇宙規模の視点で描く。分子・タンパク質を異星人や機械生命体として擬人化。冷静で知的、宇宙の神秘を感じさせるトーン。",
        "社会派" => "社会問題・医療・がん患者の視点を前面に出す。研究の社会的インパクトを中心に据え、患者・医師・家族の感情を描く。問題提起を大切に。",
        "ホラー" => "細胞の異変・がん化・制御不能な分子の恐怖を描く。静かで不気味なトーン。日常の中に忍び込む恐怖、科学が解明できない「何か」の存在感。",
        "恋愛" => "分子・タンパク質を擬人化し「本来いるべき場所を離れた逸脱者」を禁じられた恋として描く。甘くせつなく、科学的真実を純愛の比喩で表現する。",
        _ => "客観的かつ分かりやすいポップサイエンスのトーンで描く。専門知識がない読者にも伝わるよう平易に。",
    }
}

/// C1+C2+C3 統合 Gemini 実装 — paper_brief + tone → 完全 MangaStory
async fn try_gemini_narrate(
    brief: &PaperBrief,
    title: Option<&str>,
    manga_tone: Option<&str>,
) -> Option<PaperOutlineResponse> {
    let key = std::env::var("GEMINI_API_KEY").ok()?;
    if key.trim().is_empty() { return None; }
    let model = std::env::var("GEMINI_MODEL").unwrap_or_else(|_| "gemini-2.5-flash".into());
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build().ok()?;
    let title_line = title.map(|t| format!("論文タイトル: {}\n", t)).unwrap_or_default();
    let tone = manga_tone.unwrap_or("ポップサイエンス");
    let tone_instr = tone_instruction(tone);
    let prompt = format!(
        r#"あなたは学術論文を漫画化する編集者です。以下の論文要約を元に、指定トーンで漫画企画書を日本語で作成してください。
厳密なJSONのみ出力（前後に説明文・マークダウン記号なし）。以下の全キーを含めること:

- "theme_line": 漫画のテーマを一行で（30文字以内）
- "characters": 2〜4名の配列 [{{"name":"名前","role":"役割（主役/ライバル等）","description":"外見・性格・科学的意味20文字"}}]
- "synopsis": 3幕構成の粗筋（日本語、150〜300文字。第1幕→第2幕→第3幕と明示）
- "outline_markdown": Markdownの構成案（見出しと箇条書き、4〜8行）
- "panel_beats": ちょうど4要素の string 配列（導入→対比→核→余韻。各30〜60文字）

【漫画トーン: {}】
{}

{}【論文要約】
問題: {}
手法: {}
結果: {}
限界: {}
総括: {}"#,
        tone, tone_instr, title_line,
        brief.problem, brief.method, brief.key_result, brief.limitation, brief.summary
    );
    let content = gemini_generate(&client, &key, &model, &prompt, true).await?;
    tracing::info!("[C3] Gemini 生レスポンス先頭200文字: {}", &content.chars().take(200).collect::<String>());
    let outline: OutlineJson = serde_json::from_str(&content).ok()?;
    if outline.panel_beats.is_empty() { return None; }
    Some(PaperOutlineResponse {
        ok: true,
        message: "ok".into(),
        source: "gemini".into(),
        outline_markdown: outline.outline_markdown,
        panel_beats: outline.panel_beats,
        theme_line: outline.theme_line,
        characters: outline.characters,
        synopsis: outline.synopsis,
        manga_tone: Some(tone.to_string()),
    })
}

/// B3 OpenAI 実装 — Map(各チャンクを要約) → Reduce(全要約を集約)
async fn try_openai_summarize(chunks: &[String], title: Option<&str>) -> Option<PaperBrief> {
    let key = std::env::var("OPENAI_API_KEY").ok()?;
    if key.trim().is_empty() {
        return None;
    }
    let model = std::env::var("OPENAI_MODEL").unwrap_or_else(|_| "gpt-4o-mini".into());
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .ok()?;

    // ── Map フェーズ: 各チャンクから要点を抽出 ──────────────────────────
    // 【なぜ並列化しないか（MVP）】
    // tokio::join_all を使えば並列化できるが、OpenAI のレート制限（RPM/TPM）で
    // 429 を受けやすくなる。チャンク数が少ない MVP では直列で十分。
    let mut chunk_summaries: Vec<String> = Vec::new();
    for chunk in chunks.iter().take(8) {  // 最大8チャンク（コスト制限）
        let prompt = format!(
            "以下の論文抜粋から、問題・手法・結果・限界の要点を日本語で2〜4文で抽出してください。\
            マークダウンや説明文は不要。要点のみ箇条書きで。\n\n{}", chunk
        );
        let body = serde_json::json!({
            "model": model,
            "messages": [{ "role": "user", "content": prompt }],
            "max_tokens": 300,
        });
        let res = client
            .post("https://api.openai.com/v1/chat/completions")
            .header("Authorization", format!("Bearer {}", key))
            .json(&body)
            .send()
            .await
            .ok()?;
        if !res.status().is_success() {
            tracing::warn!("B3 map chunk: http {}", res.status());
            continue;
        }
        let parsed: OpenAiChatResponse = res.json().await.ok()?;
        if let Some(c) = parsed.choices.first() {
            chunk_summaries.push(c.message.content.trim().to_string());
        }
    }

    if chunk_summaries.is_empty() {
        return None;
    }

    // ── Reduce フェーズ: チャンク要約を構造化 brief に集約 ──────────────
    let combined = chunk_summaries.join("\n\n---\n\n");
    let title_line = title.map(|t| format!("論文タイトル: {}\n\n", t)).unwrap_or_default();
    let reduce_prompt = format!(
        r#"{}以下は論文各部の要約です。これを統合し、厳密なJSONのみを出力してください。
キーは次の5つ（すべて日本語で）:
- "problem": 解こうとしている問題・ギャップ（1〜2文）
- "method": 採用した手法・アプローチ（1〜2文）
- "key_result": 主要な結果・発見（1〜2文）
- "limitation": 限界・今後の課題（1〜2文）
- "summary": 上記4つを1段落にまとめた総合要約（3〜5文）

【各部の要約】
{}"#,
        title_line, combined
    );
    let reduce_body = serde_json::json!({
        "model": model,
        "messages": [{ "role": "user", "content": reduce_prompt }],
        "response_format": { "type": "json_object" },
        "max_tokens": 800,
    });
    let reduce_res = client
        .post("https://api.openai.com/v1/chat/completions")
        .header("Authorization", format!("Bearer {}", key))
        .json(&reduce_body)
        .send()
        .await
        .ok()?;
    if !reduce_res.status().is_success() {
        tracing::warn!("B3 reduce: http {}", reduce_res.status());
        return None;
    }
    let reduce_parsed: OpenAiChatResponse = reduce_res.json().await.ok()?;
    let content = reduce_parsed.choices.first()?.message.content.trim();

    #[derive(serde::Deserialize)]
    struct BriefJson {
        #[serde(default)] problem: String,
        #[serde(default)] method: String,
        #[serde(default)] key_result: String,
        #[serde(default)] limitation: String,
        #[serde(default)] summary: String,
    }
    let bj: BriefJson = serde_json::from_str(content).ok()?;
    if bj.summary.is_empty() {
        return None;
    }

    Some(PaperBrief {
        problem: bj.problem,
        method: bj.method,
        key_result: bj.key_result,
        limitation: bj.limitation,
        summary: bj.summary,
        source: "openai".into(),
    })
}

// ─────────────────────────────────────────────────────────────────────────────
// C3 Name Generate — paper_brief → MangaNameStory
//
// 【なぜ入力を brief に変えるか】
//   raw text は最大 80k 文字だが、brief は〜1000 文字に収まる。
//   B1-B3 が「論文の論理構造を抽出」した後なので、LLM は「何をどう物語るか」
//   に集中でき、コマ割りの品質が向上する。
// ─────────────────────────────────────────────────────────────────────────────

/// C3: paper_brief と title から OpenAI ネームを生成する（失敗時 None）
async fn try_openai_narrate(
    brief: &PaperBrief,
    title: Option<&str>,
    manga_tone: Option<&str>,
) -> Option<PaperOutlineResponse> {
    let key = std::env::var("OPENAI_API_KEY").ok()?;
    if key.trim().is_empty() {
        return None;
    }
    let model = std::env::var("OPENAI_MODEL").unwrap_or_else(|_| "gpt-4o-mini".into());
    let title_line = title.map(|t| format!("論文タイトル: {}\n", t)).unwrap_or_default();
    let tone = manga_tone.unwrap_or("ポップサイエンス");
    let tone_instr = tone_instruction(tone);
    let prompt = format!(
        r#"学術論文を漫画化する編集者として、以下の論文要約から{tone}スタイルの漫画企画書を日本語で作成してください。
厳密なJSONのみを出力。キー: "theme_line"(一行テーマ), "characters"(配列[name,role,description]), "synopsis"(粗筋), "outline_markdown"(Markdown), "panel_beats"(4要素配列)

【トーン指示】{tone_instr}
{title_line}
【論文要約】問題:{problem} 手法:{method} 結果:{result} 総括:{summary}"#,
        tone=tone, tone_instr=tone_instr, title_line=title_line,
        problem=brief.problem, method=brief.method, result=brief.key_result, summary=brief.summary
    );

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .ok()?;
    let body = serde_json::json!({
        "model": model,
        "messages": [{ "role": "user", "content": prompt }],
        "response_format": { "type": "json_object" },
    });
    let res = client
        .post("https://api.openai.com/v1/chat/completions")
        .header("Authorization", format!("Bearer {}", key))
        .json(&body)
        .send()
        .await
        .ok()?;
    if !res.status().is_success() {
        tracing::warn!("C3 narrate: http {}", res.status());
        return None;
    }
    let parsed: OpenAiChatResponse = res.json().await.ok()?;
    let content = parsed.choices.first()?.message.content.trim();
    let outline: OutlineJson = serde_json::from_str(content).ok()?;
    if outline.panel_beats.is_empty() {
        return None;
    }
    Some(PaperOutlineResponse {
        ok: true,
        message: "ok".into(),
        source: "openai".into(),
        outline_markdown: outline.outline_markdown,
        panel_beats: outline.panel_beats,
        theme_line: outline.theme_line,
        characters: outline.characters,
        synopsis: outline.synopsis,
        manga_tone: Some(tone.to_string()),
    })
}

/// C3 モック: brief から4拍を直接組み立てる（OpenAI 不要）
fn mock_narrate(brief: &PaperBrief) -> PaperOutlineResponse {
    let excerpt: String = brief.summary.chars().take(300).collect();
    PaperOutlineResponse {
        ok: true,
        message: "ok".into(),
        source: "mock".into(),
        theme_line: Some(format!("研究の最前線: {}", brief.key_result.chars().take(20).collect::<String>())),
        characters: vec![],
        synopsis: Some(format!(
            "第1幕: {}\n第2幕: {}\n第3幕: {}",
            brief.problem.chars().take(80).collect::<String>(),
            brief.method.chars().take(80).collect::<String>(),
            brief.key_result.chars().take(80).collect::<String>(),
        )),
        manga_tone: None,
        outline_markdown: format!(
            "## 研究マンガ ネーム案（モック）\n\n> {}\n\n\
             1. **導入** — {}\n\
             2. **対比** — 既研究との違い・ギャップ\n\
             3. **核** — {}\n\
             4. **余韻** — {}",
            excerpt,
            brief.problem.chars().take(80).collect::<String>(),
            brief.key_result.chars().take(80).collect::<String>(),
            brief.limitation.chars().take(80).collect::<String>(),
        ),
        panel_beats: vec![
            format!("導入: {}", brief.problem.chars().take(60).collect::<String>()),
            "対比: 既研究との差分・未解決問題".into(),
            format!("核: {}", brief.key_result.chars().take(60).collect::<String>()),
            format!("余韻: {}", brief.limitation.chars().take(60).collect::<String>()),
        ],
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// run_pipeline — B1→B2→B3→C3 の完全パイプライン
// ─────────────────────────────────────────────────────────────────────────────

/// DB ヘルパー: current_stage を更新する
async fn update_stage(pool: &sqlx::PgPool, job_id: Uuid, stage: &str) {
    if let Err(e) = sqlx::query(
        "UPDATE ai_jobs SET current_stage=$1, updated_at=NOW() WHERE id=$2"
    )
    .bind(stage)
    .bind(job_id)
    .execute(pool)
    .await
    {
        tracing::warn!("[job {}] stage update '{}' 失敗: {}", job_id, stage, e);
    }
}

/// DB ヘルパー: artifact を inline JSONB で保存する
async fn save_artifact(
    pool: &sqlx::PgPool,
    job_id: Uuid,
    stage: &str,
    artifact_type: &str,
    data: &serde_json::Value,
    model: &str,
) {
    if let Err(e) = sqlx::query(
        r#"INSERT INTO ai_artifacts (job_id, stage, artifact_type, artifact_inline, model_used)
           VALUES ($1, $2, $3, $4, $5)"#,
    )
    .bind(job_id)
    .bind(stage)
    .bind(artifact_type)
    .bind(data)
    .bind(model)
    .execute(pool)
    .await
    {
        tracing::warn!("[job {}] artifact save '{}' 失敗: {}", job_id, stage, e);
    }
}

/// バックグラウンドパイプライン処理（B1→B2→B3→C3）
///
/// 【エラー方針】
///   各ステージはベストエフォート。B1-B3 が失敗しても生テキストで C3 にフォールバック。
///   致命的な失敗（C3 artifact 保存失敗）のみ status='failed' にする。
async fn run_pipeline(
    pool: sqlx::PgPool,
    job_id: Uuid,
    text: String,
    title: Option<String>,
    manga_tone: Option<String>,
) {
    // ── API キー診断ログ ────────────────────────────────────────────────
    let has_gemini = std::env::var("GEMINI_API_KEY")
        .map(|k| !k.trim().is_empty())
        .unwrap_or(false);
    let has_openai = std::env::var("OPENAI_API_KEY")
        .map(|k| !k.trim().is_empty())
        .unwrap_or(false);
    tracing::info!("[job {}] pipeline start — gemini_key={} openai_key={}", job_id, has_gemini, has_openai);

    // ── status → running ────────────────────────────────────────────────
    if let Err(e) = sqlx::query(
        "UPDATE ai_jobs SET status='running', current_stage='B1_segment', started_at=NOW(), updated_at=NOW() WHERE id=$1"
    )
    .bind(job_id)
    .execute(&pool)
    .await
    {
        tracing::error!("[job {}] status→running 更新失敗: {}", job_id, e);
        return;
    }

    // ── B1: セクション分割 ──────────────────────────────────────────────
    // 外部 API なし、純粋 Rust で完結する。失敗はありえないが、
    // 結果が空なら全文 1 セクションとして後続に渡す（b1_segment 内で保証）。
    let sections = b1_segment(&text);
    let section_json = serde_json::json!(
        sections.iter().map(|s| serde_json::json!({
            "heading": s.heading,
            "body_len": s.body.len(),
        })).collect::<Vec<_>>()
    );
    save_artifact(&pool, job_id, "B1_segment", "document_sections", &section_json, "rule").await;
    tracing::info!("[job {}] B1 完了: {} セクション", job_id, sections.len());

    // ── B2: チャンク分割 ────────────────────────────────────────────────
    update_stage(&pool, job_id, "B2_chunk").await;
    let chunks = b2_chunk(&sections);
    let chunk_json = serde_json::json!({
        "count": chunks.len(),
        "avg_len": chunks.iter().map(|c| c.len()).sum::<usize>() / chunks.len().max(1),
    });
    save_artifact(&pool, job_id, "B2_chunk", "chunks_meta", &chunk_json, "rule").await;
    tracing::info!("[job {}] B2 完了: {} チャンク", job_id, chunks.len());

    // ── B3: 要約（Map-Reduce） ──────────────────────────────────────────
    update_stage(&pool, job_id, "B3_summarize").await;
    let brief = b3_summarize(&chunks, title.as_deref()).await;
    let brief_json = serde_json::to_value(&brief).unwrap_or(serde_json::Value::Null);
    save_artifact(&pool, job_id, "B3_summarize", "paper_brief", &brief_json, &brief.source).await;
    tracing::info!("[job {}] B3 完了: source={}", job_id, brief.source);

    // ── C3: ネーム生成 ──────────────────────────────────────────────────
    // 【なぜ brief を入力にするか】
    // raw text（最大 80k 文字）ではなく B3 が抽出した構造化要約（〜1k 文字）を
    // 渡すことで、LLM は「何を物語るか」に集中でき品質・コストが改善する。
    update_stage(&pool, job_id, "C3_name_generate").await;
    let tone_ref = manga_tone.as_deref();
    let result = if let Some(r) = try_gemini_narrate(&brief, title.as_deref(), tone_ref).await {
        r
    } else if let Some(r) = try_openai_narrate(&brief, title.as_deref(), tone_ref).await {
        r
    } else {
        mock_narrate(&brief)
    };

    let artifact_json = serde_json::json!({
        "theme_line": result.theme_line,
        "characters": result.characters,
        "synopsis": result.synopsis,
        "manga_tone": result.manga_tone,
        "outline_markdown": result.outline_markdown,
        "panel_beats": result.panel_beats,
        "source": result.source,
    });

    // 最終成果物を ai_artifacts に保存（v_job_name_result ビューの参照先）
    let artifact_id: Option<Uuid> = sqlx::query_scalar(
        r#"INSERT INTO ai_artifacts
            (job_id, stage, artifact_type, artifact_inline, model_used, schema_version)
           VALUES ($1, 'C3_name_generate', 'manga_name_story', $2, $3, '0.1')
           RETURNING id"#,
    )
    .bind(job_id)
    .bind(&artifact_json)
    .bind(&result.source)
    .fetch_one(&pool)
    .await
    .map_err(|e| tracing::error!("[job {}] C3 artifact insert: {}", job_id, e))
    .ok();

    // ── 完了 or 失敗 ──────────────────────────────────────────────────────
    let final_status = if artifact_id.is_some() { "completed" } else { "failed" };
    let error_msg: Option<&str> = if artifact_id.is_none() {
        Some("C3 artifact の保存に失敗しました。")
    } else {
        None
    };

    if let Err(e) = sqlx::query(
        "UPDATE ai_jobs SET status=$1, current_stage=NULL, completed_at=NOW(), updated_at=NOW(), error_message=$2 WHERE id=$3"
    )
    .bind(final_status)
    .bind(error_msg)
    .bind(job_id)
    .execute(&pool)
    .await
    {
        tracing::error!("[job {}] 最終ステータス更新失敗: {}", job_id, e);
    }

    tracing::info!("[job {}] パイプライン完了: status={} source={}", job_id, final_status, result.source);
}

/// GET /api/ai/jobs/:id — ポーリング用ステータス取得
///
/// 【フロー】
///   1. ai_jobs で status / current_stage を取得
///   2. v_job_name_result ビューで最終成果物を JOIN
///   3. completed なら story_json を含めて返す
pub async fn get_job_status(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> impl IntoResponse {
    // 【なぜ query() を使うか】
    // sqlx::query!() マクロはビルド時に DB への接続が必要（コンパイル時検査）。
    // Docker ビルド環境（Render など）では DB に繋がらないため、
    // ランタイム検査の sqlx::query() を使う。
    #[derive(sqlx::FromRow)]
    struct JobRow {
        status: String,
        current_stage: Option<String>,
        error_message: Option<String>,
        story_json: Option<serde_json::Value>,
        story_key: Option<String>,
        model_used: Option<String>,
    }

    let row = sqlx::query_as::<_, JobRow>(
        r#"
        SELECT
            j.status,
            j.current_stage,
            j.error_message,
            r.story_json,
            r.story_key,
            r.model_used
        FROM ai_jobs j
        LEFT JOIN v_job_name_result r ON r.job_id = j.id
        WHERE j.id = $1
        "#,
    )
    .bind(id)
    .fetch_optional(&state.pool)
    .await;

    match row {
        Ok(Some(r)) => (
            StatusCode::OK,
            Json(JobStatusResponse {
                ok: true,
                job_id: id,
                status: r.status,
                current_stage: r.current_stage,
                error_message: r.error_message,
                story_json: r.story_json,
                story_key: r.story_key,
                model_used: r.model_used,
            }),
        )
            .into_response(),
        Ok(None) => (
            StatusCode::NOT_FOUND,
            Json(JobStatusResponse {
                ok: false,
                job_id: id,
                status: "not_found".into(),
                current_stage: None,
                error_message: Some("指定されたジョブが見つかりません。".into()),
                story_json: None,
                story_key: None,
                model_used: None,
            }),
        )
            .into_response(),
        Err(e) => {
            tracing::error!("get_job_status: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(JobStatusResponse {
                    ok: false,
                    job_id: id,
                    status: "error".into(),
                    current_stage: None,
                    error_message: Some("DB エラーが発生しました。".into()),
                    story_json: None,
                    story_key: None,
                    model_used: None,
                }),
            )
                .into_response()
        }
    }
}
