# AGV Simulator

AGV（自律走行搬送車）による無人配送をシミュレートするWebアプリケーション。
注文受付・在庫確認・AGV配送・完了確認までの流通フローを、マルチエージェントで非同期処理する。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-green.svg)

## 機能

- 50×50グリッドマップ上でAGVがリアルタイムに動く可視化シミュレータ
- BFS経路探索による自律配送
- バッテリー管理（残量監視・自動充電・強制帰還）
- 3エージェント構成（Feasibility / Builder / Debugger）
- オプティマイザ：指定シードで最小AGV台数を二分探索で算出
- シード指定による配置の完全再現

## 必要環境

| ツール | バージョン |
|--------|-----------|
| Python | 3.12 以上 |
| uv | 任意（推奨） / pip も可 |
| Docker & Docker Compose | Redis 起動に必要 |

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/showyou/agv_simulator.git
cd agv_simulator
```

### 2. Redis を起動

```bash
docker compose up redis -d
```

### 3. 依存パッケージをインストール

**uv を使う場合（推奨）：**

```bash
uv sync
```

**pip を使う場合：**

```bash
pip install -r requirements.txt
```

### 4. アプリを起動

**uv：**

```bash
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**pip：**

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. ブラウザでアクセス

```
http://localhost:8000
```

LAN内の他のマシンからは `http://<サーバのIPアドレス>:8000` でアクセスできます。

---

## Docker Compose で全部まとめて起動する場合

```bash
docker compose up --build
```

`app`・`worker`・`redis` が一括起動します。

---

## 使い方

### 基本操作

| ボタン | 説明 |
|--------|------|
| ▶ 開始 | シミュレーション開始 |
| ■ 停止 | 一時停止 |
| ↺ リセット | 初期状態に戻す |
| ＋ 注文追加 | 手動で注文を1件追加 |

### 設定スライダー

| 項目 | 説明 |
|------|------|
| Tick速度 | 1tickの間隔（0.1〜2.0秒） |
| 注文間隔 | 自動注文の発生間隔（tick数） |
| AGV台数 | 稼働AGV数をリアルタイム変更（1〜20台） |

### シード機能

- 「シード」欄に数値を入力して「適用」すると、同じ初期配置を再現できる
- シードなしでリセットすると新しいシードが自動生成される

### オプティマイザ

1. 「操作・設定」タブ下部のオプティマイザ欄にシード値を入力
2. 「実行」ボタンを押す
3. 10000tick・待機注文数≤100を条件に、最小AGV台数を二分探索で算出
4. バックグラウンドで実行されるため、シミュレーターを止める必要なし

---

## バッテリー管理ルール

| 残量 | 挙動 |
|------|------|
| 100% → 95% | 充電完了 → 商店へ帰還 |
| 95% 未満（idle時） | 自動で充電スポット（倉庫）へ向かう |
| 30% 以下 | 新規注文を受け付けない |
| 20% 以下 | idle状態なら即充電へ |
| 倉庫まで届かない距離 | 配送中断・注文差し戻し・充電へ |
| 10% 以下 | 無条件で配送中断・充電へ |
| 0%到達 | 評価違反としてカウント |

---

## API一覧

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/state` | 現在のシミュレーション状態 |
| POST | `/start` | シミュレーション開始 |
| POST | `/stop` | 停止 |
| POST | `/reset` | リセット（`{"seed": N}` でシード指定可） |
| POST | `/order` | 手動注文追加 |
| GET | `/config` | 現在の設定値 |
| POST | `/config` | 設定変更（`tick_interval` / `order_spawn_interval` / `agv_speed` / `num_agvs`） |
| POST | `/optimize` | オプティマイザ実行開始（`{"seed": N}`） |
| GET | `/optimize/result` | オプティマイザ進捗・結果取得 |
| WS | `/ws` | WebSocket（tickごとに状態をプッシュ） |

---

## ディレクトリ構成

```
agv_simulator/
├── backend/
│   ├── main.py          # FastAPI エントリポイント
│   ├── simulator.py     # シミュレーションループ・AGVロジック
│   ├── optimizer.py     # ヘッドレスシミュレーション + 二分探索
│   ├── models.py        # データモデル
│   ├── config.py        # 設定定数
│   ├── celery_app.py    # Celery 設定
│   └── agents/
│       ├── feasibility.py  # Agent 1: 実現性判断
│       ├── builder.py      # Agent 2: ルート生成
│       └── debugger.py     # Agent 3: 完了確認・異常検知
├── frontend/
│   ├── index.html       # メインUI
│   ├── map.js           # Canvas描画
│   └── ws.js            # WebSocketクライアント
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

## ライセンス

[MIT License](LICENSE)
