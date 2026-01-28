# Pythonスクリプトの常駐化（デーモン化）ガイド - Supervisor編

Pythonで作成したWebサーバーや監視スクリプトなどを、サーバー上で常駐プロセス（デーモン）として安定稼働させるための手法です。ここでは、設定が容易で管理機能が充実している **Supervisor** を用いた方法を解説します。

## Supervisorとは
プロセス管理ツールです。指定したコマンド（スクリプト）をバックグラウンドで起動し、監視します。プロセスが停止した場合の自動再起動や、ログ出力の管理（ローテーション等）を自動で行ってくれます。

## 手順

### 1. Supervisorのインストール
Ubuntu/Debian系の場合、以下のコマンドでインストールします。
```bash
sudo apt update && sudo apt install -y supervisor
```

### 2. ログ出力用ディレクトリの作成
アプリケーションのログを保存するディレクトリを作成します。プロジェクト内に `logs` フォルダを作っておくと管理が楽です。
```bash
mkdir -p /path/to/your/project/logs
```

### 3. 設定ファイルの作成
プロジェクトのルートディレクトリなどに、設定ファイル（例: `my_project.conf`）を作成します。

**my_project.conf の例:**
```ini
[program:my-web-app]
; 実行するディレクトリ
directory=/path/to/your/project
; 実行コマンド (仮想環境のPythonを使う場合はフルパス指定推奨)
command=/path/to/your/venv/bin/python app.py
; 実行ユーザー
user=your_username
; 自動起動設定
autostart=true
autorestart=true
; 環境変数が必要な場合
environment=API_KEY="your_key",FLASK_ENV="production"
; ログ出力先
stderr_logfile=/path/to/your/project/logs/app.err.log
stdout_logfile=/path/to/your/project/logs/app.out.log

[program:my-worker]
directory=/path/to/your/project
command=/path/to/your/venv/bin/python worker.py
user=your_username
autostart=true
autorestart=true
stderr_logfile=/path/to/your/project/logs/worker.err.log
stdout_logfile=/path/to/your/project/logs/worker.out.log
```

### 4. 設定の反映
作成した設定ファイルをSupervisorの設定ディレクトリにシンボリックリンクし、設定を読み込ませます。

```bash
# 設定ファイルのリンク (拡張子は .conf である必要があります)
sudo ln -s /path/to/your/project/my_project.conf /etc/supervisor/conf.d/my_project.conf

# 設定の再読み込み
sudo supervisorctl reread

# プロセスの起動・更新
sudo supervisorctl update
```

### 5. ステータスの確認と操作
以下のコマンドで稼働状況を確認できます。
```bash
sudo supervisorctl status
```
`RUNNING` と表示されていれば正常に動作しています。

**その他の操作:**
*   停止: `sudo supervisorctl stop my-web-app`
*   再起動: `sudo supervisorctl restart my-web-app`
*   全プロセスの操作: `sudo supervisorctl restart all`

これで、OS再起動時やエラーによるプロセス終了時にも、自動的にスクリプトが再実行されるようになります。
