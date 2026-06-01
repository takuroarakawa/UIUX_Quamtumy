# AI オーケストレーター（Architect → Coder → Reviewer）

寝ている間に **Rust の叩き台** を `generated/run_*/src/lib.rs` に書き出すための簡易スクリプトです。

## セットアップ

```powershell
cd tools/ai-orchestrator
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # API キーを記入
```

## 実行

```powershell
# OpenAI（既定）
$env:OPENAI_API_KEY="sk-..."
python orchestrator.py --task "Rust で固定容量の LRU キャッシュを実装"

# Anthropic
$env:AI_PROVIDER="anthropic"
$env:ANTHROPIC_API_KEY="sk-ant-..."
python orchestrator.py --task-file ../../my_task.md --max-iterations 8
```

成果物: `generated/run_<UTC時刻>/` に `src/lib.rs`・`Cargo.toml`・`transcript.md`（全会話ログ）。

## 注意

- **API 課金**が発生します。`--max-iterations` で上限を調整してください。
- Reviewer が `REVIEW: APPROVED` と書かないとループが続きます（プロンプトで最終行を固定）。
- 生成コードは**必ず人間がビルド・レビュー**してください（自律ループは補助です）。

設計メモは [../../docs/ORCHESTRATOR.md](../../docs/ORCHESTRATOR.md)。
