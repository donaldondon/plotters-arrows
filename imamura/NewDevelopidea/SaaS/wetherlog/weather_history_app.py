"""
栃木県 天気ログ検索アプリ（SaaSテスト用 疑似データベース利用）

tochigi_weather_mock.db（generate_mock_weather_db.py で生成した
SQLiteデータベース）から、指定した地点・日付の天気データを
検索して表示するデスクトップアプリです。

このデータベースは実際の気象観測記録ではなく、
SaaSアプリのテスト用に生成した疑似データです。
"""

import os
import sys
import sqlite3
import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

# ---------------------------------------------------------------------------
# データベースの場所を特定する
# （.pyのまま実行した場合はスクリプトと同じフォルダ、
#   exe化した場合はexeファイルと同じフォルダを見る）
# ---------------------------------------------------------------------------

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "tochigi_weather_mock.db")

WEATHER_EMOJI = {
    "晴れ": "☀",
    "曇り": "☁",
    "雨": "🌧",
    "雷雨": "⛈",
    "雪": "❄",
}


# ---------------------------------------------------------------------------
# データアクセス
# ---------------------------------------------------------------------------

def get_connection():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"データベースファイルが見つかりません。\n"
            f"tochigi_weather_mock.db をこのアプリと同じフォルダに置いてください。\n"
            f"({DB_PATH})"
        )
    return sqlite3.connect(DB_PATH)


def get_locations():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT city FROM locations ORDER BY location_id")
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def get_date_range():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT MIN(date), MAX(date) FROM daily_weather")
        return cur.fetchone()
    finally:
        conn.close()


