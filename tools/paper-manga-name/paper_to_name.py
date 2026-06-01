"""
Dr. CANVAS — paper_to_name.py
Academic paper → Manga Name JSON  (manga-name-page.schema.json compatible)

Usage:
  python paper_to_name.py --file paper.txt [--pages 3] [--lang en] [--model llama3.2]
  python paper_to_name.py --text "..." [--lang ja] [--quality]
  python paper_to_name.py --interactive

Output:
  Saves to current_story.json by default (viewer.html polls this file).
  Use --out - for stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────

OLLAMA_BASE    = "http://localhost:11434"
DEFAULT_MODEL  = "llama3.2"
QUALITY_MODEL  = "llama3.1"
DEFAULT_OUT    = "current_story.json"
MAX_RETRIES    = 2
BEATS_JA       = ["起", "承", "転", "結"]
BEATS_EN       = ["setup", "development", "twist", "resolution"]
SUPPORTED_LANG = ("en", "ja", "auto")

# ── Character config (globally-usable names) ──────────────────────────────────

CHAR_CFG: dict[str, dict[str, str]] = {
    "en": {
        "char1_name":         "Dr. Kenji",
        "char1_personality":  "passionate, exclamatory, loves dramatic metaphors",
        "char1_speech":       "uses '!' often, speaks in bursts",
        "char1_appearance":   "middle-aged, disheveled hair, always holds chalk",
        "char2_name":         "Asst. Rei",
        "char2_personality":  "calm, precise, analytical",
        "char2_speech":       "translates jargon into everyday analogies",
        "char2_appearance":   "young, neat, glasses",
    },
    "ja": {
        "char1_name":         "博士",
        "char1_personality":  "情熱的・断定口調（〜だ！〜ぞ！）",
        "char1_speech":       "専門用語を叫んだあと比喩に言い換える",
        "char1_appearance":   "中年・白衣・チョーク常備・癖っ毛",
        "char2_name":         "助手",
        "char2_personality":  "冷静・丁寧口調（〜ですね〜ということです）",
        "char2_speech":       "日常のたとえ話で翻訳する",
        "char2_appearance":   "若い・眼鏡・几帳面",
    },
}

GENRE_LIST = ["educational", "sci-fi", "fantasy", "slice-of-life",
              "thriller", "mystery", "adventure", "comedy"]
TONE_LIST  = ["lighthearted", "serious", "dramatic", "humorous", "philosophical"]

# ── CharConfig dataclass-like dict helper ──────────────────────────────────────

def make_char_config(lang: str, overrides: dict | None = None) -> dict:
    """
    デフォルトのキャラ設定に overrides を上書きして返す。
    overrides のキーは CHAR_CFG と同じ ('char1_name' 等)。
    追加で 'genre', 'tone', 'world_setting' も受け付ける。
    """
    cfg = dict(CHAR_CFG.get(lang, CHAR_CFG["en"]))
    cfg.setdefault("genre",         "educational")
    cfg.setdefault("tone",          "lighthearted")
    cfg.setdefault("world_setting", "")
    if overrides:
        for k, v in overrides.items():
            if v and v.strip():
                cfg[k] = v.strip()
    return cfg

# ── System prompt builder ──────────────────────────────────────────────────────

def build_system_prompt(lang: str, char_cfg: dict | None = None) -> str:
    c = char_cfg or make_char_config(lang)
    beats = "/".join(BEATS_JA if lang == "ja" else BEATS_EN)

    # 世界観・ジャンル・トーンのブロック
    world_block = ""
    if c.get("world_setting"):
        world_block = f"\n## World / Setting\n{c['world_setting']}\n"
    genre_line = f"Genre: {c.get('genre','educational')}  |  Tone: {c.get('tone','lighthearted')}"

    if lang == "ja":
        return f"""\
