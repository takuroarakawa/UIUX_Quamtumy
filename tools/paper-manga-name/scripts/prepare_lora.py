"""
Dr. CANVAS - LoRA データセット準備スクリプト
==============================================
あなたの絵をkohya_ss用のLoRAトレーニングデータセットに変換します。

使い方:
    python prepare_lora.py --input <絵フォルダ> --output lora_dataset [--char "キャラ名"] [--style "絵柄説明"]
    python prepare_lora.py --from-drcanvas  # Dr.CANVASが保存した画像を自動収集

必要なもの:
    pip install Pillow
"""
import argparse, json, shutil, os, re, sys
from pathlib import Path
try:
    from PIL import Image
except ImportError:
    sys.exit("[ERROR] Pillow が必要です: pip install Pillow")


# ── キャプション生成 ────────────────────────────────────────────────────────────
def make_caption(stem: str, char_name: str, style_tags: str) -> str:
    """
    ファイル名・ユーザー指定情報からキャプションを生成する。
    kohya_ss は <繰り返し数>_<キャプション> フォルダ構造を要求する。
    """
    base_tags = f"{char_name}, {style_tags}" if char_name else style_tags
    # ファイル名からヒントを抽出
    stem_lower = stem.lower()
    extra = []
    if any(w in stem_lower for w in ["face","顔","表情","close"]): extra.append("close-up, face")
    if any(w in stem_lower for w in ["body","全身","full","stand"]): extra.append("full body")
    if any(w in stem_lower for w in ["action","fight","バトル"]): extra.append("action pose")
    if any(w in stem_lower for w in ["page","ページ","manga","comic"]): extra.append("manga page")
    extras = ", ".join(extra)
    caption = f"{base_tags}{', ' + extras if extras else ''}"
    return caption.strip().strip(",")


def resize_for_training(img: Image.Image, target: int = 512) -> Image.Image:
    """学習用サイズに変換（512 or 768 の正方形に近い形）"""
    w, h = img.size
    # 長辺を target に合わせる
    if w >= h:
        new_w, new_h = target, int(target * h / w)
    else:
        new_w, new_h = int(target * w / h), target
    # 8の倍数に丸める（SD要件）
    new_w = (new_w // 8) * 8
    new_h = (new_h // 8) * 8
    return img.resize((new_w, new_h), Image.LANCZOS)


def collect_images(source_dir: Path) -> list[Path]:
    exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    return sorted(p for p in source_dir.rglob("*") if p.suffix.lower() in exts)


def collect_drcanvas_images(drcanvas_root: Path) -> list[Path]:
    """Dr. CANVAS が panel_images/ に保存した画像を収集"""
    panel_dir = drcanvas_root / "panel_images"
    if not panel_dir.exists():
        sys.exit(f"[ERROR] panel_images フォルダが見つかりません: {panel_dir}")
    return collect_images(panel_dir)


# ── メイン ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="LoRA Dataset Preparation for Dr. CANVAS")
    ap.add_argument("--input",  "-i", type=Path, help="入力画像フォルダ")
    ap.add_argument("--output", "-o", type=Path, default=Path("lora_dataset"), help="出力フォルダ (default: lora_dataset)")
    ap.add_argument("--char",   "-c", default="",  help="キャラクター名・トリガーワード (例: drcanvas_style)")
    ap.add_argument("--style",  "-s", default="manga style, line art, monochrome", help="スタイルタグ")
    ap.add_argument("--repeat", "-r", type=int, default=10, help="kohya_ss リピート数 (default: 10)")
    ap.add_argument("--size",   type=int, default=512, help="学習解像度 (512 or 768)")
    ap.add_argument("--from-drcanvas", action="store_true", help="Dr. CANVASのパネル画像を使用")
    args = ap.parse_args()

    # 画像収集
    drcanvas_root = Path(__file__).parent.parent
    if args.from_drcanvas:
        images = collect_drcanvas_images(drcanvas_root)
        print(f"[INFO] Dr. CANVAS の panel_images から {len(images)} 枚を収集")
    elif args.input:
        if not args.input.exists():
            sys.exit(f"[ERROR] 入力フォルダが存在しません: {args.input}")
        images = collect_images(args.input)
        print(f"[INFO] {args.input} から {len(images)} 枚を収集")
    else:
        ap.print_help()
        sys.exit("\n[ERROR] --input または --from-drcanvas を指定してください")

    if len(images) < 5:
        print(f"[WARN] 画像が {len(images)} 枚しかありません。最低 15 枚、推奨 50 枚以上")

    # 出力ディレクトリ構造: output/img/<repeat>_<trigger>/
    trigger = args.char or "drcanvas_style"
    img_dir = args.output / "img" / f"{args.repeat}_{trigger}"
    img_dir.mkdir(parents=True, exist_ok=True)
    log_dir = args.output / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    model_dir = args.output / "model"
    model_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    for src in images:
        try:
            img = Image.open(src).convert("RGB")
            img = resize_for_training(img, args.size)
            out_name = f"{trigger}_{processed:04d}.png"
            img.save(img_dir / out_name)
            # キャプションファイル
            caption = make_caption(src.stem, trigger, args.style)
            (img_dir / f"{trigger}_{processed:04d}.txt").write_text(caption, encoding="utf-8")
            print(f"  [{processed+1}/{len(images)}] {src.name} → {out_name}")
            print(f"        caption: {caption}")
            processed += 1
        except Exception as e:
            print(f"[WARN] スキップ {src.name}: {e}")

    # 学習設定ファイルを生成
    config = {
        "pretrained_model_name_or_path": "C:/stable-diffusion-webui/models/Stable-diffusion/your_base_model.safetensors",
        "train_data_dir": str(args.output / "img"),
        "output_dir": str(model_dir),
        "output_name": trigger,
        "logging_dir": str(log_dir),
        "resolution": f"{args.size},{args.size}",
        "max_train_steps": 1500,
        "learning_rate": "1e-4",
        "unet_lr": "1e-4",
        "text_encoder_lr": "5e-5",
        "lr_scheduler": "cosine_with_restarts",
        "network_dim": 32,
        "network_alpha": 16,
        "train_batch_size": 1,
        "save_every_n_epochs": 1,
        "mixed_precision": "fp16",
        "save_precision": "fp16",
        "seed": 42,
        "caption_extension": ".txt",
        "shuffle_caption": True,
        "enable_bucket": True,
    }
    config_path = args.output / "lora_config.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print("=" * 60)
    print(f"データセット準備完了！")
    print(f"  画像数: {processed} 枚")
    print(f"  出力先: {args.output}")
    print(f"  設定ファイル: {config_path}")
    print()
    print("次のステップ:")
    print(f"  1. lora_config.json の pretrained_model_name_or_path を実際のモデルパスに変更")
    print(f"  2. python train_lora.py --config {config_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
