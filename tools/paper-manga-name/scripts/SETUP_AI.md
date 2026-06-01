# Dr. CANVAS — AI イラスト生成 セットアップガイド

> **完全無料** | ローカル実行 | APIコスト0円

---

## 必要スペック

| 項目 | 最低要件 | 推奨 |
|------|---------|------|
| GPU | NVIDIA GTX 1060 6GB | NVIDIA RTX 3060 12GB 以上 |
| VRAM | 4GB | 8GB 以上 |
| RAM | 8GB | 16GB 以上 |
| ストレージ | 25GB 空き | SSD 50GB 以上 |
| OS | Windows 10/11 | Windows 11 |
| Python | 3.10.x | 3.10.6 推奨 |

> CPUのみでも動作しますが、1枚生成に数分かかります。

---

## Part 1: AUTOMATIC1111 (Stable Diffusion WebUI)

### 1-1. Git のインストール
https://git-scm.com/download/win からダウンロード・インストール

### 1-2. Python 3.10.6 のインストール
https://www.python.org/downloads/release/python-3106/
- インストール時「Add Python to PATH」にチェック

### 1-3. AUTOMATIC1111 のクローン
```bat
cd C:\
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
cd stable-diffusion-webui
```

### 1-4. モデルのダウンロード
`stable-diffusion-webui\models\Stable-diffusion\` フォルダに .safetensors/.ckpt ファイルを配置。

推奨（マンガ向け）:
- **Anything V5** (HuggingFace / CivitAI で「Anything v5」検索)
- **CounterfeitXL** (高品質アニメ系)

### 1-5. API モードで起動
```bat
C:\stable-diffusion-webui\webui.bat --api --listen
```
または付属スクリプトを使用:
```bat
scripts\start_sd.bat
```

起動後 → http://127.0.0.1:7860 でUIが開く
Dr. CANVAS は http://127.0.0.1:7860/sdapi/v1/... に接続します

---

## Part 2: LoRA 学習 (kohya_ss)

LoRA = **あなたの絵柄をSDに覚えさせる**小型モデル。学習後は Dr. CANVAS のパネル生成で自動的に適用されます。

### 2-1. kohya_ss のインストール
```bat
cd C:\
git clone https://github.com/bmaltais/kohya_ss.git
cd kohya_ss
python -m venv venv
venv\Scripts\activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
```

### 2-2. データセット準備
Dr. CANVAS の `scripts\prepare_lora.py` を使用:
```bat
python scripts\prepare_lora.py --input "あなたの絵フォルダ" --output "lora_dataset"
```
- 最低 15 枚、推奨 50 枚以上
- 同じキャラの表情違い・アングル違いが効果的
- 白黒でも可

### 2-3. 学習実行
```bat
python scripts\train_lora.py --dataset "lora_dataset" --output "my_style_lora" --steps 1500
```
GTX 1080 で約 30〜60 分

### 2-4. LoRA の配置
生成された `my_style_lora.safetensors` を:
```
stable-diffusion-webui\models\Lora\my_style_lora.safetensors
```
にコピー

### 2-5. Dr. CANVAS での設定
Phase 3 「イラスト生成」→「⚙ SD設定」→ **LoRA名** に `my_style_lora` と入力 → 保存

---

## Part 3: クイックスタート（自動インストール）

```bat
scripts\install_ai_all.bat
```
上記スクリプトが以下を自動実行:
1. Git/Python バージョン確認
2. AUTOMATIC1111 のクローン・初回起動
3. kohya_ss のインストール

---

## よくある問題

| 症状 | 解決策 |
|------|--------|
| `CUDA out of memory` | `--medvram` または `--lowvram` オプションを追加 |
| 接続できない | `--api` オプションで起動しているか確認 |
| 生成が遅い | GPU ドライバを最新に更新 |
| 白い画像しか出ない | モデルファイルが壊れている可能性 → 再ダウンロード |
