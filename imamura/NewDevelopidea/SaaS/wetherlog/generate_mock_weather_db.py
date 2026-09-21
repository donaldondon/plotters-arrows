"""
SaaSテスト用 疑似データベース生成スクリプト
テーマ: 過去5年分の栃木県内4市の天気・気温データ

実在の観測データではなく、栃木県の気候特性(内陸性気候・夏の高温多湿・
冬の乾燥・梅雨・台風シーズンなど)を模してランダム生成した「もっともらしい」
テスト用データです。SaaSアプリの動作確認・負荷テスト・表示確認などに
ご利用ください。

生成結果: tochigi_weather_mock.db (SQLite)
  - locations テーブル: 地点マスタ
  - daily_weather テーブル: 日次の天気・気温データ
"""

import datetime
import math
import random
import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

RANDOM_SEED = 20260920  # 再実行しても同じデータが生成されるように固定
random.seed(RANDOM_SEED)

DB_PATH = Path(__file__).parent / "tochigi_weather_mock.db"

YEARS_BACK = 5
END_DATE = datetime.date(2026, 9, 19)          # 昨日まで(生成基準日の前日)
START_DATE = END_DATE.replace(year=END_DATE.year - YEARS_BACK) + datetime.timedelta(days=1)

# 栃木県内の代表4地点（緯度経度は概略値、標高差で気温オフセットを表現）
LOCATIONS = [
    {"name": "宇都宮市", "lat": 36.5551, "lon": 139.8828, "elevation_m": 119, "temp_offset": 0.0},
    {"name": "足利市",   "lat": 36.3417, "lon": 139.4486, "elevation_m": 85,  "temp_offset": 0.6},
    {"name": "日光市",   "lat": 36.7200, "lon": 139.6982, "elevation_m": 600, "temp_offset": -4.5},
    {"name": "那須塩原市", "lat": 36.9649, "lon": 140.0453, "elevation_m": 300, "temp_offset": -2.2},
]

# 宇都宮市を基準とした月別平年値 (最高気温, 最低気温) [℃]
MONTHLY_NORMALS = {
    1: (9, -2), 2: (10, -1), 3: (14, 2), 4: (19, 8), 5: (23, 13), 6: (26, 18),
    7: (30, 22), 8: (32, 23), 9: (27, 19), 10: (21, 12), 11: (16, 5), 12: (11, 0),
}

# 月別の基準降水確率（晴れ/曇り/雨の出やすさに反映）
MONTHLY_RAIN_PROB = {
    1: 0.22, 2: 0.24, 3: 0.30, 4: 0.35, 5: 0.35, 6: 0.50,
    7: 0.45, 8: 0.35, 9: 0.40, 10: 0.33, 11: 0.24, 12: 0.20,
}

# 月別の基準「曇りやすさ」（降水がない日に曇りになる確率）
MONTHLY_CLOUD_PROB = {
    1: 0.30, 2: 0.35, 3: 0.40, 4: 0.45, 5: 0.45, 6: 0.60,
    7: 0.45, 8: 0.40, 9: 0.45, 10: 0.35, 11: 0.30, 12: 0.30,
}

WEATHER_CHOICES = ["晴れ", "曇り", "雨", "雷雨", "雪"]

# ---------------------------------------------------------------------------
# SaaS実践演習（iPaaS連携・Stripe課金・生成AIツール）用の追加テーブル設定
# ---------------------------------------------------------------------------

SAAS_SEED = RANDOM_SEED + 1  # 天気データの乱数列とは独立させる

SAMPLE_USERS = [
    # (name, email, plan)
    ("佐藤 恵",     "sato.megumi@example.com",     "pro"),
    ("鈴木 大輔",   "suzuki.daisuke@example.com",  "free"),
    ("高橋 蒼",     "takahashi.aoi@example.com",   "free"),
    ("田中 舞",     "tanaka.mai@example.com",      "pro"),
    ("伊藤 蓮",     "ito.ren@example.com",         "free"),
    ("渡辺 さくら", "watanabe.sakura@example.com", "pro"),
    ("山本 陸",     "yamamoto.riku@example.com",   "free"),
    ("中村 陽菜",   "nakamura.hina@example.com",   "trial"),
]

