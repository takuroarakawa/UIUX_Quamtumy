"""
Dr. CANVAS - LoRA 学習スクリプト
==================================
kohya_ss を使ってあなたの絵柄の LoRA モデルを学習します。

使い方:
    python train_lora.py --config lora_dataset/lora_config.json
    python train_lora.py --dataset lora_dataset --output my_style_lora --steps 1500

kohya_ss のインストール先 (デフォルト: C:\kohya_ss):
    git clone https://github.com/bmaltais/kohya_ss.git C:\kohya_ss
"""
import argparse, json, subprocess, sys, os
from pathlib import Path


KOHYA_DEFAULT = Path("C:/kohya_ss")
VENV_PYTHON   = KOHYA_DEFAULT / "venv/Scripts/python.exe"
TRAIN_SCRIPT  = KOHYA_DEFAULT / "train_network.py"


def find_kohya() -> tuple[Path, Path]:
    """kohya_ss とその Python 環境を探す"""
    candidates = [
        Path("C:/kohya_ss"),
        Path(os.environ.get("USERPROFILE","")) / "kohya_ss",
        Path("D:/kohya_ss"),
    ]
    for base in candidates:
        py = base / "venv/Scripts/python.exe"
        ts = base / "train_network.py"
        if py.exists() and ts.exists():
            return py, ts
    return None, None


def install_kohya():
    print("[INFO] kohya_ss をインストールします...")
    cmds = [
        ["git", "clone", "https://github.com/bmaltais/kohya_ss.git", str(KOHYA_DEFAULT)],
        ["python", "-m", "venv", str(KOHYA_DEFAULT / "venv")],
        [str(KOHYA_DEFAULT / "venv/Scripts/pip.exe"), "install", "torch", "torchvision",
         "--index-url", "https://download.pytorch.org/whl/cu118"],
        [str(KOHYA_DEFAULT / "venv/Scripts/pip.exe"), "install", "-r",
         str(KOHYA_DEFAULT / "requirements.txt")],
    ]
    for cmd in cmds:
        print(f"  $ {' '.join(cmd)}")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            sys.exit(f"[ERROR] コマンド失敗: {' '.join(cmd)}")
    print("[OK] kohya_ss インストール完了")


def build_train_args(config: dict) -> list[str]:
    """kohya_ss train_network.py の引数リストを生成"""
    arg_map = {
        "pretrained_model_name_or_path": "--pretrained_model_name_or_path",
        "train_data_dir":               "--train_data_dir",
        "output_dir":                   "--output_dir",
        "output_name":                  "--output_name",
        "logging_dir":                  "--logging_dir",
        "resolution":                   "--resolution",
        "max_train_steps":              "--max_train_steps",
        "learning_rate":                "--learning_rate",
        "unet_lr":                      "--unet_lr",
        "text_encoder_lr":              "--text_encoder_lr",
        "lr_scheduler":                 "--lr_scheduler",
        "network_dim":                  "--network_dim",
        "network_alpha":                "--network_alpha",
        "train_batch_size":             "--train_batch_size",
        "save_every_n_epochs":          "--save_every_n_epochs",
        "mixed_precision":              "--mixed_precision",
        "save_precision":               "--save_precision",
        "seed":                         "--seed",
        "caption_extension":            "--caption_extension",
    }
    bool_flags = {
        "shuffle_caption": "--shuffle_caption",
        "enable_bucket":   "--enable_bucket",
    }
    args = ["--network_module", "networks.lora"]
    for key, flag in arg_map.items():
        if key in config:
            args += [flag, str(config[key])]
    for key, flag in bool_flags.items():
        if config.get(key):
            args.append(flag)
    return args


def main():
    ap = argparse.ArgumentParser(description="LoRA Training for Dr. CANVAS")
    ap.add_argument("--config",  "-c", type=Path, help="lora_config.json パス")
    ap.add_argument("--dataset", "-d", type=Path, help="データセットフォルダ (config の代わり)")
    ap.add_argument("--output",  "-o", default="drcanvas_style_lora", help="出力名")
    ap.add_argument("--steps",   type=int, default=1500, help="学習ステップ数")
    ap.add_argument("--install", action="store_true", help="kohya_ss をインストール")
    a = ap.parse_args()

    # kohya_ss を探す
    if a.install:
        install_kohya()

    py_path, train_path = find_kohya()
    if not py_path:
        print("[WARN] kohya_ss が見つかりません。")
        print("       --install オプションで自動インストールするか、")
        print("       手動で C:\\kohya_ss にインストールしてください。")
        print()
        print("       git clone https://github.com/bmaltais/kohya_ss.git C:\\kohya_ss")
        sys.exit(1)

    # 設定ロード
    if a.config and a.config.exists():
        config = json.loads(a.config.read_text(encoding="utf-8"))
    elif a.dataset and a.dataset.exists():
        config = {
            "pretrained_model_name_or_path": "C:/stable-diffusion-webui/models/Stable-diffusion/v1-5-pruned.safetensors",
            "train_data_dir": str(a.dataset / "img"),
            "output_dir":     str(a.dataset / "model"),
            "output_name":    a.output,
            "logging_dir":    str(a.dataset / "log"),
            "resolution":     "512,512",
            "max_train_steps": a.steps,
            "learning_rate":  "1e-4",
            "unet_lr":        "1e-4",
            "text_encoder_lr":"5e-5",
            "lr_scheduler":   "cosine_with_restarts",
            "network_dim":    32,
            "network_alpha":  16,
            "train_batch_size": 1,
            "save_every_n_epochs": 1,
            "mixed_precision":"fp16",
            "save_precision": "fp16",
            "seed": 42,
            "caption_extension": ".txt",
            "shuffle_caption": True,
            "enable_bucket":   True,
        }
        Path(config["output_dir"]).mkdir(parents=True, exist_ok=True)
    else:
        ap.print_help()
        sys.exit("\n[ERROR] --config または --dataset を指定してください")

    train_args = build_train_args(config)

    print("=" * 60)
    print(f"  LoRA 学習開始: {config.get('output_name','lora')}")
    print(f"  ステップ数: {config.get('max_train_steps', a.steps)}")
    print(f"  データ: {config['train_data_dir']}")
    print(f"  出力: {config['output_dir']}")
    print("=" * 60)

    cmd = [str(py_path), str(train_path)] + train_args
    result = subprocess.run(cmd, cwd=str(KOHYA_DEFAULT.parent))

    if result.returncode == 0:
        lora_path = Path(config["output_dir"]) / f"{config.get('output_name','lora')}.safetensors"
        sd_lora_dir = Path("C:/stable-diffusion-webui/models/Lora")
        print()
        print("=" * 60)
        print("[完了] LoRA 学習が完了しました！")
        print(f"  LoRA ファイル: {lora_path}")
        if sd_lora_dir.exists():
            import shutil
            shutil.copy2(lora_path, sd_lora_dir / lora_path.name)
            print(f"  AUTOMATIC1111 へコピー済み: {sd_lora_dir / lora_path.name}")
        print()
        print("Dr. CANVAS での使い方:")
        print(f"  Phase 3 → SD設定 → LoRA名: {config.get('output_name','lora')}")
        print("=" * 60)
    else:
        print(f"[ERROR] 学習が失敗しました (code={result.returncode})")
        print("SETUP_AI.md の「よくある問題」を確認してください。")


if __name__ == "__main__":
    main()
