# 自律ループ・プロンプト設計（Architect / Coder / Reviewer）

## 役割の分離（単一責任）

| 役割 | 入力 | 出力 | 失敗しやすい点 |
|------|------|------|----------------|
| **Architect** | ユーザー要件 | 設計メモ（スコープ・API 案・エラー方針） | 実装まで書きすぎる |
| **Coder** | 設計 +（あれば）レビュー指摘 | ` ```rust ` 内のコード | `unwrap` だらけ |
| **Reviewer** | 要件 + 設計 + コード | 指摘 + **最終行 `REVIEW: APPROVED` または `REVIEW: NEEDS_REVISION`** | 曖昧な「まあ良い」 |

## ループの止め方（機械可読）

Reviewer の**最後の数行**に必ず次のいずれかを含めるよう指示する:

- `REVIEW: APPROVED` → ループ終了、ファイル書き出し
- `REVIEW: NEEDS_REVISION` → Coder に全文をフィードバックとして戻す

これにより **while の終了条件がパース可能**になる。

## リスクと対策

- **無限課金**: `--max-iterations` で上限（既定 6）。
- **品質**: 生成物は `cargo test` / `clippy` を必ず通す前提で、人間がマージする。
- **秘密情報**: `.env` にキー、リポジトリにコミットしない。

## 実装場所

- `tools/ai-orchestrator/orchestrator.py`