def fetch_weather(city: str, date_str: str):
    """指定地点・日付の天気データを1件取得する（無ければ None）"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT dw.date, dw.weather, dw.max_temp_c, dw.min_temp_c, dw.avg_temp_c,
                   dw.precipitation_mm, dw.humidity_pct, dw.wind_speed_mps
            FROM daily_weather dw
            JOIN locations l ON dw.location_id = l.location_id
            WHERE l.city = ? AND dw.date = ?
            """,
            (city, date_str),
        )
        row = cur.fetchone()
        if row is None:
            return None
        keys = ["date", "weather", "max_temp_c", "min_temp_c", "avg_temp_c",
                "precipitation_mm", "humidity_pct", "wind_speed_mps"]
        return dict(zip(keys, row))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class WeatherHistoryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("栃木県 天気ログ検索（過去5年・疑似データ）")
        self.geometry("420x560")
        self.resizable(False, False)
        self.configure(bg="#f4f7fb")

        self.title_font = tkfont.Font(family="Meiryo", size=14, weight="bold")
        self.big_font = tkfont.Font(family="Meiryo", size=44)
        self.normal_font = tkfont.Font(family="Meiryo", size=12)
        self.small_font = tkfont.Font(family="Meiryo", size=9)

        self.min_date = None
        self.max_date = None
        self.current_date = None

        self._build_widgets()
        self._load_initial_data()

    # -- 画面構築 -----------------------------------------------------

    def _build_widgets(self):
        header = tk.Frame(self, bg="#2f6fed")
        header.pack(fill="x")
        tk.Label(header, text="栃木県 天気ログ検索", font=self.title_font,
                  bg="#2f6fed", fg="white", pady=12).pack()

        # 地点・日付の選択エリア
        form = tk.Frame(self, bg="#f4f7fb")
        form.pack(pady=(14, 4))

        tk.Label(form, text="地点", font=self.normal_font, bg="#f4f7fb").grid(row=0, column=0, sticky="w")
        self.city_var = tk.StringVar()
        self.city_combo = ttk.Combobox(form, textvariable=self.city_var, state="readonly", width=14)
        self.city_combo.grid(row=0, column=1, columnspan=3, pady=4, sticky="w")

        tk.Label(form, text="日付", font=self.normal_font, bg="#f4f7fb").grid(row=1, column=0, sticky="w")
        self.year_var = tk.StringVar()
        self.month_var = tk.StringVar()
        self.day_var = tk.StringVar()
        self.year_combo = ttk.Combobox(form, textvariable=self.year_var, state="readonly", width=6)
        self.month_combo = ttk.Combobox(form, textvariable=self.month_var, state="readonly", width=4,
                                          values=[f"{m:02d}" for m in range(1, 13)])
        self.day_combo = ttk.Combobox(form, textvariable=self.day_var, state="readonly", width=4,
                                        values=[f"{d:02d}" for d in range(1, 32)])
        self.year_combo.grid(row=1, column=1, pady=4)
        tk.Label(form, text="年", font=self.small_font, bg="#f4f7fb").grid(row=1, column=2)
        self.month_combo.grid(row=1, column=3, padx=(8, 0))
        tk.Label(form, text="月", font=self.small_font, bg="#f4f7fb").grid(row=1, column=4)
        self.day_combo.grid(row=1, column=5, padx=(8, 0))
        tk.Label(form, text="日", font=self.small_font, bg="#f4f7fb").grid(row=1, column=6)

        self.range_label = tk.Label(self, text="", font=self.small_font, bg="#f4f7fb", fg="#666666")
        self.range_label.pack()

        nav_frame = tk.Frame(self, bg="#f4f7fb")
        nav_frame.pack(pady=8)
        tk.Button(nav_frame, text="◀ 前日", font=self.small_font, command=self.go_prev_day).grid(row=0, column=0, padx=6)
        tk.Button(nav_frame, text="検索", font=self.normal_font, command=self.search, bg="#2f6fed", fg="white",
                  padx=16).grid(row=0, column=1, padx=6)
        tk.Button(nav_frame, text="次の日 ▶", font=self.small_font, command=self.go_next_day).grid(row=0, column=2, padx=6)

        # 結果表示エリア
        self.date_label = tk.Label(self, text="", font=self.normal_font, bg="#f4f7fb")
        self.date_label.pack(pady=(10, 0))

        self.emoji_label = tk.Label(self, text="", font=self.big_font, bg="#f4f7fb")
        self.emoji_label.pack()

        self.weather_label = tk.Label(self, text="地点と日付を選んで「検索」を押してください",
                                        font=self.title_font, bg="#f4f7fb", wraplength=380, justify="center")
        self.weather_label.pack(pady=(0, 10))

        temp_frame = tk.Frame(self, bg="#f4f7fb")
        temp_frame.pack(pady=4)
        self.max_label = self._make_box(temp_frame, "最高", 0)
        self.min_label = self._make_box(temp_frame, "最低", 1)
        self.avg_label = self._make_box(temp_frame, "平均", 2)

        sub_frame = tk.Frame(self, bg="#f4f7fb")
        sub_frame.pack(pady=10)
        self.precip_label = self._make_box(sub_frame, "降水量", 0, unit="mm")
        self.humidity_label = self._make_box(sub_frame, "湿度", 1, unit="%")
        self.wind_label = self._make_box(sub_frame, "風速", 2, unit="m/s")

        self.status_label = tk.Label(self, text="", font=self.small_font, bg="#f4f7fb", fg="#c0392b")
        self.status_label.pack(pady=(6, 0))

        tk.Label(self, text="※実際の気象観測データではなく、SaaSテスト用の疑似データです。",
                  font=self.small_font, bg="#f4f7fb", fg="#888888").pack(side="bottom", pady=8)

    def _make_box(self, parent, title, col, unit="℃"):
        box = tk.Frame(parent, bg="#f4f7fb")
        box.grid(row=0, column=col, padx=12)
        tk.Label(box, text=title, font=self.small_font, bg="#f4f7fb", fg="#555555").pack()
        value_label = tk.Label(box, text=f"--{unit}", font=self.normal_font, bg="#f4f7fb")
        value_label.pack()
        value_label._unit = unit
        return value_label

    # -- 初期化・データ読み込み ------------------------------------------

    def _load_initial_data(self):
        try:
            cities = get_locations()
            min_d, max_d = get_date_range()
        except Exception as exc:
            self.status_label.config(text=str(exc))
            return

        self.city_combo["values"] = cities
        if cities:
            self.city_var.set(cities[0])

        self.min_date = datetime.date.fromisoformat(min_d)
        self.max_date = datetime.date.fromisoformat(max_d)
        self.range_label.config(text=f"データ期間: {min_d} ～ {max_d}")

        self.year_combo["values"] = [str(y) for y in range(self.min_date.year, self.max_date.year + 1)]

        # デフォルトはデータの最終日（最新日）を表示
        self._set_date_widgets(self.max_date)
        self.search()

    def _set_date_widgets(self, date_obj: datetime.date):
        self.year_var.set(str(date_obj.year))
        self.month_var.set(f"{date_obj.month:02d}")
        self.day_var.set(f"{date_obj.day:02d}")

    def _get_selected_date(self):
        try:
            y = int(self.year_var.get())
            m = int(self.month_var.get())
            d = int(self.day_var.get())
            return datetime.date(y, m, d)
        except (ValueError, TypeError):
            return None

    # -- 操作 ----------------------------------------------------------

    def search(self):
        date_obj = self._get_selected_date()
        city = self.city_var.get()

        if date_obj is None or not city:
            self.status_label.config(text="地点と日付を正しく選択してください。")
            return

        self.status_label.config(text="")
        date_str = date_obj.isoformat()

        try:
            data = fetch_weather(city, date_str)
        except Exception as exc:
            self.status_label.config(text=str(exc))
            return

        if data is None:
            self.date_label.config(text=f"{city} / {date_str}")
            self.emoji_label.config(text="❓")
            self.weather_label.config(text="この日付のデータはありません\n"
                                             f"（データ期間: {self.min_date} ～ {self.max_date}）")
            for lbl in (self.max_label, self.min_label, self.avg_label,
                        self.precip_label, self.humidity_label, self.wind_label):
                lbl.config(text=f"--{lbl._unit}")
            return

        self.current_date = date_obj
        weekday = ["月", "火", "水", "木", "金", "土", "日"][date_obj.weekday()]
        self.date_label.config(text=f"{city} / {data['date']} ({weekday})")
        self.emoji_label.config(text=WEATHER_EMOJI.get(data["weather"], "🌡"))
        self.weather_label.config(text=data["weather"])

        self.max_label.config(text=f"{data['max_temp_c']}℃")
        self.min_label.config(text=f"{data['min_temp_c']}℃")
        self.avg_label.config(text=f"{data['avg_temp_c']}℃")
        self.precip_label.config(text=f"{data['precipitation_mm']}mm")
        self.humidity_label.config(text=f"{data['humidity_pct']}%")
        self.wind_label.config(text=f"{data['wind_speed_mps']}m/s")

    def go_prev_day(self):
        self._shift_day(-1)

    def go_next_day(self):
        self._shift_day(1)

    def _shift_day(self, delta):
        date_obj = self._get_selected_date() or self.current_date
        if date_obj is None:
            return
        new_date = date_obj + datetime.timedelta(days=delta)
        if self.min_date and new_date < self.min_date:
            return
        if self.max_date and new_date > self.max_date:
            return
        self._set_date_widgets(new_date)
        self.search()


def main():
    app = WeatherHistoryApp()
    app.mainloop()


if __name__ == "__main__":
    main()