PLAN_INFO = {
    "free":  {"plan_name": "Free",     "price_jpy": 0,    "billing_cycle": "monthly"},
    "pro":   {"plan_name": "Proプラン", "price_jpy": 980,  "billing_cycle": "monthly"},
    "trial": {"plan_name": "Proプラン(トライアル)", "price_jpy": 0, "billing_cycle": "monthly"},
}

SAMPLE_AUTOMATION_EVENTS = [
    # (event_type, source, payload_summary, status)
    ("severe_weather_alert", "Make.com シナリオ",
     "2026-08-10 宇都宮市: 降水量52.3mmを検知しSlackへ警報通知", "sent"),
    ("severe_weather_alert", "Make.com シナリオ",
     "2026-01-18 日光市: 最低気温-8.1℃を検知しSlackへ注意喚起通知", "sent"),
    ("form_submission", "Google Forms",
     "体感天気アンケート回答受付: 「蒸し暑い」栃木県宇都宮市", "logged"),
    ("form_submission", "Google Forms",
     "体感天気アンケート回答受付: 「肌寒い」栃木県那須塩原市", "logged"),
    ("subscription_created", "Stripe Webhook (test mode)",
     "田中 舞 さんがProプランに登録（テストモード）", "processed"),
    ("subscription_canceled", "Stripe Webhook (test mode)",
     "鈴木 大輔 さんがProプランを解約（テストモード）", "processed"),
]

SAMPLE_AI_REPORTS = [
    # (target_date, target_city, tone, prompt_summary)
    ("2026-09-18", "宇都宮市", "ビジネスメール調",
     "本日の天気・気温をもとに、取引先へ送る挨拶文の書き出しを生成"),
    ("2026-09-19", "那須塩原市", "カジュアル・SNS投稿調",
     "本日の天気・気温をもとに、SNSに投稿する一言コメントを生成"),
]


# ---------------------------------------------------------------------------
# 季節変化のベースライン気温
# ---------------------------------------------------------------------------

def _smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)


def seasonal_base_temp(date: datetime.date):
    """月別平年値を月の15日に配置し、日付をなめらかに補間して
    その日のベースとなる(最高気温, 最低気温)を返す"""
    year = date.year
    anchors = []
    # 前年12月・当年1-12月・翌年1月をつないで年またぎも補間できるようにする
    anchors.append((datetime.date(year - 1, 12, 15).toordinal(), MONTHLY_NORMALS[12]))
    for m in range(1, 13):
        anchors.append((datetime.date(year, m, 15).toordinal(), MONTHLY_NORMALS[m]))
    anchors.append((datetime.date(year + 1, 1, 15).toordinal(), MONTHLY_NORMALS[1]))

    ordinal = date.toordinal()
    for i in range(len(anchors) - 1):
        x0, (max0, min0) = anchors[i]
        x1, (max1, min1) = anchors[i + 1]
        if x0 <= ordinal <= x1:
            t = _smoothstep((ordinal - x0) / (x1 - x0))
            return max0 + (max1 - max0) * t, min0 + (min1 - min0) * t

    return MONTHLY_NORMALS[date.month]


# ---------------------------------------------------------------------------
# データ生成本体
# ---------------------------------------------------------------------------

def daterange(start: datetime.date, end: datetime.date):
    days = (end - start).days
    for i in range(days + 1):
        yield start + datetime.timedelta(days=i)