あなたは「Dr. CANVAS」の脚本AIです。
学術論文を、初心者向けのマンガネーム（構成案）に変換します。
{genre_line}
{world_block}
## キャラクター
- 【{c["char1_name"]}】：{c["char1_personality"]}。口調：{c["char1_speech"]}。外見：{c["char1_appearance"]}
- 【{c["char2_name"]}】：{c["char2_personality"]}。口調：{c["char2_speech"]}。外見：{c["char2_appearance"]}

## 絶対ルール（すべて守る）
1. **出力言語は日本語**。フィールド値はすべて日本語で書く。
2. **dialogue は必ず埋める**（空文字・null・プレースホルダー禁止）。
   - 偶数コマ→【{c["char1_name"]}】、奇数コマ→【{c["char2_name"]}】のように交互に。
   - 専門用語は必ず日常比喩（食べ物・スポーツ・乗り物・天気など）に置き換える。
3. **character_expression は必ず埋める**（例：「目を血走らせてチョークを振る」）。
4. **visual_description は絵コンテ指示として書く**（例：「研究室のコマ。{c["char1_name"]}が〜」）。
5. **source_text_ref.excerpt は論文テキストから必ず引用する**（空文字禁止）。
6. 出力は **JSONオブジェクト1つのみ**。```json マーカーや説明文は一切不要。

## JSONスキーマ（厳守）
{{
  "page_number": <int>,
  "layout_type": <"single"|"vertical_2"|"vertical_3"|"horizontal_2"|"grid_2x2"|"top_wide_bottom_two"|"left_tall_right_two">,
  "layout_rationale": "このレイアウトを選んだ理由",
  "panels": [
    {{
      "narrative_beat": <"{beats}">,
      "visual_description": "絵コンテ指示（空文字禁止）",
      "dialogue": "【{c["char1_name"]}】または【{c["char2_name"]}】のセリフ（空文字禁止）",
      "character_expression": "表情・感情の指示（空文字禁止）",
      "source_text_ref": {{
        "excerpt": "論文からの引用フレーズ（空文字禁止）",
        "location_label": "セクション名・段落など",
        "link_kind": <"verbatim"|"paraphrase"|"inspired_by">
      }}
    }}
  ]
}}

## コマ数→拍の対応
- 1コマ→["結"] layout:single
- 2コマ→["起","結"] layout:horizontal_2
- 3コマ→["起","承","結"] layout:vertical_3
- 4コマ→["起","承","転","結"] layout:grid_2x2
"""
    else:
        return f"""\
You are the script AI for "Dr. CANVAS" — converting academic papers into manga storyboards.
{genre_line}
{world_block}
## Characters
- [{c["char1_name"]}]: {c["char1_personality"]}. Speech: {c["char1_speech"]}. Appearance: {c["char1_appearance"]}
- [{c["char2_name"]}]: {c["char2_personality"]}. Speech: {c["char2_speech"]}. Appearance: {c["char2_appearance"]}

## Absolute Rules (follow ALL)
1. **Output language is English** for all field values.
2. **dialogue must never be empty** (no null, no placeholder, no empty string).
   - Even-indexed panels: [{c["char1_name"]}], odd-indexed: [{c["char2_name"]}].
   - Replace every technical term with an everyday analogy.
   - Write natural spoken English.
3. **character_expression must never be empty**.
4. **visual_description is a storyboard direction** (scene, composition, action).
5. **source_text_ref.excerpt must quote from the paper** — never empty.
6. Output **exactly one JSON object**. No fences, no explanation.

## JSON Schema (strict)
{{
  "page_number": <int>,
  "layout_type": <"single"|"vertical_2"|"vertical_3"|"horizontal_2"|"grid_2x2"|"top_wide_bottom_two"|"left_tall_right_two">,
  "layout_rationale": "Reason for this layout",
  "panels": [
    {{
      "narrative_beat": <"{beats}">,
      "visual_description": "Storyboard direction (never empty)",
      "dialogue": "[{c["char1_name"]}] or [{c["char2_name"]}] spoken line (never empty)",
      "character_expression": "Expression/emotion direction (never empty)",
      "source_text_ref": {{
        "excerpt": "Quote from the paper (never empty)",
        "location_label": "Section or position",
        "link_kind": <"verbatim"|"paraphrase"|"inspired_by">
      }}
    }}
  ]
}}

## Panel count → beat mapping
- 1 panel  → ["resolution"]  layout: single
- 2 panels → ["setup","resolution"]  layout: horizontal_2
- 3 panels → ["setup","development","resolution"]  layout: vertical_3
- 4 panels → ["setup","development","twist","resolution"]  layout: grid_2x2
"""
# ── Utilities ──────────────────────────────────────────────────────────────────

def _post(url: str, payload: dict, timeout: int = 180) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach Ollama API: {e}") from e


def check_ollama(model: str) -> None:
    try:
        _post(f"{OLLAMA_BASE}/api/show", {"name": model}, timeout=10)
    except RuntimeError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        print("  → Is Ollama running?  Try: ollama serve", file=sys.stderr)
        sys.exit(1)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def detect_lang(text: str) -> str:
    """Simple heuristic: count CJK characters."""
    cjk = sum(1 for ch in text if "\u3000" <= ch <= "\u9fff" or "\uff00" <= ch <= "\uffef")
    return "ja" if cjk / max(len(text), 1) > 0.05 else "en"

# ── Text splitting ─────────────────────────────────────────────────────────────

def split_into_chunks(text: str, n: int) -> list[str]:
    """Split paper text into n balanced chunks (paragraph-first, sentence fallback)."""
    text = text.strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) < 2:
        sents = [s.strip() for s in re.split(r"(?<=[.!?。．！？])\s+", text) if s.strip()]
        paras = sents if sents else [text]
    chunks: list[str] = []
    for i in range(n):
        s = (i * len(paras)) // n
        e = ((i + 1) * len(paras)) // n
        chunks.append("\n\n".join(paras[s:e]) or paras[min(i, len(paras) - 1)])
    return chunks

# ── JSON extraction & repair ───────────────────────────────────────────────────

def _repair_json(raw: str) -> str:
    """Fix common LLM JSON breakage patterns."""
    s = raw
    # Curly / typographic quotes → straight
    for bad, good in [("\u201c", '"'), ("\u201d", '"'), ("\u2018", "'"), ("\u2019", "'"), ("\uff02", '"')]:
        s = s.replace(bad, good)
    # Escape bare newlines inside string values
    def _fix_newlines(text: str) -> str:
        out, in_str, esc = [], False, False
        for ch in text:
            if esc: out.append(ch); esc = False; continue
            if ch == "\\": out.append(ch); esc = True; continue
            if ch == '"': in_str = not in_str; out.append(ch); continue
            if in_str and ch == "\n": out.append("\\n"); continue
            if in_str and ch == "\r": out.append("\\r"); continue
            out.append(ch)
        return "".join(out)
    s = _fix_newlines(s)
    # Trailing commas
    s = re.sub(r",\s*([}\]])", r"\1", s)
    # Remove junk like {"assistant":""} at start of string values
    s = re.sub(r'\{"[^"]+":"[^"]*"\}\s*', "", s)
    return s


def _extract_json(content: str, page_num: int) -> dict[str, Any]:
    cleaned = re.sub(r"```(?:json)?\s*|```", "", content).strip()
    for repaired in (False, True):
        src = _repair_json(cleaned) if repaired else cleaned
        s0 = src.find("{"); e0 = src.rfind("}") + 1
        if s0 != -1 and e0 > s0:
            try: return json.loads(src[s0:e0])
            except json.JSONDecodeError: pass
        for m in re.finditer(r"\{", src):
            s = m.start(); depth = 0
            for idx, ch in enumerate(src[s:], s):
                if ch == "{": depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try: return json.loads(src[s:idx + 1])
                        except json.JSONDecodeError: break
    raise ValueError(f"P{page_num}: No valid JSON found.\n---\n{content[:600]}")

# ── Validation ─────────────────────────────────────────────────────────────────

def _validate_page(page: dict) -> list[str]:
    errs: list[str] = []
    panels = page.get("panels", [])
    if not isinstance(panels, list) or not panels:
        return ["panels is empty"]
    for j, p in enumerate(panels):
        for key in ("visual_description", "dialogue", "character_expression"):
            val = p.get(key, "")
            if not isinstance(val, str) or not val.strip():
                errs.append(f"panels[{j}].{key} is empty")
        ref = p.get("source_text_ref", {})
        excerpt = ref.get("excerpt", "") if isinstance(ref, dict) else ""
        if not excerpt.strip():
            errs.append(f"panels[{j}].source_text_ref.excerpt is empty")
    return errs

# ── Page generation ────────────────────────────────────────────────────────────

def _build_user_prompt(page_num: int, total: int, chunk: str,
                       panels: int, lang: str, retry: int) -> str:
    beats = (BEATS_JA if lang == "ja" else BEATS_EN)
    beat_seq = beats[:panels] if panels <= 4 else (beats[:2] + [beats[1]] * (panels - 4) + beats[2:])
    beat_seq = beat_seq[:panels]
    retry_note = (
        "\n⚠ Previous attempt had empty dialogue / character_expression / excerpt. "
        "Fill ALL fields this time.\n" if retry > 0 else ""
    )
    return (
        f"{retry_note}"
        f"Page {page_num} of {total}. Panel count: {panels} "
        f"(beat sequence: {' → '.join(beat_seq)}).\n\n"
        f"## Paper excerpt for this page\n{chunk}\n\n"
        f"Output exactly one JSON object now."
    )


def generate_page(page_num: int, total: int, chunk: str,
                  panels: int, model: str, lang: str,
                  temperature: float = 0.72,
                  char_cfg: dict | None = None) -> dict[str, Any]:
    system = build_system_prompt(lang, char_cfg)
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        user_msg = _build_user_prompt(page_num, total, chunk, panels, lang, attempt)
        payload = {
            "model": model, "stream": False,
            "options": {"temperature": temperature + attempt * 0.07},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ],
        }
        label = f" (retry {attempt}/{MAX_RETRIES})" if attempt else ""
        _log(f"  [P{page_num}/{total}] {model}{label} generating…")
        t0 = time.time()
        resp = _post(f"{OLLAMA_BASE}/api/chat", payload)
        content: str = resp.get("message", {}).get("content", "")
        _log(f"    → {time.time()-t0:.1f}s  ({len(content)} chars)")
        try:
            obj = _extract_json(content, page_num)
        except ValueError as e:
            last_err = e; _log(f"    ✗ JSON: {e}"); continue
        obj["page_number"] = page_num
        errs = _validate_page(obj)
        if errs:
            last_err = ValueError(f"Validation: {errs}")
            _log(f"    ✗ {last_err}"); continue
        _log("    ✓ OK")
        return obj
    raise RuntimeError(f"P{page_num}: Failed after {MAX_RETRIES+1} attempts.\n{last_err}")

# ── Main conversion ────────────────────────────────────────────────────────────

def paper_to_name(text: str, total_pages: int = 3, panels_per_page: int = 4,
                  model: str = DEFAULT_MODEL, title: str = "Untitled",
                  lang: str = "en", char_cfg: dict | None = None) -> dict[str, Any]:
    check_ollama(model)
    if lang == "auto":
        lang = detect_lang(text)
        _log(f"  [lang] auto-detected → {lang}")
    resolved_cfg = make_char_config(lang, char_cfg)
    chunks = split_into_chunks(text, total_pages)
    pages = [generate_page(i + 1, total_pages, c, panels_per_page, model, lang, char_cfg=resolved_cfg)
             for i, c in enumerate(chunks)]
    return {"title": title, "lang": lang,
            "char_config": resolved_cfg,
            "pages": pages}

# ── Save the Cat ビート定義 ────────────────────────────────────────────────────

SAVE_THE_CAT_BEATS: list[dict[str, str]] = [
    {"id": "opening_image", "ja": "オープニングイメージ", "en": "Opening Image",
     "hint_ja": "世界観の最初の一コマ・研究の舞台を印象的に",
     "hint_en": "Opening scene that establishes the world"},
    {"id": "theme_stated",  "ja": "テーマ表明",          "en": "Theme Stated",
     "hint_ja": "論文の核心的問いや仮説を示すセリフ",
     "hint_en": "The paper's core question stated out loud"},
    {"id": "setup",         "ja": "セットアップ",         "en": "Set-Up",
     "hint_ja": "キャラクターと研究背景を紹介",
     "hint_en": "Characters and research background introduced"},
    {"id": "catalyst",      "ja": "カタリスト",           "en": "Catalyst",
     "hint_ja": "研究の引き金となった発見や問題が発生",
     "hint_en": "The triggering discovery or problem appears"},
    {"id": "debate",        "ja": "ディベート",           "en": "Debate",
     "hint_ja": "挑戦への葛藤・本当に解決できるのか？",
     "hint_en": "Internal conflict before committing to the research"},
    {"id": "break_into_2",  "ja": "研究への突入",         "en": "Break into Two",
     "hint_ja": "本格的な研究・実験へのコミット",
     "hint_en": "Fully commits to solving the problem"},
    {"id": "b_story",       "ja": "Bストーリー",          "en": "B Story",
     "hint_ja": "サポートキャラとの重要な会話・ヒントが得られる",
     "hint_en": "A key conversation with a supporting character"},
    {"id": "fun_and_games", "ja": "実験と展開",           "en": "Fun and Games",
     "hint_ja": "実験プロセス・データ収集・新発見が続く",
     "hint_en": "The research process unfolds with new discoveries"},
    {"id": "midpoint",      "ja": "中間の発見",           "en": "Midpoint",
     "hint_ja": "重要な中間発見・仮説が正しそうと確認",
     "hint_en": "A key intermediate discovery validates the approach"},
    {"id": "bad_guys",      "ja": "困難・障壁",           "en": "Bad Guys Close In",
     "hint_ja": "予期しない困難・矛盾するデータが出現",
     "hint_en": "Unexpected challenges and contradictory data appear"},
    {"id": "all_is_lost",   "ja": "危機",                 "en": "All Is Lost",
     "hint_ja": "最大の困難・研究が行き詰まる瞬間",
     "hint_en": "The darkest moment — research seems to fail"},
    {"id": "dark_night",    "ja": "内省・再考",           "en": "Dark Night of the Soul",
     "hint_ja": "振り返り・根本的な問い直し",
     "hint_en": "Deep reflection and reconsideration"},
    {"id": "break_into_3",  "ja": "解決の糸口",           "en": "Break into Three",
     "hint_ja": "新たな視点・突破口の発見",
     "hint_en": "A new perspective leads to the breakthrough"},
    {"id": "finale",        "ja": "フィナーレ",           "en": "Finale",
     "hint_ja": "研究成果を証明・問題が解決される",
     "hint_en": "Research findings proven and problem solved"},
    {"id": "final_image",   "ja": "最終イメージ",         "en": "Final Image",
     "hint_ja": "未来への展望・変化した世界観を示す締めのコマ",
     "hint_en": "Closing image showing the transformed world/outlook"},
]

def generate_script(text: str, total_pages: int = 6, panels_per_page: int = 4,
                    model: str = DEFAULT_MODEL, lang: str = "ja",
                    char_cfg: dict | None = None) -> dict[str, Any]:
    """Save the Cat 15ビートに基づく脚本を論文テキストから生成"""
    check_ollama(model)
    c = make_char_config(lang, char_cfg)

    beats_info = "\n".join(
        f'- {b["id"]}: {b["ja"] if lang=="ja" else b["en"]} — {b["hint_ja"] if lang=="ja" else b["hint_en"]}'
        for b in SAVE_THE_CAT_BEATS
    )

    if lang == "ja":
        system = f"""あなたはマンガ脚本家AIです。学術論文を「Save the Cat」15ビート構造でマンガ脚本に変換します。
キャラクター:
- 【{c['char1_name']}】{c['char1_personality']}。口調: {c['char1_speech']}
- 【{c['char2_name']}】{c['char2_personality']}。口調: {c['char2_speech']}
ジャンル: {c.get('genre','educational')} / トーン: {c.get('tone','lighthearted')}
世界観: {c.get('world_setting','研究室')}
JSONのみ出力してください。説明不要。"""
        user = f"""論文テキスト:
---
{text[:4000]}
---

上記論文を元に{total_pages}ページ×{panels_per_page}コマのマンガ脚本をSave the Catビートで生成してください。

ビート構造:
{beats_info}

出力JSON形式（全15ビートを必ず記述）:
{{
  "title": "キャッチーなタイトル",
  "premise": "一行あらすじ（研究の核心を劇的に一文で）",
  "beats": [
    {{
      "id": "opening_image",
      "scene": "シーン説明（場所・人物の配置・構図）",
      "dialogue": "[{c['char1_name']}] 台詞（または地の文ナレーション）",
      "visual": "ビジュアル演出（感情・アクション・効果線など）",
      "paper_ref": "論文の参照箇所（セクション名や図番号）"
    }},
    ...全15ビート
  ]
}}"""
    else:
        system = f"""You are a manga scriptwriter AI.
Convert academic papers into manga scripts using "Save the Cat" 15-beat structure.
Characters: {c['char1_name']} ({c['char1_personality']}) and {c['char2_name']} ({c['char2_personality']}).
Output valid JSON only."""
        user = f"""Paper text:
---
{text[:4000]}
---

Create a {total_pages}-page manga script using Save the Cat 15-beat structure.

Beat list:
{beats_info}

Output JSON (all 15 beats required):
{{
  "title": "Catchy title",
  "premise": "One-line dramatic premise",
  "beats": [
    {{"id":"opening_image","scene":"...","dialogue":"[{c['char1_name']}] ...","visual":"...","paper_ref":"..."}}
    ... (all 15 beats)
  ]
}}"""

    _log("脚本生成中 (Save the Cat)...")
    raw = _call_ollama(model=model, system=system, user=user, temperature=0.75)
    script = _extract_json(raw)

    if not script or "beats" not in script:
        _log("脚本JSON抽出失敗 — 空テンプレートで返します")
        script = {
            "title": "Untitled",
            "premise": "",
            "beats": [
                {"id": b["id"], "scene": "", "dialogue": "", "visual": "", "paper_ref": ""}
                for b in SAVE_THE_CAT_BEATS
            ],
        }

    # 欠損ビートを補完
    existing_ids = {b.get("id") for b in script.get("beats", [])}
    for b_def in SAVE_THE_CAT_BEATS:
        if b_def["id"] not in existing_ids:
            script["beats"].append({"id": b_def["id"], "scene": "", "dialogue": "", "visual": "", "paper_ref": ""})

    return script


def script_to_name(script: dict, total_pages: int = 6, panels_per_page: int = 4,
                   model: str = DEFAULT_MODEL, lang: str = "ja",
                   char_cfg: dict | None = None) -> dict[str, Any]:
    """脚本ビートをページごとのマンガネームに変換"""
    check_ollama(model)
    c = make_char_config(lang, char_cfg or script.get("char_config", {}))
    beats = script.get("beats", [])
    title = script.get("title", "Untitled")

    # ビートをページに均等分配
    beats_per_page = max(1, len(beats) // total_pages)
    pages: list[dict[str, Any]] = []

    for pi in range(total_pages):
        start = pi * beats_per_page
        end   = start + beats_per_page if pi < total_pages - 1 else len(beats)
        page_beats = beats[start:end]

        # ビートのテキストをページのチャンクとして渡す
        chunk = "\n\n".join(
            f"Beat: {b.get('id','')}\nScene: {b.get('scene','')}\n"
            f"Dialogue: {b.get('dialogue','')}\nVisual: {b.get('visual','')}"
            for b in page_beats
        )
        beat_ids = [b.get("id","") for b in page_beats]

        _log(f"P{pi+1}/{total_pages} 生成中 ({', '.join(beat_ids)})...")
        try:
            page = generate_page(pi + 1, total_pages, chunk, panels_per_page,
                                 model, lang, char_cfg=c)
            page["beat_ids"] = beat_ids
        except Exception as e:
            _log(f"P{pi+1} エラー: {e}")
            page = {
                "page_number":    pi + 1,
                "layout_type":    "grid_2x2",
                "layout_rationale": "",
                "beat_ids":       beat_ids,
                "panels":         [],
            }
        pages.append(page)

    return {
        "title":       title,
        "lang":        lang,
        "char_config": c,
        "script":      script,
        "pages":       pages,
    }

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Paper text → Dr. CANVAS Manga Name JSON  (Ollama-powered)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python paper_to_name.py --file paper.txt --lang en --pages 3\n"
            "  python paper_to_name.py --file paper.txt --lang ja --quality\n"
            "  python paper_to_name.py --text '...' --lang auto\n"
        ),
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--text",        help="Paper text as a string")
    src.add_argument("--file",        help="Path to .txt / .md paper file")
    src.add_argument("--interactive", action="store_true", help="Read from stdin")
    parser.add_argument("--pages",   type=int,  default=3,           help="Number of pages to generate (default:3)")
    parser.add_argument("--panels",  type=int,  default=4,           help="Panels per page 1-8 (default:4)")
    parser.add_argument("--model",   default=DEFAULT_MODEL,          help=f"Ollama model (default:{DEFAULT_MODEL})")
    parser.add_argument("--quality", action="store_true",            help=f"Use higher-quality model: {QUALITY_MODEL}")
    parser.add_argument("--lang",    default="en", choices=SUPPORTED_LANG,
                                                                     help="Output language: en / ja / auto (default:en)")
    parser.add_argument("--title",   default="Untitled",             help="Manga title")
    parser.add_argument("--out",     default=DEFAULT_OUT,            help=f"Output JSON file (default:{DEFAULT_OUT}, '-' for stdout)")
    parser.add_argument("--indent",  type=int,  default=2,           help="JSON indent width")
    args = parser.parse_args()

    if args.text:
        text = args.text
    elif args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    elif args.interactive:
        _log("Paste paper text. End with Ctrl+Z (Win) / Ctrl+D (Unix):")
        text = sys.stdin.read()
    else:
        parser.print_help(); sys.exit(0)

    model  = QUALITY_MODEL if args.quality else args.model
    panels = max(1, min(8, args.panels))
    _log(f"[Dr. CANVAS] model={model}  pages={args.pages}  panels/p={panels}  lang={args.lang}  out={args.out}")

    story  = paper_to_name(text=text, total_pages=args.pages, panels_per_page=panels,
                           model=model, title=args.title, lang=args.lang)
    result = json.dumps(story, ensure_ascii=False, indent=args.indent)

    if args.out == "-":
        sys.stdout.buffer.write((result + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(result)
        _log(f"[Dr. CANVAS] Saved → {args.out}  ({len(result):,} bytes)")


if __name__ == "__main__":
    main()
