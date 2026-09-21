====================================================
 栃木県 天気・気温 疑似データベース（SaaSテスト用） 説明書
====================================================

■ 概要
--------------------------------------------------
このデータベースは、SaaSアプリケーションの動作確認・表示確認・
負荷テストなどを目的として作成した「疑似（合成）データ」です。
実際の気象観測記録ではありません。

栃木県の気候特性（内陸性気候、夏の高温多湿、冬の乾燥と寒暖差、
梅雨、台風シーズンなど）を踏まえてランダム生成していますが、
実在の日の実際の天気・気温とは一致しません。テスト目的以外
（実際の気象情報の参照など）にはご利用にならないでください。

  対象地域: 栃木県 宇都宮市・足利市・日光市・那須塩原市（4地点）
  期間    : 2021-09-20 ～ 2026-09-19（過去5年分・日次）
  件数    : 7,304件（1,826日 × 4地点）
  ファイル: tochigi_weather_mock.db （SQLite3形式）

  ※このデータベースは元々「ノーコードCRUDアプリ」演習のために作成しましたが、
    続く3つの演習（iPaaS連携／Stripeサブスク課金／生成AIツール）にも
    使えるよう、users・subscriptions・automation_events・ai_generated_reports
    の4テーブルを追加しています（詳細は下記）。


■ フォルダの中身
--------------------------------------------------
  tochigi_weather_mock.db      ... 疑似データ本体（SQLiteデータベース）
  generate_mock_weather_db.py  ... 上記データベースを生成したPythonスクリプト
                                    （再実行すると同じ乱数シードで
                                     同一データベースを再生成できます）
  csv_export/                  ... 全テーブルをCSVに書き出したもの
                                    （Googleスプレッドシート・Airtable・
                                     Bubbleへのインポート用）
  README_weather_mock_db.txt   ... このファイル


■ テーブル構成
--------------------------------------------------
[locations] 地点マスタ
  location_id   INTEGER  主キー
  prefecture    TEXT     都道府県名（"栃木県"）
  city          TEXT     市名（宇都宮市／足利市／日光市／那須塩原市）
  latitude      REAL     緯度（概略値）
  longitude     REAL     経度（概略値）
  elevation_m   REAL     標高[m]（概略値）

[daily_weather] 日次の天気・気温データ
  id                 INTEGER  主キー
  location_id        INTEGER  locations.location_id への外部キー
  date               TEXT     日付（YYYY-MM-DD）
  weather            TEXT     天気（晴れ／曇り／雨／雷雨／雪 のいずれか）
  max_temp_c         REAL     最高気温[℃]
  min_temp_c         REAL     最低気温[℃]
  avg_temp_c         REAL     平均気温[℃]（最高・最低の平均）
  precipitation_mm   REAL     降水量[mm]（降水なしの日は0.0）
  humidity_pct       REAL     湿度[%]
  wind_speed_mps     REAL     風速[m/s]

  (location_id, date) は一意（UNIQUE制約）。
  date・location_id にインデックスを作成済みのため、
  期間検索や地点別集計も高速に行えます。

[meta] データ生成に関する情報
  key / value の2列。生成日時・対象期間・乱数シードなどを記録。

[users] SaaS利用ユーザー（ダミー）
  user_id, name, email, plan（free/pro/trial）,
  stripe_customer_id（ダミー値）, home_location（お気に入り地点）, created_at
  8名分のサンプルユーザーを収録。

[subscriptions] サブスクリプション契約履歴（ダミー）
  subscription_id, user_id, plan_name, price_jpy, billing_cycle,
  status（active/trialing/canceled）, current_period_end,
  stripe_subscription_id（ダミー値）, created_at
  proプラン契約中3件・トライアル1件・解約済み1件のサンプルを収録。

[automation_events] iPaaS自動化のイベントログ（ダミー）
  event_id, event_type（severe_weather_alert/form_submission/
  subscription_created など）, source（Make.com/Google Forms/
  Stripe Webhookなど）, payload_summary, status, triggered_at
  「実際にZapier/Makeが動いたらこう記録される」という見本データです。

[ai_generated_reports] 生成AIツールの出力ログ（下書き状態のサンプル）
  report_id, user_id, target_date, target_city, tone, prompt_summary,
  generated_text（未生成はNULL）, model_name, status（draft/generated）,
  created_at
  generated_text 列に実際のAI API呼び出し結果を書き込んでいく想定です。


■ 使い方の例（SQL）
--------------------------------------------------
-- 宇都宮市の直近30日分を新しい順に取得
SELECT dw.date, dw.weather, dw.max_temp_c, dw.min_temp_c, dw.avg_temp_c
FROM daily_weather dw
JOIN locations l ON dw.location_id = l.location_id
WHERE l.city = '宇都宮市'
ORDER BY dw.date DESC
LIMIT 30;

-- 地点別・年別の平均気温
SELECT l.city, strftime('%Y', dw.date) AS year,
       ROUND(AVG(dw.avg_temp_c), 1) AS avg_temp