def generate_records():
    """地域全体で連動する「気圧配置」的なランダムウォークを日次で進めながら、
    各地点の気温・天気・降水量・湿度・風速を生成する"""
    records = []

    system_temp = 0.0   # 広域の気温偏差（数日単位の寒暖の波）
    system_wet = 0.0    # 広域の湿り気偏差（曇り・雨が続きやすいかどうか）

    for date in daterange(START_DATE, END_DATE):
        # 広域システムを1日ずつランダムウォークさせる（自己相関を持たせて
        # 数日単位でまとまった天候になるようにする）
        system_temp = 0.75 * system_temp + random.gauss(0, 1.3)
        system_wet = 0.80 * system_wet + random.gauss(0, 0.55)

        month = date.month
        base_max_utsu, base_min_utsu = seasonal_base_temp(date)

        rain_prob = MONTHLY_RAIN_PROB[month] + max(-0.15, min(0.15, system_wet * 0.06))
        rain_prob = max(0.03, min(0.85, rain_prob))
        is_rain_day = random.random() < rain_prob

        cloud_prob = MONTHLY_CLOUD_PROB[month] + max(0.0, system_wet) * 0.08
        cloud_prob = max(0.05, min(0.85, cloud_prob))

        for loc in LOCATIONS:
            noise = random.gauss(0, 1.0)
            max_temp = base_max_utsu + loc["temp_offset"] + system_temp + noise
            min_temp = base_min_utsu + loc["temp_offset"] + system_temp + noise * 0.8

            # 最低気温が最高気温を超えないように補正
            if min_temp > max_temp - 1.0:
                min_temp = max_temp - 1.0 - abs(random.gauss(0, 0.5))

            max_temp = round(max_temp, 1)
            min_temp = round(min_temp, 1)
            avg_temp = round((max_temp + min_temp) / 2, 1)

            # 降水量・天気カテゴリの決定
            precip_mm = 0.0
            weather = "晴れ"

            if is_rain_day:
                # 雪になりうる条件（晩秋～早春かつ気温が低い）
                is_snow_season = month in (11, 12, 1, 2, 3)
                if is_snow_season and min_temp <= 3.0 and random.random() < 0.35:
                    weather = "雪"
                    precip_mm = round(max(0.5, random.gauss(6, 4)), 1)
                elif month in (6, 7, 8) and random.random() < 0.20:
                    weather = "雷雨"
                    precip_mm = round(max(1.0, random.gauss(25, 18)), 1)
                else:
                    weather = "雨"
                    # 多くは小雨、まれに大雨（対数正規に近い分布を簡易再現）
                    if random.random() < 0.12:
                        precip_mm = round(max(10.0, random.gauss(45, 20)), 1)
                    else:
                        precip_mm = round(max(0.5, random.gauss(8, 6)), 1)
            else:
                weather = "曇り" if random.random() < cloud_prob else "晴れ"
                precip_mm = 0.0

            # 湿度（雨・曇り・夏は高め、晴れ・冬は低め）
            humidity_base = {"晴れ": 55, "曇り": 68, "雨": 85, "雷雨": 88, "雪": 75}[weather]
            humidity_season = 10 if month in (6, 7, 8, 9) else (-8 if month in (12, 1, 2) else 0)
            humidity = humidity_base + humidity_season + random.gauss(0, 6)
            humidity = round(max(20, min(99, humidity)), 1)

            # 風速（台風シーズン・雷雨時はやや強め）
            wind_base = 2.3 + (1.5 if month == 9 else 0.0) + (1.2 if weather in ("雨", "雷雨") else 0.0)
            wind_speed = max(0.2, round(wind_base + random.gauss(0, 1.0), 1))

            records.append({
                "date": date.isoformat(),
                "location": loc["name"],
                "weather": weather,
                "max_temp_c": max_temp,
                "min_temp_c": min_temp,
                "avg_temp_c": avg_temp,
                "precipitation_mm": precip_mm,
                "humidity_pct": humidity,
                "wind_speed_mps": wind_speed,
            })

    return records


# ---------------------------------------------------------------------------
# SQLite書き出し
# ---------------------------------------------------------------------------

