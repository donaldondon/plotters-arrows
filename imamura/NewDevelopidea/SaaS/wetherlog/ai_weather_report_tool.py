"""
生成AI単機能ツール: 天気データ→文章生成（SaaS実践演習 その3）

tochigi_weather_mock.db の天気データをもとに、OpenAI APIで
「特定業界向けの短い文章」（取引先へのメール書き出し、SNS投稿コメントなど）
を自動生成し、生成結果を ai_generated_reports テーブルに記録するツールです。

このデータベースは実際の気象観測記録ではなく、SaaSテスト用の疑似データです。
生成される文章もそれに基づくフィクションとしてお使いください。

事前準備:
  1. OpenAIのAPIキーを取得する（https://platform.openai.com/）
  2. コマンドプロンプトで次を実行してライブラリを入れる
       python -m pip install openai
  3. このアプリと同じフォルダに tochigi_weather_mock.db を置く
     （generate_mock_weather_db.py で生成したものと同じファイル）

APIキーはこのアプリの画面に入力するだけで、ファイルには保存されません
（起動のたびに入力するか、環境変数 OPENAI_API_KEY を設定しておくと
 自動的に入力欄に反映されます）。
"""

import os
import sys
import sqlite3
import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "tochigi_weather_mock.db")

DEFAULT_MODEL = "gpt-4o-mini"

TONE_OPTIONS = [
    "ビジネスメール調（取引先への挨拶文）",
    "カジュアル・SNS投稿調",
    "物流・配送業務連絡調",
    "農業・屋外作業アドバイス調",
    "アパレル店舗向け（来客予想コメント）",
]

WEATHER_EMOJI = {"晴れ": "☀", "曇り": "☁", "雨": "🌧", "雷雨": "⛈", "雪": "❄"}


# ---------------------------------------------------------------------------
# データベースアクセス
# ---------------------------------------------------------------------------

def get_connection():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            "データベースファイルが見つかりません。\n"
            "tochigi_weather_mock.db をこのアプリと同じフォルダに置いてください。\n"
            f"({DB_PATH})"
        )
    return sqlite3.connect(DB_PATH)


def get_locations():
    conn = get_connection()
    try:
        return [row[0] for row in conn.execute("SELECT city FROM locations ORDER BY location_id")]
    finally:
        conn.close()


def get_date_range():
    conn = get_connection()
    try:
        return conn.execute("SELECT MIN(date), MAX(date) FROM daily_weather").fetchone()
    finally:
        conn.close()


def get_users():
    """(user_id, name) のリスト。usersテーブルが無い旧バージョンのdbにも対応。"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cur.fetchone() is None:
            return []
        return cur.execute("SELECT user_id, name FROM users ORDER BY user_id").fetchall()
    finally:
        conn.close()


def fetch_weather(city: str, date_str: str):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT dw.date, dw.weather, dw.max_temp_c, dw.min_temp_c, dw.avg_temp_c,
                   dw.precipitation_mm, dw.humidity_pct, dw.wind_speed_mps
            FROM daily_weather dw
            JOIN locations l ON dw.location_id = l.location_id
            WHERE l.city = ? AND dw.date = ?
            """,
            (city, date_str),
        ).fetchone()
        if row is None:
            return None
        keys = ["date", "weather", "max_temp_c", "min_temp_c", "avg_temp_c",
                "precipitation_mm", "humidity_pct", "wind_speed_mps"]
        return dict(zip(keys, row))
    finally:
        conn.close()


def ensure_reports_table(conn):
    """ai_generated_reports テーブルが無い場合は作成する（旧dbとの互換用）"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_generated_reports (
            report_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER REFERENCES users(user_id),
            target_date      TEXT NOT NULL,
            target_city      TEXT NOT NULL,
            tone             TEXT NOT NULL,
            prompt_summary   TEXT NOT NULL,
            generated_text   TEXT,
            model_name       TEXT,
            status           TEXT NOT NULL DEFAULT 'draft',
            created_at       TEXT NOT NULL
        )
    """)


