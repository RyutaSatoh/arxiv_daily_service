# ArXiv CS.CV Daily Summarizer

これは、arXivのComputer Vision (cs.CV) の新着論文を毎日取得し、Gemini APIを使用して日本語要約とContributionの抽出を行うサービスです。

## セットアップ

1. 必要なライブラリをインストールします:
   ```bash
   pip install -r requirements.txt
   ```

2. Gemini APIキーを設定します:
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```

## 使い方

### 1. 手動実行 (テスト用)
すぐにデータを取得して保存したい場合は、以下を実行します。
```bash
python main_job.py
```
`data/` ディレクトリに `YYYY-MM-DD.json` が作成されます。

### 2. 定期実行 (スケジューラー)
毎日決まった時間に実行するには、スケジューラーを起動します。
```bash
python scheduler_service.py
```
デフォルトでは毎日 10:00 (システム時刻) に実行されます。

### 3. Web UIの起動
保存されたデータを閲覧するためのWebサーバーを起動します。
```bash
python app.py
```
ブラウザで `http://localhost:5000` にアクセスしてください。

## 注意点
- arXivへの過度なアクセスを避けるため、スクレイピングの頻度には注意してください。
- Gemini APIのレート制限に注意してください。
