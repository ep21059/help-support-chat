# ヘルプサポートチャットウィジェット

**FastAPI**、**Vue 3**、**PostgreSQL**、**Docker** で構築されたリアルタイム・カスタマーサポートチャットアプリケーションです。

## 機能
- **リアルタイムメッセージング**: WebSocketsを使用した即時双方向通信。
- **画像送信機能**: 訪問者・オペレーター双方が画像をアップロード・送信可能。
- **既読機能 (Read Receipts)**: 相手がメッセージを開いた際に「既読」ステータスを表示。
- **訪問者ウィジェット**: サイト訪問者向けのフローティングチャットインターフェース。
- **オペレーターダッシュボード**: 複数の会話を管理するための管理パネル。未読メッセージの通知機能付き。
- **日本時間 (JST) 対応**: すべてのタイムスタンプは日本時間で表示されます。
- **永続化**: チャット履歴はPostgreSQLに保存されます。

## 技術スタック
- **バックエンド**: Python 3.11 (FastAPI), SQLAlchemy (Async), WebSockets.
- **フロントエンド**: Vue.js 3.3, Vite, TailwindCSS, Lucide Icons.
- **データベース**: PostgreSQL 15.
- **インフラ**: Docker, Docker Compose.

## セットアップと実行

1. **前提条件**: DockerとDocker Composeがインストールされていることを確認してください。

2. **ビルドと実行**:
   ```bash
   docker-compose up --build
   ```

   > [!IMPORTANT]
   > データベースのスキーマ変更（例：既読機能の追加）が含まれる場合、以下のコマンドでデータベースをリセットして再起動する必要があります：
   > ```bash
   > docker-compose down -v
   > docker-compose up --build
   > ```

3. **アプリケーションへのアクセス**:
   - **訪問者ビュー (ランディングページ)**: [http://localhost:5173](http://localhost:5173)
   - **オペレーターダッシュボード**: [http://localhost:5173/#admin](http://localhost:5173/#admin)
   - **APIドキュメント**: [http://localhost:8000/docs](http://localhost:8000/docs)

## アーキテクチャ

### ディレクトリ構造
```
.
├── backend/            # FastAPI アプリケーション
├── frontend/           # Vue.js アプリケーション
└── docker-compose.yml  # オーケストラレーション
```

### 主な設計ポイント
1. **WebSockets**:
   - 訪問者は `/ws/visitor/{visitor_id}` に接続します。
   - オペレーターは `/ws/operator` に接続し、すべてのグローバルイベントを受信します。
   - 既読 (`messages_read`) 等の状態更新もWebSocket経由でリアルタイム配信されます。

2. **REST API**:
   - `POST /api/conversations`: 新しい会話を作成。
   - `POST /api/conversations/{visitor_id}/read`: メッセージを既読にする。
   - `POST /api/upload`: 画像ファイルのアップロード。
   - `GET /api/conversations`: すべての会話履歴を取得。

3. **タイムゾーン処理**:
   - バックエンドはUTC (`Z` suffix付き) で時刻を返し、フロントエンドがブラウザのロケール (JST) に変換して表示します。

### 今後の改善点
- **認証**: `/auth/login` エンドポイントをJWTで保護する (現在はデモ用に簡易実装)。
- **本番環境**: 静的ファイルとAPIを提供するためにNginxをリバースプロキシとして使用。