def build_database(records, db_path: Path):
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE locations (
            location_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            prefecture    TEXT NOT NULL,
            city          TEXT NOT NULL UNIQUE,
            latitude      REAL,
            longitude     REAL,
            elevation_m   REAL
        )
    """)

    cur.execute("""
        CREATE TABLE daily_weather (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id        INTEGER NOT NULL REFERENCES locations(location_id),
            date               TEXT NOT NULL,
            weather            TEXT NOT NULL,
            max_temp_c         REAL NOT NULL,
            min_temp_c         REAL NOT NULL,
            avg_temp_c         REAL NOT NULL,
            precipitation_mm   REAL NOT NULL,
            humidity_pct       REAL NOT NULL,
            wind_speed_mps     REAL NOT NULL,
            UNIQUE(location_id, date)
        )
    """)
    cur.execute("CREATE INDEX idx_daily_weather_date ON daily_weather(date)")
    cur.execute("CREATE INDEX idx_daily_weather_location ON daily_weather(location_id)")

    cur.execute("""
        CREATE TABLE meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    location_ids = {}
    for loc in LOCATIONS:
        cur.execute(
            "INSERT INTO locations (prefecture, city, latitude, longitude, elevation_m) "
            "VALUES (?, ?, ?, ?, ?)",
            ("栃木県", loc["name"], loc["lat"], loc["lon"], loc["elevation_m"]),
        )
        location_ids[loc["name"]] = cur.lastrowid

    rows = [
        (
            location_ids[r["location"]],
            r["date"],
            r["weather"],
            r["max_temp_c"],
            r["min_temp_c"],
            r["avg_temp_c"],
            r["precipitation_mm"],
            r["humidity_pct"],
            r["wind_speed_mps"],
        )
        for r in records
    ]
    cur.executemany(
        "INSERT INTO daily_weather "
        "(location_id, date, weather, max_temp_c, min_temp_c, avg_temp_c, "
        " precipitation_mm, humidity_pct, wind_speed_mps) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )

    meta = {
        "description": "SaaSテスト用の疑似(合成)データです。実際の気象観測値ではありません。",
        "theme": "栃木県内4市の過去5年分の天気・気温データ（日次）",
        "period_start": START_DATE.isoformat(),
        "period_end": END_DATE.isoformat(),
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "random_seed": str(RANDOM_SEED),
        "row_count": str(len(rows)),
    }
    cur.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", list(meta.items()))

    conn.commit()
    conn.close()
    return meta


# ---------------------------------------------------------------------------
# SaaS実践演習用テーブルの追加（ユーザー・サブスク・自動化ログ・AI生成ログ）
# ---------------------------------------------------------------------------

def seed_saas_tables(db_path: Path):
    """後続の演習（iPaaS連携／Stripeサブスク課金／生成AIツール）で使う
    ダミーのユーザー・サブスクリプション・自動化イベント・AI生成ログを追加する。

    ここで作るIDは実際のStripeオブジェクトとは無関係なダミー文字列です。
    （テストモードで本物のStripeと連携する際は、Stripe側が発行した
      実際のcustomer/subscription IDに置き換えてください）
    """
    rng = random.Random(SAAS_SEED)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE users (
            user_id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name                 TEXT NOT NULL,
            email                TEXT NOT NULL UNIQUE,
            plan                 TEXT NOT NULL,               -- free / pro / trial
            stripe_customer_id   TEXT,                        -- ダミー値（本番はStripe発行のIDに置換）
            home_location        TEXT,                        -- locations.city のいずれか（お気に入り地点）
            created_at           TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE subscriptions (
            subscription_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id                  INTEGER NOT NULL REFERENCES users(user_id),
            plan_name                TEXT NOT NULL,
            price_jpy                INTEGER NOT NULL,
            billing_cycle            TEXT NOT NULL,           -- monthly など
            status                   TEXT NOT NULL,           -- active / trialing / canceled / past_due
            current_period_end       TEXT,
            stripe_subscription_id   TEXT,                    -- ダミー値（本番はStripe発行のIDに置換）
            created_at               TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE automation_events (
            event_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type       TEXT NOT NULL,   -- severe_weather_alert / form_submission / subscription_created など
            source           TEXT NOT NULL,   -- Zapier / Make.com / Google Forms / Stripe Webhook など
            payload_summary  TEXT NOT NULL,
            status           TEXT NOT NULL,   -- sent / logged / processed / failed
            triggered_at     TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE ai_generated_reports (
            report_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER REFERENCES users(user_id),
            target_date      TEXT NOT NULL,
            target_city      TEXT NOT NULL,
            tone             TEXT NOT NULL,     -- ビジネスメール調 / カジュアル調 など
            prompt_summary   TEXT NOT NULL,
            generated_text   TEXT,              -- 実際に生成AI APIを呼び出した結果を書き込む欄（未生成はNULL）
            model_name       TEXT,
            status           TEXT NOT NULL DEFAULT 'draft',  -- draft / generated / failed
            created_at       TEXT NOT NULL
        )
    """)

    # --- users ---------------------------------------------------------
    cities = [loc["name"] for loc in LOCATIONS]
    now_str = datetime.datetime.now().isoformat(timespec="seconds")
    user_ids = {}
    for name, email, plan in SAMPLE_USERS:
        home_city = rng.choice(cities)
        cur.execute(
            "INSERT INTO users (name, email, plan, stripe_customer_id, home_location, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, plan, f"cus_test_{rng.randint(10000000, 99999999)}", home_city, now_str),
        )
        user_ids[name] = cur.lastrowid

    # --- subscriptions ---------------------------------------------------
    status_by_plan = {
        "pro": "active",
        "trial": "trialing",
        "free": None,  # 無料プランはサブスクリプション行を作らない
    }
    for name, email, plan in SAMPLE_USERS:
        status = status_by_plan.get(plan)
        if status is None:
            continue
        info = PLAN_INFO[plan]
        period_end = (datetime.date.today() + datetime.timedelta(days=rng.randint(5, 30))).isoformat()
        cur.execute(
            "INSERT INTO subscriptions "
            "(user_id, plan_name, price_jpy, billing_cycle, status, current_period_end, "
            " stripe_subscription_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_ids[name], info["plan_name"], info["price_jpy"], info["billing_cycle"],
                status, period_end, f"sub_test_{rng.randint(10000000, 99999999)}", now_str,
            ),
        )
    # 解約済みユーザーの例も1件追加（鈴木大輔がPro解約したケース）
    cur.execute(
        "INSERT INTO subscriptions "
        "(user_id, plan_name, price_jpy, billing_cycle, status, current_period_end, "
        " stripe_subscription_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_ids["鈴木 大輔"], PLAN_INFO["pro"]["plan_name"], PLAN_INFO["pro"]["price_jpy"],
            "monthly", "canceled", (datetime.date.today() - datetime.timedelta(days=10)).isoformat(),
            f"sub_test_{rng.randint(10000000, 99999999)}", now_str,
        ),
    )

    # --- automation_events ------------------------------------------------
    base_day = datetime.date.today()
    for i, (event_type, source, payload_summary, status) in enumerate(SAMPLE_AUTOMATION_EVENTS):
        triggered_at = (base_day - datetime.timedelta(days=len(SAMPLE_AUTOMATION_EVENTS) - i)).isoformat()
        cur.execute(
            "INSERT INTO automation_events (event_type, source, payload_summary, status, triggered_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_type, source, payload_summary, status, triggered_at),
        )

    # --- ai_generated_reports（サンプルは下書き状態。実際の生成は別ツールで行う）--
    sample_user_names = list(user_ids.keys())
    for i, (target_date, target_city, tone, prompt_summary) in enumerate(SAMPLE_AI_REPORTS):
        owner = user_ids[sample_user_names[i % len(sample_user_names)]]
        cur.execute(
            "INSERT INTO ai_generated_reports "
            "(user_id, target_date, target_city, tone, prompt_summary, generated_text, "
            " model_name, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (owner, target_date, target_city, tone, prompt_summary, None, None, "draft", now_str),
        )

    conn.commit()
    conn.close()


def main():
    records = generate_records()
    meta = build_database(records, DB_PATH)
    seed_saas_tables(DB_PATH)
    print(f"生成完了: {DB_PATH}")
    for k, v in meta.items():
        print(f"  {k}: {v}")
    print("  追加テーブル: users, subscriptions, automation_events, ai_generated_reports")


if __name__ == "__main__":
    main()
