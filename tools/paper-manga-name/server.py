"""
Dr. CANVAS — server.py
静的ファイル配信 + PDF/テキスト → マンガネーム生成 API

起動:
  python server.py          # port 5174
  python server.py --port 5174

エンドポイント:
  GET  /                    → viewer.html
  GET  /<file>              → 静的ファイル
  POST /api/generate        → PDF or テキスト → SSE で進捗ストリーム
  GET  /api/story           → current_story.json の内容
  GET  /api/status          → サーバー稼働確認
  GET  /api/sd-status       → Stable Diffusion (AUTOMATIC1111) 接続確認
  POST /api/generate-panel  → 指定パネルの画像をSD生成
  POST /api/generate-all    → 全パネルを順次SD生成
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import threading
import time
import traceback
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

# ── 設定 ──────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
STORY_FILE  = BASE_DIR / "current_story.json"
CONFIG_FILE = BASE_DIR / "drcanvas-config.json"
IMG_DIR     = BASE_DIR / "panel_images"
DEFAULT_PORT = 5174
ALLOWED_ORIGINS = ["http://127.0.0.1:5174", "http://localhost:5174",
                   "http://127.0.0.1:5173", "http://localhost:5173"]

# ── Stable Diffusion (AUTOMATIC1111) 統合 ────────────────────────────────────
SD_DEFAULT_URL = "http://127.0.0.1:7860"

def _load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

def _sd_url() -> str:
    return _load_config().get("sd_url", SD_DEFAULT_URL)

def _sd_available() -> bool:
    """AUTOMATIC1111 が起動しているか確認"""
    try:
        req = urllib.request.Request(f"{_sd_url()}/internal/ping", method="GET")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        try:
            req = urllib.request.Request(f"{_sd_url()}/sdapi/v1/progress", method="GET")
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception:
            return False

def _build_panel_prompt(panel: dict, char_cfg: dict,
                         lora_name: str = "", style_prompt: str = "") -> tuple[str, str]:
    """パネルデータからSD用プロンプトを生成"""
    visual   = panel.get("visual_description", "")
    expr     = panel.get("character_expression", "")
    beat     = panel.get("narrative_beat", "setup")
    c1_app   = (char_cfg or {}).get("char1_appearance", "")
    c2_app   = (char_cfg or {}).get("char2_appearance", "")
    c1_name  = (char_cfg or {}).get("char1_name", "")
    c2_name  = (char_cfg or {}).get("char2_name", "")
    world    = (char_cfg or {}).get("world_setting", "")

    beat_framing = {
        "setup":       "establishing shot, calm atmosphere, wide shot",
        "development": "medium shot, dynamic gesture, action pose, explaining",
        "twist":       "dramatic close-up, shocked expression, speed lines, impact",
        "resolution":  "medium shot, satisfied smile, warm soft lighting",
    }.get(beat, "")

    char_parts = []
    if c1_name and c1_app:
        char_parts.append(f"{c1_name}: {c1_app}")
    elif c1_app:
        char_parts.append(c1_app)
    if c2_name and c2_app:
        char_parts.append(f"{c2_name}: {c2_app}")
    elif c2_app:
        char_parts.append(c2_app)

    scene_parts = [
        style_prompt or "manga panel, black and white, ink illustration, detailed linework, hatching, professional manga art",
        visual,
        world,
        beat_framing,
        expr,
        ", ".join(char_parts),
        "masterpiece, best quality, clean lines, clear composition",
    ]
    pos = ", ".join(p for p in scene_parts if p and p.strip())
    if lora_name and lora_name.strip():
        pos = f"<lora:{lora_name.strip()}:0.85>, {pos}"

    neg = ("color, colored, photorealistic, 3d render, blurry, low quality, jpeg artifacts, "
           "nsfw, watermark, signature, text overlay, western comics style, bad anatomy, "
           "extra limbs, deformed")
    return pos, neg

def _generate_image_sd(prompt: str, neg: str,
                        width: int = 512, height: int = 768,
                        steps: int = 24, cfg_scale: float = 7.5,
                        sampler: str = "DPM++ 2M Karras") -> str | None:
    """SD txt2img API を呼び出し、base64 PNG を返す"""
    payload = json.dumps({
        "prompt":          prompt,
        "negative_prompt": neg,
        "width":           width,
        "height":          height,
        "steps":           steps,
        "cfg_scale":       cfg_scale,
        "sampler_name":    sampler,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{_sd_url()}/sdapi/v1/txt2img",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            result = json.loads(r.read())
            images = result.get("images", [])
            return images[0] if images else None
    except Exception as e:
        print(f"[SD] 生成エラー: {e}", flush=True)
        return None

def _save_panel_image(b64: str, page_idx: int, panel_idx: int) -> str:
    """base64画像をファイルに保存し、data URI を返す（JSONに格納するため）"""
    IMG_DIR.mkdir(exist_ok=True)
    import base64
    fname = IMG_DIR / f"P{page_idx+1}_{panel_idx+1}.png"
    fname.write_bytes(base64.b64decode(b64))
    return f"data:image/png;base64,{b64}"

# paper_to_name モジュールを同ディレクトリから import
sys.path.insert(0, str(BASE_DIR))
import paper_to_name as _ptn

# ── 生成状態（スレッド間共有） ────────────────────────────────────────────────
_lock   = threading.Lock()
_status = {"running": False, "log": [], "error": None}

def _reset():
    with _lock:
        _status["running"] = False
        _status["log"]     = []
        _status["error"]   = None

def _append_log(msg: str):
    with _lock:
        _status["log"].append(msg)

# paper_to_name の _log をフック
_orig_log = _ptn._log
def _hooked_log(msg: str):
    _append_log(msg)
    _orig_log(msg)
_ptn._log = _hooked_log

# ── マルチパート解析（依存なし） ────────────────────────────────────────────
def _parse_multipart(body: bytes, content_type: str) -> dict:
    """
    Robust multipart/form-data parser.
    Handles binary PDF data correctly — does NOT strip binary content.
    Returns {field_name: bytes}.
    """
    import re
    m = re.search(r'boundary=([^\s;,]+)', content_type)
    if not m:
        return {}
    boundary_raw = m.group(1).strip('"\'')
    first_delim  = b'--'     + boundary_raw.encode('latin-1')
    delim        = b'\r\n--' + boundary_raw.encode('latin-1')

    result: dict[str, bytes] = {}

    start = body.find(first_delim)
    if start < 0:
        return {}
    pos = start + len(first_delim)

    while pos < len(body):
        next2 = body[pos:pos + 2]
        if next2 == b'--':
            break          # 終端 boundary
        if next2 != b'\r\n':
            break          # malformed
        pos += 2           # \r\n をスキップ

        end = body.find(delim, pos)
        if end < 0:
            end = len(body)

        chunk   = body[pos:end]
        hdr_end = chunk.find(b'\r\n\r\n')
        if hdr_end < 0:
            pos = end + len(delim)
            continue

        headers = chunk[:hdr_end]
        value   = chunk[hdr_end + 4:]   # バイナリをそのまま保持

        nm = re.search(rb'name="([^"]+)"', headers)
        if nm:
            result[nm.group(1).decode('utf-8', errors='replace')] = value

        pos = end + len(delim)

    return result

# ── HTTP ハンドラ ─────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # アクセスログを抑制

    def _cors(self):
        origin = self.headers.get("Origin", "")
        allow  = origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[0]
        self.send_header("Access-Control-Allow-Origin", allow)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_PUT(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        if path == "/api/story":
            try:
                data = json.loads(body.decode("utf-8"))
                STORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                self._json(200, {"ok": True})
            except Exception as e:
                self._json(400, {"error": str(e)})
        elif path == "/api/sd-config":
            # SD設定（URL, LoRA名, スタイルプロンプト）を保存
            try:
                data = json.loads(body.decode("utf-8"))
                cfg = _load_config()
                for k in ("sd_url", "lora_name", "style_prompt"):
                    if k in data:
                        cfg[k] = data[k]
                _save_config(cfg)
                self._json(200, {"ok": True})
            except Exception as e:
                self._json(400, {"error": str(e)})
        else:
            self._json(404, {"error": "unknown endpoint"})

    def do_GET(self):
        path = urlparse(self.path).path

        # ── API ─────────────────────────────────────────────────────────
        if path == "/api/story":
            if STORY_FILE.exists():
                data = STORY_FILE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._cors()
                self.end_headers()
                self.wfile.write(data)
            else:
                self._json(404, {"error": "no story yet"})
            return

        if path == "/api/status":
            with _lock:
                s = dict(_status)
            self._json(200, s)
            return

        # ── SD接続確認 ─────────────────────────────────────────────────
        if path == "/api/sd-status":
            available = _sd_available()
            cfg = _load_config()
            self._json(200, {
                "available": available,
                "url":       cfg.get("sd_url", SD_DEFAULT_URL),
                "lora_name": cfg.get("lora_name", ""),
                "style_prompt": cfg.get("style_prompt", ""),
            })
            return

        # ── panel_images 静的配信 ─────────────────────────────────────
        if path.startswith("/panel_images/"):
            file_path = BASE_DIR / path.lstrip("/")
            if file_path.exists() and file_path.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self._cors()
                self.end_headers()
                self.wfile.write(file_path.read_bytes())
            else:
                self._json(404, {"error": "image not found"})
            return

        # ── 静的ファイル ─────────────────────────────────────────────────
        if path == "/" or path == "":
            path = "/viewer.html"

        file_path = BASE_DIR / path.lstrip("/")
        if file_path.exists() and file_path.is_file():
            mime, _ = mimetypes.guess_type(str(file_path))
            self.send_response(200)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self._cors()
            self.end_headers()
            self.wfile.write(file_path.read_bytes())
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/story":
            # PUT的なPOST: 編集済みストーリーを保存
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8"))
                STORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                self._json(200, {"ok": True})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return

        # ── 単一パネルをSD生成 ─────────────────────────────────────────
        if path == "/api/generate-panel":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                req_data = json.loads(body.decode("utf-8"))
            except Exception:
                self._json(400, {"error": "invalid JSON"}); return

            if not _sd_available():
                self._json(503, {"error": "Stable Diffusion が起動していません。AUTOMATIC1111 を起動してください。"}); return
            if not STORY_FILE.exists():
                self._json(404, {"error": "ストーリーデータがありません"}); return

            page_idx  = req_data.get("page_index", 0)
            panel_idx = req_data.get("panel_index", 0)
            cfg_saved = _load_config()
            lora_name    = req_data.get("lora_name", cfg_saved.get("lora_name", ""))
            style_prompt = req_data.get("style_prompt", cfg_saved.get("style_prompt", ""))

            story = json.loads(STORY_FILE.read_text(encoding="utf-8"))
            pages = story.get("pages", [])
            if page_idx >= len(pages):
                self._json(400, {"error": "ページ番号が範囲外"}); return
            panels = pages[page_idx].get("panels", [])
            if panel_idx >= len(panels):
                self._json(400, {"error": "パネル番号が範囲外"}); return

            panel    = panels[panel_idx]
            char_cfg = story.get("char_config", {})
            pos, neg = _build_panel_prompt(panel, char_cfg, lora_name, style_prompt)

            print(f"[SD] P{page_idx+1}-#{panel_idx+1} 生成開始...", flush=True)
            print(f"[SD] Prompt: {pos[:120]}...", flush=True)

            img_b64 = _generate_image_sd(pos, neg)
            if img_b64 is None:
                self._json(500, {"error": "SD生成に失敗しました"}); return

            data_uri = _save_panel_image(img_b64, page_idx, panel_idx)
            # ストーリーJSONに保存
            story["pages"][page_idx]["panels"][panel_idx]["generated_image"] = data_uri
            STORY_FILE.write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")

            print(f"[SD] P{page_idx+1}-#{panel_idx+1} 生成完了", flush=True)
            self._json(200, {"image": data_uri, "page_index": page_idx, "panel_index": panel_idx})
            return

        # ── 全パネルをSD生成（SSEストリーム） ─────────────────────────
        if path == "/api/generate-all":
            if not _sd_available():
                self._json(503, {"error": "Stable Diffusion が起動していません"}); return
            if not STORY_FILE.exists():
                self._json(404, {"error": "ストーリーデータがありません"}); return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            try:
                req_data = json.loads(body.decode("utf-8"))
            except Exception:
                req_data = {}

            cfg_saved    = _load_config()
            lora_name    = req_data.get("lora_name", cfg_saved.get("lora_name", ""))
            style_prompt = req_data.get("style_prompt", cfg_saved.get("style_prompt", ""))

            story    = json.loads(STORY_FILE.read_text(encoding="utf-8"))
            char_cfg = story.get("char_config", {})
            pages    = story.get("pages", [])

            # 総パネル数
            total = sum(len(p.get("panels", [])) for p in pages)

            # SSEストリームで進捗通知
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self._cors()
            self.end_headers()

            def sse(ev: str, data):
                msg = f"event: {ev}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                try:
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    pass

            done_count = 0
            for pi, page in enumerate(pages):
                for ni, panel in enumerate(page.get("panels", [])):
                    pos, neg = _build_panel_prompt(panel, char_cfg, lora_name, style_prompt)
                    sse("log", f"P{pi+1}-#{ni+1} 生成中... ({done_count+1}/{total})")
                    img_b64 = _generate_image_sd(pos, neg)
                    if img_b64:
                        data_uri = _save_panel_image(img_b64, pi, ni)
                        story["pages"][pi]["panels"][ni]["generated_image"] = data_uri
                        STORY_FILE.write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")
                        sse("panel_done", {"page_index": pi, "panel_index": ni, "image": data_uri})
                    else:
                        sse("panel_error", {"page_index": pi, "panel_index": ni})
                    done_count += 1

            sse("done", {"total": total, "generated": done_count})
            return

        # ── 脚本生成（Save the Cat / SSEストリーム） ──────────────────
        if path == "/api/generate-script":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                req_data = json.loads(body.decode("utf-8"))
            except Exception:
                self._json(400, {"error": "invalid JSON"}); return

            pdf_bytes = None
            text_input = req_data.get("text", "")
            if req_data.get("file_b64"):
                import base64
                try:
                    pdf_bytes = base64.b64decode(req_data["file_b64"])
                except Exception:
                    pass

            # Extract text from PDF if provided
            if pdf_bytes:
                try:
                    import fitz
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    text_input = "\n".join(p.get_text() for p in doc)
                    doc.close()
                except Exception as e:
                    self._json(500, {"error": f"PDF抽出エラー: {e}"}); return

            text_input = _ptn._trim_paper(text_input)
            if not text_input.strip():
                self._json(400, {"error": "テキストが空です"}); return

            total_pages  = int(req_data.get("total_pages", 6))
            panels       = int(req_data.get("panels", 4))
            lang         = req_data.get("lang", "ja")
            model        = req_data.get("model", _ptn.DEFAULT_MODEL)
            char_cfg_ovr = {k: req_data.get(k, "") for k in (
                "char1_name","char1_personality","char1_speech","char1_appearance",
                "char2_name","char2_personality","char2_speech","char2_appearance",
                "genre","tone","world_setting"
            )}

            # SSE stream
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self._cors()
            self.end_headers()

            def sse_script(ev, data):
                msg = f"event: {ev}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                try: self.wfile.write(msg.encode("utf-8")); self.wfile.flush()
                except Exception: pass

            orig = _ptn._log
            def hooked(msg):
                sse_script("log", msg)
                orig(msg)
            _ptn._log = hooked
            try:
                sse_script("log", "脚本生成開始...")
                script = _ptn.generate_script(
                    text=text_input, total_pages=total_pages,
                    panels_per_page=panels, model=model, lang=lang,
                    char_cfg=char_cfg_ovr,
                )
                # story JSONに保存
                if STORY_FILE.exists():
                    try:
                        current = json.loads(STORY_FILE.read_text(encoding="utf-8"))
                    except Exception:
                        current = {}
                else:
                    current = {}
                current["script"]    = script
                current["title"]     = script.get("title", current.get("title","Untitled"))
                current["script_text"] = text_input[:2000]
                current.setdefault("char_config", _ptn.make_char_config(lang, char_cfg_ovr))
                STORY_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
                sse_script("done", {"script": script})
            except Exception as e:
                sse_script("error", str(e))
            finally:
                _ptn._log = orig
            return

        # ── 脚本→ネーム変換（SSEストリーム） ─────────────────────────
        if path == "/api/script-to-name":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                req_data = json.loads(body.decode("utf-8"))
            except Exception:
                self._json(400, {"error": "invalid JSON"}); return

            if not STORY_FILE.exists():
                self._json(404, {"error": "ストーリーデータがありません"}); return

            story   = json.loads(STORY_FILE.read_text(encoding="utf-8"))
            script  = req_data.get("script") or story.get("script")
            if not script:
                self._json(400, {"error": "脚本データがありません"}); return

            total_pages     = int(req_data.get("total_pages", 6))
            panels_per_page = int(req_data.get("panels", 4))
            lang    = req_data.get("lang", story.get("lang","ja"))
            model   = req_data.get("model", _ptn.DEFAULT_MODEL)
            char_cfg_ovr = req_data.get("char_config") or story.get("char_config") or {}

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self._cors()
            self.end_headers()

            def sse2(ev, data):
                msg = f"event: {ev}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                try: self.wfile.write(msg.encode("utf-8")); self.wfile.flush()
                except Exception: pass

            beats    = script.get("beats", [])
            bpp      = max(1, len(beats) // total_pages)
            pages_out = []

            for pi in range(total_pages):
                start      = pi * bpp
                end_idx    = start + bpp if pi < total_pages - 1 else len(beats)
                page_beats = beats[start:end_idx]
                beat_ids   = [b.get("id","") for b in page_beats]

                chunk = "\n\n".join(
                    f"Beat: {b.get('id','')}\nScene: {b.get('scene','')}\n"
                    f"Dialogue: {b.get('dialogue','')}\nVisual: {b.get('visual','')}"
                    for b in page_beats
                )

                sse2("progress", {"page": pi+1, "total": total_pages, "beats": beat_ids})
                try:
                    page = _ptn.generate_page(
                        pi+1, total_pages, chunk, panels_per_page,
                        model, lang, char_cfg=_ptn.make_char_config(lang, char_cfg_ovr)
                    )
                    page["beat_ids"] = beat_ids
                except Exception as e:
                    _log(f"P{pi+1} エラー: {e}")
                    page = {"page_number": pi+1, "layout_type":"grid_2x2",
                            "beat_ids": beat_ids, "panels":[]}
                pages_out.append(page)
                sse2("page_done", {"page_index": pi, "page": page})

            story["pages"]  = pages_out
            story["script"] = script
            story["lang"]   = lang
            story.setdefault("char_config", _ptn.make_char_config(lang, char_cfg_ovr))
            STORY_FILE.write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")
            sse2("done", {"pages": len(pages_out)})
            return

        # ── あらすじ生成（50文字以内） ─────────────────────────────────────
        if path == "/api/synopsis":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                req_data = json.loads(body.decode("utf-8"))
            except Exception:
                self._json(400, {"error": "invalid JSON"}); return

            title = req_data.get("title", "")
            text  = req_data.get("text", title)
            lang  = req_data.get("lang", "ja")
            model = req_data.get("model", _ptn.DEFAULT_MODEL)

            trimmed = _ptn._trim_paper(text)[:1500] if text else title
            prompt  = (
                f"次の学術論文の内容を、マンガのあらすじとして50文字以内の日本語で簡潔に表現してください。"
                f"返答はあらすじの文のみを出力し、余計な説明を加えないでください。\n\n論文: {trimmed or title}"
            ) if lang == "ja" else (
                f"Summarize the following academic paper as a manga synopsis in 50 characters or fewer in English. "
                f"Output only the synopsis sentence.\n\nPaper: {trimmed or title}"
            )

            try:
                import urllib.request as _ur
                req_body = json.dumps({
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                }).encode("utf-8")
                req_obj = _ur.Request(
                    f"http://127.0.0.1:11434/api/generate",
                    data=req_body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with _ur.urlopen(req_obj, timeout=60) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                synopsis = resp_data.get("response", "").strip()[:100]
                self._json(200, {"synopsis": synopsis})
            except Exception as e:
                self._json(500, {"error": f"Ollama エラー: {e}"}); return
            return

        # ── AI チャット（SSEストリーム） ──────────────────────────────────
        if path == "/api/chat":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                req_data = json.loads(body.decode("utf-8"))
            except Exception:
                self._json(400, {"error": "invalid JSON"}); return

            messages = req_data.get("messages", [])
            system   = req_data.get("system", "あなたはマンガ制作を支援するAIアシスタントです。")
            model    = req_data.get("model", _ptn.DEFAULT_MODEL)

            # SSEストリーム
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self._cors()
            self.end_headers()

            try:
                import urllib.request as _ur
                req_body = json.dumps({
                    "model": model,
                    "messages": [{"role": "system", "content": system}] + messages,
                    "stream": True,
                }, ensure_ascii=False).encode("utf-8")
                req_obj = _ur.Request(
                    "http://127.0.0.1:11434/api/chat",
                    data=req_body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with _ur.urlopen(req_obj, timeout=120) as resp:
                    for line in resp:
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line.decode("utf-8"))
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                self.wfile.write(f"data:{token}\n\n".encode("utf-8"))
                                self.wfile.flush()
                            if chunk.get("done"):
                                self.wfile.write(b"data:[DONE]\n\n")
                                self.wfile.flush()
                                break
                        except Exception:
                            continue
            except Exception as e:
                try:
                    self.wfile.write(f"data:[ERROR] {e}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    pass
            return

        if path != "/api/generate":
            self._json(404, {"error": "unknown endpoint"})
            return

        # 生成中なら拒否
        with _lock:
            if _status["running"]:
                self._json(409, {"error": "generation already running"})
                return
            _status["running"] = True
            _status["log"]     = []
            _status["error"]   = None

        length       = int(self.headers.get("Content-Length", 0))
        content_type = self.headers.get("Content-Type", "")
        body         = self.rfile.read(length)

        # ── パラメータ解析 ───────────────────────────────────────────────
        pdf_bytes = None
        params    = {}

        # キャラ設定 + 生成オプションの全フィールド名
        ALL_PARAM_KEYS = (
            "pages", "panels", "lang", "model", "title", "quality", "text",
            "char1_name", "char1_personality", "char1_speech", "char1_appearance",
            "char2_name", "char2_personality", "char2_speech", "char2_appearance",
            "genre", "tone", "world_setting",
        )

        if "multipart/form-data" in content_type:
            parts = _parse_multipart(body, content_type)
            # ファイルフィールド（PDF / txt / md）
            file_val = parts.get("file", b"")
            if file_val:
                pdf_bytes = file_val
            # テキスト／オプションフィールドをすべて収集
            for k in ALL_PARAM_KEYS:
                v = parts.get(k)
                if v is not None:
                    params[k] = v.decode("utf-8", errors="replace").strip()
        elif "application/json" in content_type:
            try:
                params = json.loads(body)
            except Exception:
                pass
        else:
            # raw text
            params["text"] = body.decode("utf-8", errors="replace")

        # ── SSE レスポンス開始 ──────────────────────────────────────────
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self._cors()
        self.end_headers()

        def sse(event: str, data: str):
            try:
                msg = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                self.wfile.write(msg.encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass

        def run():
            try:
                # PDF → テキスト
                if pdf_bytes:
                    sse("log", "📄 PDF からテキストを抽出しています...")
                    try:
                        import fitz
                        import re
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        raw = "\n\n".join(p.get_text("text") for p in doc)
                        raw = re.sub(r"-\n(\w)", r"\1", raw)
                        raw = re.sub(r"\n{3,}", "\n\n", raw)
                        doc.close()
                        sse("log", f"✅ 抽出完了 ({len(raw):,} 文字)")
                        params["text"] = raw
                    except ImportError:
                        sse("error", "pymupdf がインストールされていません。pip install pymupdf")
                        return

                text = params.get("text", "").strip()
                if not text:
                    sse("error", "テキストまたは PDF が必要です")
                    return

                # 長文は要約セクションだけ使う（チャンクが大きすぎるとモデルが詰まる）
                if len(text) > 15000:
                    sse("log", f"⚡ 論文が長いため主要セクションを抽出します ({len(text):,} 文字)")
                    text = _trim_paper(text)
                    sse("log", f"   → {len(text):,} 文字に絞り込みました")

                pages   = int(params.get("pages",  3))
                panels  = max(1, min(8, int(params.get("panels", 4))))
                lang    = params.get("lang",  "en")
                title   = params.get("title", "Untitled")
                quality = str(params.get("quality", "false")).lower() in ("true","1","yes")
                model   = _ptn.QUALITY_MODEL if quality else params.get("model", _ptn.DEFAULT_MODEL)

                # キャラ・世界観・ジャンル設定を収集
                char_cfg_keys = (
                    "char1_name","char1_personality","char1_speech","char1_appearance",
                    "char2_name","char2_personality","char2_speech","char2_appearance",
                    "genre","tone","world_setting",
                )
                char_cfg_raw = {k: params.get(k, "") for k in char_cfg_keys}
                char_cfg = _ptn.make_char_config(lang if lang != "auto" else "en", char_cfg_raw)

                if lang == "auto":
                    lang = _ptn.detect_lang(text)
                    sse("log", f"🌐 言語自動検出: {lang}")
                    char_cfg = _ptn.make_char_config(lang, char_cfg_raw)

                sse("log", f"🚀 生成開始  model={model}  pages={pages}  panels/p={panels}  lang={lang}")
                sse("log", f"   キャラ1={char_cfg['char1_name']} / キャラ2={char_cfg['char2_name']}  ジャンル={char_cfg['genre']}")

                # ログをポーリングしてSSEに流す
                sent_idx = [0]
                def flush_log():
                    with _lock:
                        logs = _status["log"][sent_idx[0]:]
                    for m in logs:
                        sse("log", m)
                    sent_idx[0] += len(logs)

                # 生成（paper_to_name を直接呼ぶ）
                _ptn.check_ollama(model)
                chunks = _ptn.split_into_chunks(text, pages)
                result_pages = []
                for i, chunk in enumerate(chunks, 1):
                    flush_log()
                    sse("progress", {"page": i, "total": pages})
                    page = _ptn.generate_page(i, pages, chunk, panels, model, lang, char_cfg=char_cfg)
                    result_pages.append(page)
                    flush_log()

                story = {"title": title, "lang": lang, "char_config": char_cfg, "pages": result_pages}
                STORY_FILE.write_text(
                    json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                flush_log()
                sse("done", {"pages": pages, "file": str(STORY_FILE.name)})

            except Exception as e:
                tb = traceback.format_exc()
                with _lock:
                    _status["error"] = str(e)
                sse("error", str(e))
                sse("log", tb[:500])
            finally:
                with _lock:
                    _status["running"] = False

        # 別スレッドで生成、完了まで SSE ポーリング
        t = threading.Thread(target=run, daemon=True)
        t.start()

        # SSE ループ（ログを逐次送出）
        sent_idx = 0
        while t.is_alive():
            with _lock:
                logs = _status["log"][sent_idx:]
            for m in logs:
                try:
                    msg = f"event: log\ndata: {json.dumps(m, ensure_ascii=False)}\n\n"
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    return
            sent_idx += len(logs)
            time.sleep(0.4)

        t.join()

    def _json(self, code: int, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.end_headers()
        self.wfile.write(body)


# ── ペーパー要約抽出 ─────────────────────────────────────────────────────────
def _trim_paper(text: str, max_chars: int = 12000) -> str:
    """長文論文から Abstract + Results先頭 + Discussion を抜き出す。"""
    import re
    lines = text.split("\n")
    section_map: dict[str, int] = {}
    for kw in ("Results", "Discussion", "Methods", "References", "Conclusion"):
        for i, l in enumerate(lines):
            if l.strip() == kw:
                section_map[kw] = i
                break

    results_start = section_map.get("Results", 0)
    disc_start    = section_map.get("Discussion", section_map.get("Conclusion", len(lines)))
    meth_start    = section_map.get("Methods",    section_map.get("References", len(lines)))

    abstract   = "\n".join(lines[:results_start])[:4000]
    results_hi = "\n".join(lines[results_start : results_start + 300])[:3000]
    discussion = "\n".join(lines[disc_start : meth_start])[:3000]

    combined = f"{abstract}\n\n{results_hi}\n\n{discussion}".strip()
    return combined[:max_chars]


# ── エントリポイント ──────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Dr. CANVAS local server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    url    = f"http://127.0.0.1:{args.port}/viewer.html"
    url_name = f"http://127.0.0.1:{args.port}/name.html"
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"[Dr. CANVAS] Serving on {url}", flush=True)
    print(f"[Dr. CANVAS] Name viewer: {url_name}", flush=True)
    print(f"[Dr. CANVAS] POST /api/generate  -- PDF or text -> manga name (SSE)", flush=True)
    print(f"[Dr. CANVAS] GET  /api/story      -- current_story.json", flush=True)
    print(f"[Dr. CANVAS] Press Ctrl+C to stop.", flush=True)

    # 起動後にブラウザを自動オープン
    def _open():
        time.sleep(1.2)
        import subprocess
        subprocess.Popen(["cmd", "/c", f"start {url}"], shell=False,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Dr. CANVAS] Stopped.")

if __name__ == "__main__":
    main()
