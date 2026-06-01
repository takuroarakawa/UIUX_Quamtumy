#!/usr/bin/env python3
"""
Architect -> Coder -> Reviewer オーケストレーター
Reviewer が REVIEW: APPROVED を出すまで Coder にフィードバックを戻す。

環境変数:
  AI_PROVIDER=openai | anthropic  (既定: openai)
  OPENAI_API_KEY / ANTHROPIC_API_KEY
  OPENAI_MODEL (既定 gpt-4o-mini) / ANTHROPIC_MODEL (既定 claude-3-5-sonnet-20241022)

使用例:
  python orchestrator.py --task "Rust で LRU キャッシュを実装"
  python orchestrator.py --task-file ./task.md --max-iterations 8
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# --- プロンプト設計（役割を分離：各ステージは単一責任） ---

ARCHITECT_SYSTEM = """あなたはシニアソフトウェアアーキテクトです。
ユーザー要件を読み、Rust で実装するための**設計メモ**だけを書いてください。
出力は Markdown。以下を含めること:
- 目的と非目的（スコープ外）
- 公開 API（関数・型の名前案）
- エラー方針（Result / カスタムエラー）
- テスト観点（最低1つ）
日本語で簡潔に。"""

CODER_SYSTEM = """あなたは Rust の熟練実装者です。
与えられた設計とフィードバックに従い、**1つの lib.rs に収まる**完成コードを書いてください。
- `edition = "2021"` を想定
- `unwrap()` は避け、エラーは `Result` で表現
- 最後に `#[cfg(test)] mod tests` で最低1テスト
コードは必ず ```rust フェンスで囲むこと。"""

REVIEWER_SYSTEM = """あなたは厳格なコードレビュアーです。
Rust の安全性・エラー処理・テストの有無を確認する。
**応答の最後の行だけ**を次のどちらかにすること（大文字厳守）:
REVIEW: APPROVED
または
REVIEW: NEEDS_REVISION
その直前に、修正が必要な場合のみ具体的な指摘を箇条書きで書くこと。
APPROVED の場合は指摘を書かない。"""


def _provider() -> str:
    return os.environ.get("AI_PROVIDER", "openai").lower().strip()


def _call_openai(system: str, user: str) -> str:
    from openai import OpenAI

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI()
    r = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return (r.choices[0].message.content or "").strip()


def _call_anthropic(system: str, user: str) -> str:
    import anthropic

    model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    client = anthropic.Anthropic()
    r = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts: list[str] = []
    for block in r.content:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", ""))
    return "\n".join(parts).strip()


def call_llm(system: str, user: str) -> str:
    p = _provider()
    if p == "anthropic":
        return _call_anthropic(system, user)
    return _call_openai(system, user)


def extract_rust_blocks(text: str) -> list[str]:
    """```rust ... ``` をすべて抽出（複数あれば結合候補）。"""
    pattern = re.compile(r"```rust\n(.*?)```", re.DOTALL | re.IGNORECASE)
    return [m.group(1).strip() for m in pattern.finditer(text)]


def pick_best_rust(text: str) -> str:
    blocks = extract_rust_blocks(text)
    if not blocks:
        # フェンスなしなら全文を救済
        return text.strip()
    return max(blocks, key=len)


def is_approved(review_text: str) -> bool:
    tail = "\n".join(review_text.strip().splitlines()[-8:])
    return "REVIEW: APPROVED" in tail.upper()


def needs_revision(review_text: str) -> bool:
    if is_approved(review_text):
        return False
    tail = "\n".join(review_text.strip().splitlines()[-8:])
    return "NEEDS_REVISION" in tail.upper() or "REVIEW:" not in tail.upper()


def run_pipeline(task: str, max_iterations: int, out_root: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_root / f"run_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    src_dir = run_dir / "src"
    src_dir.mkdir(exist_ok=True)

    log_path = run_dir / "transcript.md"
    parts: list[str] = [f"# Orchestrator run `{ts}`\n", f"## Task\n\n{task}\n\n"]

    # 1) Architect
    spec = call_llm(ARCHITECT_SYSTEM, f"## 要件\n{task}")
    parts.append("## Architect\n\n" + spec + "\n\n")
    (run_dir / "SPEC.md").write_text(spec, encoding="utf-8")

    # 2) Coder (初回)
    code = call_llm(
        CODER_SYSTEM,
        f"## 設計\n{spec}\n\n## 指示\n上記設計に従い lib.rs 相当のコードを出力してください。",
    )
    parts.append("## Coder (initial)\n\n````\n" + code + "\n````\n\n")

    iteration = 0
    review = ""
    while iteration < max_iterations:
        iteration += 1
        review = call_llm(
            REVIEWER_SYSTEM,
            f"## 要件\n{task}\n\n## 設計メモ\n{spec}\n\n## 提出コード\n```rust\n{pick_best_rust(code)}\n```\n",
        )
        parts.append(f"## Reviewer (iter {iteration})\n\n{review}\n\n")
        log_path.write_text("".join(parts), encoding="utf-8")

        if is_approved(review):
            break
        if not needs_revision(review):
            review += "\n\nREVIEW: NEEDS_REVISION\n(フォーマット補正)"

        feedback = review
        code = call_llm(
            CODER_SYSTEM,
            f"## 設計\n{spec}\n\n## 前回コード\n```rust\n{pick_best_rust(code)}\n```\n\n"
            f"## レビューからの修正依頼\n{feedback}\n\n"
            "指摘をすべて反映した完全なコードを ```rust で出力してください。",
        )
        parts.append(f"## Coder (revision {iteration})\n\n````\n{code}\n````\n\n")

    final_rust = pick_best_rust(code)
    (src_dir / "lib.rs").write_text(final_rust, encoding="utf-8")
    cargo_toml = """[package]
name = "generated_crate"
version = "0.1.0"
edition = "2021"
"""
    (run_dir / "Cargo.toml").write_text(cargo_toml, encoding="utf-8")

    status = "APPROVED" if is_approved(review) else "MAX_ITERATIONS"
    parts.append(f"\n## Status: {status}\n")
    log_path.write_text("".join(parts), encoding="utf-8")

    readme = run_dir / "README.txt"
    readme.write_text(
        f"生成物: src/lib.rs\nステータス: {status}\n"
        f"レビュー最終行を確認し、未承認なら transcript.md を見て手で直してください。\n",
        encoding="utf-8",
    )
    return run_dir


def main() -> None:
    ap = argparse.ArgumentParser(description="Architect / Coder / Reviewer オーケストレーター")
    ap.add_argument("--task", type=str, help="実装したい内容（平文）")
    ap.add_argument("--task-file", type=Path, help="要件が書かれたファイル")
    ap.add_argument("--max-iterations", type=int, default=6)
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "generated",
        help="出力ルート（既定: tools/ai-orchestrator/generated）",
    )
    args = ap.parse_args()

    if args.task_file:
        task = args.task_file.read_text(encoding="utf-8")
    elif args.task:
        task = args.task
    else:
        print("ERROR: --task または --task-file を指定してください。", file=sys.stderr)
        sys.exit(2)

    if _provider() == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY が未設定です。", file=sys.stderr)
        sys.exit(1)
    if _provider() == "openai" and not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY が未設定です。", file=sys.stderr)
        sys.exit(1)

    out = run_pipeline(task.strip(), args.max_iterations, args.out)
    print(f"OK: 成果物は {out} にあります（src/lib.rs）")


if __name__ == "__main__":
    main()