def save_report(user_id, target_date, target_city, tone, prompt_summary,
                 generated_text, model_name, status):
    conn = get_connection()
    try:
        ensure_reports_table(conn)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ai_generated_reports "
            "(user_id, target_date, target_city, tone, prompt_summary, generated_text, "
            " model_name, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, target_date, target_city, tone, prompt_summary, generated_text,
             model_name, status, datetime.datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def fetch_recent_reports(limit=15):
    conn = get_connection()
    try:
        ensure_reports_table(conn)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        has_users = cur.fetchone() is not None
        if has_users:
            query = """
                SELECT r.report_id, r.target_date, r.target_city, r.tone, r.status,
                       r.generated_text, u.name
                FROM ai_generated_reports r
                LEFT JOIN users u ON r.user_id = u.user_id
                ORDER BY r.report_id DESC LIMIT ?
            """
        else:
            query = """
                SELECT report_id, target_date, target_city, tone, status, generated_text, NULL
                FROM ai_generated_reports ORDER BY report_id DESC LIMIT ?
            """
        return cur.execute(query, (limit,)).fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# プロンプト生成・OpenAI呼び出し
# ---------------------------------------------------------------------------

def build_prompt(weather: dict, city: str, tone: str) -> str:
    return (
        f"あなたは日本語の文章作成アシスタントです。以下の天気データをもとに、"
        f"指定されたトーン・業界向けの短い文章を1つ作成してください。\n\n"
        f"【天気データ（{city}・{weather['date']}）】\n"
        f"天気: {weather['weather']}\n"
        f"最高気温: {weather['max_temp_c']}℃ / 最低気温: {weather['min_temp_c']}℃ "
        f"/ 平均気温: {weather['avg_temp_c']}℃\n"
        f"降水量: {weather['precipitation_mm']}mm / 湿度: {weather['humidity_pct']}% "
        f"/ 風速: {weather['wind_speed_mps']}m/s\n\n"
        f"【文章のトーン・用途】\n{tone}\n\n"
        f"【指示】\n"
        f"上記の天気データに自然に触れながら、3〜5文程度の短い文章を作成してください。"
        f"日本語で、指定されたトーンに合わせた自然な文体にしてください。"
        f"天気データはあくまでテスト用の疑似データであることは文章に含めず、"
        f"実際の日常の一文として書いてください。"
    )


