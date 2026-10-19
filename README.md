# からつdrift

自動車維持費の記録・集計と、車好き同士の投稿共有を行うDjango Webアプリです。利用者アカウント、車両、維持費、投稿、いいねをサーバー側のDBに保存します。

## ローカル起動（Windows）

リポジトリのルート（このREADMEがあるフォルダー）でPowerShellを開きます。

```powershell
py -3.9 -m venv .venv-procon
.\.venv-procon\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd karatsu_drift
python manage.py migrate
python manage.py runserver
```

ブラウザーで `http://127.0.0.1:8000/` を開きます。ログイン画面から利用者を登録してください。共有機能の確認には、別のブラウザー（またはプライベートウィンドウ）で2つ目のアカウントを作ると分かりやすいです。

管理画面用アカウントを作る場合は、別のターミナルで同じ仮想環境を有効にしてから `python manage.py createsuperuser` を実行します。

登録済みのDBを初期化するときは、必要なデータを保存してから `python manage.py flush` を実行します。マイグレーションは `karatsu_drift/app/migrations/` にあります。

## 主な機能

- メールアドレスでのアカウント登録、ログイン、ログアウト、アカウント削除
- 車両の登録・削除と、匿名統計への共有同意
- 維持費の登録、月別／年別集計、費目・車両・期間での絞り込み、記録の編集・削除
- 共有同意済みの維持費データを使った車種別の参考額検索
- 全利用者が閲覧できる投稿、写真メモ・画像投稿、投稿削除、いいね／取り消し
- 管理者向けDjango管理画面（`/admin/`）

## DBと保存場所

初期設定ではSQLiteの `karatsu_drift/db.sqlite3` に保存します。PostgreSQLを使う場合は、起動前に環境変数を設定します。

```powershell
$env:DB_ENGINE = "postgresql"
$env:DB_NAME = "karatsu_drift"
$env:DB_USER = "postgres"
$env:DB_PASSWORD = "<DBパスワード>"
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "5432"
```

投稿画像は `karatsu_drift/media/posts/` に保存します。画像はJPEG、PNG、WebP、5MB以下に制限しています。DBと画像フォルダーはバックアップ対象です。

Python 3.9のローカル環境ではDjango 4.2系を使います。インターネットへ公開する場合は、サポート中のDjango 5.2 LTSを使えるPython 3.10以上へ更新し、PostgreSQL、HTTPS、秘密鍵・許可ホスト設定、永続画像ストレージを整えてください。`runserver` は提出デモ用の開発サーバーです。

公開サーバー用の静的ファイルは `python manage.py collectstatic --noinput` で生成します。`DJANGO_DEBUG=0` にし、`DJANGO_SECRET_KEY`、`DJANGO_ALLOWED_HOSTS`、`DJANGO_CSRF_TRUSTED_ORIGINS` を環境変数で設定してください。HTTPSと本番用WSGIサーバーも必要です。

## Renderで提出デモを公開する

リポジトリ直下の `render.yaml` は、RenderのBlueprintからWebサービスとPostgreSQLを作る設定です。GitHubへ変更をpushした後、RenderでNew Blueprint Instanceを選び、`karatsu_drift` リポジトリを接続してApplyすると公開できます。Renderは`RENDER_EXTERNAL_HOSTNAME`をアプリへ渡し、Djangoの許可ホストとCSRFオリジンに反映します。

このBlueprintは提出用の無料デモ設定です。Renderの無料Webサービスは15分アクセスがないと休止し、無料Postgresは作成から30日で期限切れになります。無料Webサービスではアップロード画像も再起動・再デプロイ時に消えます。長期運用や投稿画像の保存には有料のWebサービス／Postgresと永続ディスク、または外部画像ストレージが必要です。Renderの利用条件と料金をDashboardで確認してからApplyしてください。

無料Postgresは新規作成されるため、ローカルDBの内容は自動で移りません。公開後に利用者が新規登録すれば共有できます。既存データも移す場合は、RenderのPostgres接続情報を使ってローカルから一度だけ`loaddata`します。`sqlite-backup.json`は利用者データを含むためGitへ登録しないでください（`.gitignore`で除外済み）。

## 設計資料との対応

画面設計書のSCR-01〜SCR-07をWeb画面に実装し、ガントチャートの認証、車両、維持費、車種検索、投稿、いいねをサーバー機能として接続しています。JavaのServlet／DAO／Bean相当の役割は、DjangoのView／ORMモデル／サービス処理で構成します。

設計書間には差があります。テーブル設計書の費目は5区分ですが、画面設計書には8区分が定義されているため、アプリは画面設計書の8区分を採用しています。テーブル一覧に年月テーブル・費目マスタはないため、発生日から集計し、費目は選択肢として保持します。画面設計書では写真欄はメモのみですが、ガントチャートの写真追加にも対応するため、メモに加えて画像ファイルも任意で投稿できます。
