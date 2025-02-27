# Battery Optimizer (Pilot Version)

このリポジトリでは、Streamlit を使用した Web アプリケーションを提供しています。
Battery Optimizer (Pilot Version) は、Streamlit と PuLP を利用してバッテリー運用の最適化を行うアプリケーションです。このアプリケーションでは、CSV 形式の価格データをアップロードし、最適化処理を実行、バッテリー残量と市場価格の推移をグラフで表示します。

## 特徴

- バッテリー運用の最適化試算
- バッテリー残量と市場価格の推移グラフ表示
- PuLP と CBC ソルバーを用いた最適化処理
- 過去データを使ったバッテリー運用の収益試算用
- 期間内で最適化を行った際の収益を計算

## 使用にあたっての注意事項

- 項目が多数ある場合は試算に時間がかかります
- EPRXは3時間1ブロックではなく、30分のブロックの2026年4月以降のルールを適用しています。

## 必要な環境

- Python 3.11 以上
- pip

## インストール手順

1. **リポジトリのクローン**

   ```bash
   git clone https://github.com/Factlabel/battery_optimizer.git
   cd battery_optimizer
   
2. **仮想環境の作成（推奨）**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows の場合は .venv\Scripts\activate

3. **必要なパッケージのインストール**

   ```bash
   pip install -r requirements.txt
   
## アプリケーションの実行

- main.py がプロジェクトルート直下にあるため、以下のコマンドでアプリを起動できます。

   ```bash
   streamlit run main.py

## CBCソルバーに関する注意事項

- 本アプリケーションは、PuLP に付属する CBC ソルバーを利用しています。環境によっては、以下のエラーが発生する場合があります。

   ```bash
   pulp.apis.core.PulpSolverError: PULP_CBC_CMD: Not Available (check permissions on .../cbc)
  
## 対策

1. **実行権限の確認**
仮想環境内の CBC 実行ファイルに実行権限が付与されているか確認してください。ターミナルで以下のコマンドを実行します。

   ```bash
   chmod +x .venv/lib/python3.11/site-packages/pulp/solverdir/cbc/osx/arm64/cbc
   
2. **Apple Silicon (arm64) の場合**
Apple Silicon 環境では、付属の CBC バイナリが動作しない場合があります。その場合は Homebrew を利用して CBC をインストールしてください。
   ```bash
   brew install cbc

3. **Apple Silicon (arm64) の場合**
Homebrew でインストールした CBC を使用するには、コード内でソルバーのパスを指定します。例：
   ```bash
   solver = pulp.PULP_CBC_CMD(path="/opt/homebrew/bin/cbc", msg=0)
   
## プロジェクト構成
```bash
   battery_optimizer/
├── .venv/                          # 仮想環境
├── assets/
│   └── images/
│       └── LOGO_factlabel.png      # ロゴ画像
├── src/
│   ├── init.py
│   ├── optimization.py             # 最適化処理のロジック（PuLP 使用）
│   └── config.py                   # エリアごとの託送料金、損失率
├── main.py                         # アプリケーションポータル
├── requirements.txt                # パッケージ一覧
└── README.md                       