FROM daily_weather dw
JOIN locations l ON dw.location_id = l.location_id
GROUP BY l.city, year
ORDER BY l.city, year;

-- 天気カテゴリ別の日数集計
SELECT weather, COUNT(*) FROM daily_weather GROUP BY weather;


■ 3つの発展演習での使い方（重要な注意点あり）
--------------------------------------------------
Zapier/Make・Stripe・多くのノーコードツールは「クラウドサービス」なので、
このパソコンの中にあるSQLiteファイル（tochigi_weather_mock.db）を
直接読み書きすることはできません。演習ごとに以下のように橋渡しして
ください。

[1] iPaaS連携（Zapier / Make）
    このdbファイルには直接繋がらないため、
      csv_export/automation_events.csv を Googleスプレッドシートに
      取り込んでおくと、そのシートをZapier/Makeのトリガー／書き込み先
      として使えます。
    演習例:
      ・Googleフォーム(「今日の体感天気」アンケート)の回答を
        Slackに通知する（automation_events の form_submission 行が
        「実際に動いたらこう記録される」という見本です）
      ・スプレッドシート上の降水量が一定値を超えたらSlack通知する
        （severe_weather_alert 行が見本）
    自動化が動いた結果を記録として残したい場合は、Zapier/Makeの
    最後のステップでスプレッドシートに1行追記する、という形にすると
    automation_events テーブルと同じ形の記録が作れます。

[2] Stripeサブスク課金
    こちらもSQLiteファイルにStripeが直接繋がるわけではありません。
    実践の流れとしては:
      1. Stripeのテスト環境で商品・価格（例: Proプラン 月額980円）を作成
      2. Bubble/Glideなど選んだノーコードツール側にStripeプラグインを設定
      3. ノーコードツール自身のデータベースに users/subscriptions と
         同じような項目（プラン・ステータス・契約更新日など）を作る
      4. csv_export/users.csv, subscriptions.csv の内容を参考データとして
         そのままインポートし、動作確認用の初期データにする
    このデータベースの users/subscriptions テーブルは、
    「最終的にどんな項目を持たせればよいか」の設計見本として
    使ってください。stripe_customer_id 等はダミー値なので、
    実際にStripeテストモードで作成されたIDに置き換わります。

[3] 生成AI APIを使った単機能ツール
    これは自分のPython/Webアプリから直接このSQLiteファイルを読み書き
    できるので、3つの中で最もそのまま使えます。
    演習例:
      ・daily_weather から指定日の天気データを取得
      ・OpenAI等のAPIに投げて「取引先へのメール書き出し」や
        「SNS投稿コメント」を生成（ai_generated_reports の
        prompt_summary / tone 列がその入力パターンの見本）
      ・生成結果を ai_generated_reports.generated_text 列に書き戻し、
        status を draft → generated に更新
    ご希望であれば、この「天気データ→生成AI→文章出力」を行う
    Pythonスクリプトも作成できます。


■ 追加ツール: ai_weather_report_tool.py（生成AI文章作成ツール）
--------------------------------------------------
[3]の演習用に、天気データをもとにOpenAI APIで短い文章を生成し、
ai_generated_reports テーブルに記録するGUIツールを同梱しています。

  ai_weather_report_tool.py  ... アプリ本体
  build_exe_ai_tool.bat      ... ダブルクリックで AIWeatherReportTool.exe を
                                  ビルドするスクリプト（openai, pyinstaller を
                                  自動インストールします）

事前準備:
  1. OpenAIのAPIキーを取得（https://platform.openai.com/）
  2. build_exe_ai_tool.bat を実行してexe化するか、
     python -m pip install openai をした上で
     python ai_weather_report_tool.py で直接起動

使い方:
  地点・日付・文章のトーン（ビジネスメール調／SNS投稿調など）を選び、
  APIキーを入力して「文章を生成してデータベースに記録」を押すと、
  その日の天気データをもとにした短い文章が生成され、
  ai_generated_reports テーブルに自動で記録されます。
  過去の生成履歴も画面下部の一覧からいつでも確認できます。

  APIキーはファイルに保存されません。環境変数 OPENAI_API_KEY を
  設定しておくと起動時に自動で入力欄に反映されます。


■ データを作り直したい場合
--------------------------------------------------
generate_mock_weather_db.py 内の以下の値を編集して再実行すると、
別条件のデータベースを作り直せます。

  RANDOM_SEED    ... 乱数シード（変えると別パターンのデータになる）
  YEARS_BACK     ... 遡る年数
  END_DATE       ... データの終了日
  LOCATIONS      ... 対象地点（緯度経度・標高オフセット）
  MONTHLY_NORMALS... 月別の平年気温（ベースとなる季節変化）

実行方法（Pythonが使える環境で）:
  python generate_mock_weather_db.py

同じフォルダに tochigi_weather_mock.db が上書き生成されます。


以上