def call_openai(api_key: str, model: str, prompt: str) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "openaiライブラリが見つかりません。\n"
            "コマンドプロンプトで次を実行してインストールしてください。\n"
            "  python -m pip install openai"
        ) from exc

    if not api_key:
        raise RuntimeError("APIキーが入力されていません。")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "あなたは日本語の文章作成が得意なアシスタントです。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
        max_tokens=400,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class AIWeatherReportApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("天気データ×生成AI 文章作成ツール（SaaS演習）")
        self.geometry("560x760")
        self.resizable(False, False)
        self.configure(bg="#f4f7fb")

        self.title_font = tkfont.Font(family="Meiryo", size=13, weight="bold")
        self.normal_font = tkfont.Font(family="Meiryo", size=11)
        self.small_font = tkfont.Font(family="Meiryo", size=9)

        self.min_date = None
        self.max_date = None
        self.users = []  # (user_id, name)

        self._build_widgets()
        self._load_initial_data()

    # -- 画面構築 -----------------------------------------------------

    def _build_widgets(self):
        header = tk.Frame(self, bg="#2f6fed")
        header.pack(fill="x")
        tk.Label(header, text="天気データ×生成AI 文章作成ツール", font=self.title_font,
                  bg="#2f6fed", fg="white", pady=10).pack()

        form = tk.Frame(self, bg="#f4f7fb")
        form.pack(pady=10, padx=16, fill="x")

        # 地点・日付
        tk.Label(form, text="地点", font=self.normal_font, bg="#f4f7fb").grid(row=0, column=0, sticky="w")
        self.city_var = tk.StringVar()
        self.city_combo = ttk.Combobox(form, textvariable=self.city_var, state="readonly", width=12)
        self.city_combo.grid(row=0, column=1, sticky="w", padx=(4, 16))

        tk.Label(form, text="日付", font=self.normal_font, bg="#f4f7fb").grid(row=0, column=2, sticky="w")
        self.year_var = tk.StringVar()
        self.month_var = tk.StringVar()
        self.day_var = tk.StringVar()
        self.year_combo = ttk.Combobox(form, textvariable=self.year_var, state="readonly", width=6)
        self.month_combo = ttk.Combobox(form, textvariable=self.month_var, state="readonly", width=4,
                                          values=[f"{m:02d}" for m in range(1, 13)])
        self.day_combo = ttk.Combobox(form, textvariable=self.day_var, state="readonly", width=4,
                                        values=[f"{d:02d}" for d in range(1, 32)])
        self.year_combo.grid(row=0, column=3)
        self.month_combo.grid(row=0, column=4, padx=(4, 0))
        self.day_combo.grid(row=0, column=5, padx=(4, 0))

        # トーン
        tk.Label(form, text="文章のトーン・用途", font=self.normal_font, bg="#f4f7fb").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.tone_var = tk.StringVar(value=TONE_OPTIONS[0])
        self.tone_combo = ttk.Combobox(form, textvariable=self.tone_var, state="readonly",
                                         width=40, values=TONE_OPTIONS)
        self.tone_combo.grid(row=2, column=0, columnspan=6, sticky="w", pady=(2, 0))

        # 利用者（任意）
        tk.Label(form, text="利用者（任意・記録用）", font=self.normal_font, bg="#f4f7fb").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.user_var = tk.StringVar(value="(指定なし)")
        self.user_combo = ttk.Combobox(form, textvariable=self.user_var, state="readonly", width=40)
        self.user_combo.grid(row=4, column=0, columnspan=6, sticky="w", pady=(2, 0))

        # APIキー
        tk.Label(form, text="OpenAI APIキー", font=self.normal_font, bg="#f4f7fb").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.api_key_var = tk.StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        self.api_key_entry = tk.Entry(form, textvariable=self.api_key_var, show="*", width=42)
        self.api_key_entry.grid(row=6, column=0, columnspan=6, sticky="w", pady=(2, 0))

        # 天気プレビュー
        self.weather_preview = tk.Label(self, text="", font=self.small_font, bg="#eef2fa",
                                          fg="#333333", justify="left", anchor="w",
                                          wraplength=520, padx=10, pady=6)
        self.weather_preview.pack(fill="x", padx=16, pady=(8, 4))

        # 生成ボタン
        self.generate_button = tk.Button(self, text="文章を生成してデータベースに記録",
                                           font=self.normal_font, bg="#2f6fed", fg="white",
                                           command=self.on_generate, padx=10, pady=6)
        self.generate_button.pack(pady=6)

        self.status_label = tk.Label(self, text="", font=self.small_font, bg="#f4f7fb", fg="#c0392b",
                                       wraplength=520, justify="left")
        self.status_label.pack(padx=16)

        # 生成結果
        tk.Label(self, text="生成結果", font=self.normal_font, bg="#f4f7fb").pack(anchor="w", padx=16, pady=(8, 0))
        self.result_text = tk.Text(self, height=6, width=62, font=self.normal_font, wrap="word")
        self.result_text.pack(padx=16, pady=(2, 8))

        # 履歴
        tk.Label(self, text="生成履歴（クリックで内容を表示）", font=self.normal_font, bg="#f4f7fb").pack(
            anchor="w", padx=16)
        history_frame = tk.Frame(self)
        history_frame.pack(padx=16, pady=(2, 10), fill="both", expand=True)
        self.history_list = tk.Listbox(history_frame, font=self.small_font, height=8)
        self.history_list.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(history_frame, command=self.history_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.history_list.config(yscrollcommand=scrollbar.set)
        self.history_list.bind("<<ListboxSelect>>", self.on_history_select)
        self._history_data = []

        tk.Label(self, text="※実際の気象データではなく、SaaSテスト用の疑似データに基づく生成AI演習ツールです。",
                  font=self.small_font, bg="#f4f7fb", fg="#888888").pack(side="bottom", pady=6)

    # -- 初期化 ---------------------------------------------------------

    def _load_initial_data(self):
        try:
            cities = get_locations()
            min_d, max_d = get_date_range()
            self.users = get_users()
        except Exception as exc:
            self.status_label.config(text=str(exc))
            return

        self.city_combo["values"] = cities
        if cities:
            self.city_var.set(cities[0])

        self.min_date = datetime.date.fromisoformat(min_d)
        self.max_date = datetime.date.fromisoformat(max_d)
        self.year_combo["values"] = [str(y) for y in range(self.min_date.year, self.max_date.year + 1)]
        self._set_date_widgets(self.max_date)

        user_labels = ["(指定なし)"] + [f"{name} (ID:{uid})" for uid, name in self.users]
        self.user_combo["values"] = user_labels
        self.user_var.set("(指定なし)")

        self.refresh_weather_preview()
        self.refresh_history()

    def _set_date_widgets(self, date_obj: datetime.date):
        self.year_var.set(str(date_obj.year))
        self.month_var.set(f"{date_obj.month:02d}")
        self.day_var.set(f"{date_obj.day:02d}")

    def _get_selected_date(self):
        try:
            return datetime.date(int(self.year_var.get()), int(self.month_var.get()), int(self.day_var.get()))
        except (ValueError, TypeError):
            return None

    def _get_selected_user_id(self):
        label = self.user_var.get()
        if label == "(指定なし)" or not label:
            return None
        for uid, name in self.users:
            if label == f"{name} (ID:{uid})":
                return uid
        return None

    # -- 天気プレビュー ---------------------------------------------------

    def refresh_weather_preview(self):
        date_obj = self._get_selected_date()
        city = self.city_var.get()
        if date_obj is None or not city:
            return
        try:
            data = fetch_weather(city, date_obj.isoformat())
        except Exception as exc:
            self.weather_preview.config(text=str(exc))
            return

        if data is None:
            self.weather_preview.config(
                text=f"{city} / {date_obj.isoformat()} のデータが見つかりません"
                     f"（データ期間: {self.min_date} ～ {self.max_date}）")
            return

        emoji = WEATHER_EMOJI.get(data["weather"], "🌡")
        self.weather_preview.config(
            text=f"{emoji} {city} / {data['date']}  天気: {data['weather']}  "
                 f"最高{data['max_temp_c']}℃ / 最低{data['min_temp_c']}℃ / 平均{data['avg_temp_c']}℃  "
                 f"降水量{data['precipitation_mm']}mm  湿度{data['humidity_pct']}%  風速{data['wind_speed_mps']}m/s"
        )

    # -- 生成処理 ---------------------------------------------------------

    def on_generate(self):
        self.status_label.config(text="")
        date_obj = self._get_selected_date()
        city = self.city_var.get()
        tone = self.tone_var.get()
        api_key = self.api_key_var.get().strip()

        if date_obj is None or not city:
            self.status_label.config(text="地点と日付を正しく選択してください。")
            return

        try:
            weather = fetch_weather(city, date_obj.isoformat())
        except Exception as exc:
            self.status_label.config(text=str(exc))
            return

        if weather is None:
            self.status_label.config(
                text=f"{city} / {date_obj.isoformat()} の天気データが見つかりません。")
            return

        prompt = build_prompt(weather, city, tone)
        prompt_summary = f"{city}/{weather['date']}の天気({weather['weather']})をもとに「{tone}」の文章を生成"

        self.generate_button.config(state="disabled", text="生成中...")
        self.update_idletasks()

        user_id = self._get_selected_user_id()
        try:
            generated_text = call_openai(api_key, DEFAULT_MODEL, prompt)
            self.result_text.delete("1.0", "end")
            self.result_text.insert("1.0", generated_text)
            save_report(user_id, weather["date"], city, tone, prompt_summary,
                        generated_text, DEFAULT_MODEL, "generated")
            self.status_label.config(text="生成し、データベース(ai_generated_reports)に記録しました。", fg="#28a745")
            self.refresh_history()
        except Exception as exc:
            save_report(user_id, weather["date"], city, tone, prompt_summary,
                        None, DEFAULT_MODEL, "failed")
            self.status_label.config(text=f"生成に失敗しました: {exc}", fg="#c0392b")
        finally:
            self.generate_button.config(state="normal", text="文章を生成してデータベースに記録")

    # -- 履歴 -----------------------------------------------------------

    def refresh_history(self):
        try:
            rows = fetch_recent_reports()
        except Exception as exc:
            self.status_label.config(text=str(exc))
            return

        self._history_data = rows
        self.history_list.delete(0, "end")
        for report_id, target_date, target_city, tone, status, generated_text, user_name in rows:
            mark = "✔" if status == "generated" else ("✕" if status == "failed" else "…")
            who = f" / {user_name}" if user_name else ""
            self.history_list.insert(
                "end", f"[{mark}] {target_date} {target_city}{who} - {tone[:14]}"
            )

    def on_history_select(self, event):
        selection = self.history_list.curselection()
        if not selection:
            return
        row = self._history_data[selection[0]]
        _, _, _, _, status, generated_text, _ = row
        self.result_text.delete("1.0", "end")
        if generated_text:
            self.result_text.insert("1.0", generated_text)
        else:
            self.result_text.insert("1.0", f"(この履歴は生成に失敗しています: status={status})")


def main():
    app = AIWeatherReportApp()

    # 地点・日付が変わったらプレビューを更新する
    app.city_combo.bind("<<ComboboxSelected>>", lambda e: app.refresh_weather_preview())
    app.year_combo.bind("<<ComboboxSelected>>", lambda e: app.refresh_weather_preview())
    app.month_combo.bind("<<ComboboxSelected>>", lambda e: app.refresh_weather_preview())
    app.day_combo.bind("<<ComboboxSelected>>", lambda e: app.refresh_weather_preview())

    app.mainloop()


if __name__ == "__main__":
    main()
