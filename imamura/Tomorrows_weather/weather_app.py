"""
明日の天気を表示するアプリ
データソース: ウェザーニュース (https://weathernews.jp/)
対象地域: 栃木県宇都宮市
"""

import re
import tkinter as tk
from tkinter import font as tkfont
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

LOCATION_NAME = "栃木県宇都宮市"
SOURCE_URL = "https://weathernews.jp/onebox/tenki/tochigi/09201/"
SOURCE_NAME = "ウェザーニュース"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# 傘の要否判定のしきい値（降水確率 %）
UMBRELLA_NEEDED_THRESHOLD = 50
UMBRELLA_MAYBE_THRESHOLD = 30


# ---------------------------------------------------------------------------
# 天気データの取得・解析
# ---------------------------------------------------------------------------

def fetch_html(url: str) -> str:
    """ウェザーニュースのページのHTMLを取得する"""
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _find_tomorrow_container(soup: BeautifulSoup):
    """「明日の天気」の見出しを含む祖先要素のうち、
    最高/最低気温と降水確率(%)を含む最小のブロックを探して返す"""
    heading = soup.find(string=re.compile("明日の天気"))
    if heading is None:
        return None

    container = heading.parent
    for _ in range(8):
        if container is None:
            break
        text = container.get_text()
        if "最高" in text and "最低" in text and "%" in text:
            return container
        if container.parent is None:
            break
        container = container.parent
    return container


def parse_tomorrow_weather(html: str) -> dict:
    """ページのHTMLから明日の天気情報を抽出する。

    戻り値の辞書:
        weather_text: 天気の説明文字列 (例: "くもり時々雨")
        max_temp: 最高気温 (int or None)
        min_temp: 最低気温 (int or None)
        avg_temp: 平均気温 (最高・最低から算出した推定値。float or None)
        am_pop: 午前の降水確率 (int or None)
        pm_pop: 午後の降水確率 (int or None)
    """
    soup = BeautifulSoup(html, "html.parser")
    container = _find_tomorrow_container(soup)

    result = {
        "weather_text": None,
        "max_temp": None,
        "min_temp": None,
        "avg_temp": None,
        "am_pop": None,
        "pm_pop": None,
    }

    if container is None:
        return result

    text = container.get_text("\n")

    # 天気の説明文字列（天気アイコンのalt属性から取得。無ければキーワード検索）
    icon = container.find("img", src=re.compile("wxicon"))
    weather_text = None
    if icon is not None:
        weather_text = icon.get("alt") or icon.get("title")
    if not weather_text:
        for kw in ["晴れ時々曇り", "曇り時々晴れ", "晴れのち曇り", "曇りのち晴れ",
                   "晴れのち雨", "雨のち晴れ", "曇り時々雨", "雨時々曇り",
                   "くもり時々雨", "雨時々くもり", "晴れ", "くもり", "曇り",
                   "雨", "雪", "雷"]:
            if kw in text:
                weather_text = kw
                break
    result["weather_text"] = weather_text

    max_match = re.search(r"最高\D{0,6}?(\d{1,2})", text)
    min_match = re.search(r"最低\D{0,6}?(\d{1,2})", text)
    if max_match:
        result["max_temp"] = int(max_match.group(1))
    if min_match:
        result["min_temp"] = int(min_match.group(1))
    if result["max_temp"] is not None and result["min_temp"] is not None:
        result["avg_temp"] = round((result["max_temp"] + result["min_temp"]) / 2, 1)

    # 降水確率は表形式(午前/午後の見出し行 + 値の行)で書かれているため、
    # 表の行・列構造から直接対応付ける（テキストの前後関係だけで判定すると
    # 見出しと値の位置がずれて誤認識することがあるため）
    table = container.find("table")
    if table is not None:
        rows = table.find_all("tr")
        if len(rows) >= 2:
            header_cells = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
            data_cells = [c.get_text(strip=True) for c in rows[1].find_all(["th", "td"])]
            for label, value in zip(header_cells, data_cells):
                pct_match = re.search(r"(\d{1,3})\s*%", value)
                if not pct_match:
                    continue
                pct = int(pct_match.group(1))
                if "午前" in label:
                    result["am_pop"] = pct
                elif "午後" in label:
                    result["pm_pop"] = pct

    # 表が見つからない場合のフォールバック（ラベル直後の%表記を拾う）
    if result["am_pop"] is None:
        am_match = re.search(r"午前\D{0,6}?(\d{1,3})\s*%", text)
        if am_match:
            result["am_pop"] = int(am_match.group(1))
    if result["pm_pop"] is None:
        pm_match = re.search(r"午後\D{0,6}?(\d{1,3})\s*%", text)
        if pm_match:
            result["pm_pop"] = int(pm_match.group(1))

    return result


def judge_umbrella(am_pop, pm_pop):
    """降水確率から傘の要否を判定する。(メッセージ, 色) を返す"""
    values = [v for v in (am_pop, pm_pop) if v is not None]
    if not values:
        return "降水確率が取得できませんでした", "#888888"

    max_pop = max(values)
    if max_pop >= UMBRELLA_NEEDED_THRESHOLD:
        return "☂ 傘が必要です", "#d9534f"
    elif max_pop >= UMBRELLA_MAYBE_THRESHOLD:
        return "☂ 念のため折りたたみ傘があると安心です", "#e0a800"
    else:
        return "☀ 傘は不要です", "#28a745"


def weather_emoji(weather_text):
    if not weather_text:
        return "❓"
    if "雷" in weather_text:
        return "⛈"
    if "雪" in weather_text:
        return "❄"
    if "雨" in weather_text:
        return "🌧"
    if "曇" in weather_text or "くもり" in weather_text:
        return "☁"
    if "晴" in weather_text:
        return "☀"
    return "🌡"


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class WeatherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"明日の天気 - {LOCATION_NAME}")
        self.geometry("380x520")
        self.resizable(False, False)
        self.configure(bg="#f4f7fb")

        self.title_font = tkfont.Font(family="Meiryo", size=16, weight="bold")
        self.big_font = tkfont.Font(family="Meiryo", size=48)
        self.normal_font = tkfont.Font(family="Meiryo", size=13)
        self.small_font = tkfont.Font(family="Meiryo", size=10)

        self._build_widgets()
        self.after(100, self.refresh)

    def _build_widgets(self):
        header = tk.Frame(self, bg="#2f6fed")
        header.pack(fill="x")
        tk.Label(header, text=LOCATION_NAME, font=self.title_font,
                  bg="#2f6fed", fg="white", pady=14).pack()

        self.date_label = tk.Label(self, text="", font=self.normal_font, bg="#f4f7fb")
        self.date_label.pack(pady=(12, 0))

        self.emoji_label = tk.Label(self, text="…", font=self.big_font, bg="#f4f7fb")
        self.emoji_label.pack(pady=(4, 0))

        self.weather_label = tk.Label(self, text="読み込み中...", font=self.title_font, bg="#f4f7fb")
        self.weather_label.pack(pady=(0, 10))

        temp_frame = tk.Frame(self, bg="#f4f7fb")
        temp_frame.pack(pady=6)
        self.max_label = self._make_temp_box(temp_frame, "最高", 0)
        self.min_label = self._make_temp_box(temp_frame, "最低", 1)
        self.avg_label = self._make_temp_box(temp_frame, "平均(推定)", 2)

        pop_frame = tk.Frame(self, bg="#f4f7fb")
        pop_frame.pack(pady=14)
        self.am_pop_label = self._make_pop_box(pop_frame, "午前の降水確率", 0)
        self.pm_pop_label = self._make_pop_box(pop_frame, "午後の降水確率", 1)

        self.umbrella_frame = tk.Frame(self, bg="#888888")
        self.umbrella_frame.pack(fill="x", padx=20, pady=10, ipady=10)
        self.umbrella_label = tk.Label(self.umbrella_frame, text="判定中...",
                                         font=self.normal_font, bg="#888888", fg="white")
        self.umbrella_label.pack()

        self.refresh_button = tk.Button(self, text="更新", command=self.refresh, font=self.small_font)
        self.refresh_button.pack(pady=(6, 2))

        self.status_label = tk.Label(self, text=f"データ提供: {SOURCE_NAME}",
                                       font=self.small_font, bg="#f4f7fb", fg="#666666")
        self.status_label.pack(side="bottom", pady=8)

    def _make_temp_box(self, parent, title, col):
        box = tk.Frame(parent, bg="#f4f7fb")
        box.grid(row=0, column=col, padx=10)
        tk.Label(box, text=title, font=self.small_font, bg="#f4f7fb", fg="#555555").pack()
        value_label = tk.Label(box, text="--℃", font=self.normal_font, bg="#f4f7fb")
        value_label.pack()
        return value_label

    def _make_pop_box(self, parent, title, col):
        box = tk.Frame(parent, bg="#f4f7fb")
        box.grid(row=0, column=col, padx=16)
        tk.Label(box, text=title, font=self.small_font, bg="#f4f7fb", fg="#555555").pack()
        value_label = tk.Label(box, text="--%", font=self.normal_font, bg="#f4f7fb")
        value_label.pack()
        return value_label

    def refresh(self):
        self.weather_label.config(text="取得中...")
        self.status_label.config(text=f"データ提供: {SOURCE_NAME}（更新中...）")
        self.update_idletasks()
        try:
            html = fetch_html(SOURCE_URL)
            data = parse_tomorrow_weather(html)
            self._render(data)
        except Exception as exc:  # ネットワークエラーやページ構造の変化に備える
            self.weather_label.config(text="取得に失敗しました")
            self.status_label.config(text=f"エラー: {exc}")

    def _render(self, data):
        tomorrow = datetime.now() + timedelta(days=1)
        self.date_label.config(text=tomorrow.strftime("%Y年%m月%d日 (明日)"))

        self.emoji_label.config(text=weather_emoji(data["weather_text"]))
        self.weather_label.config(text=data["weather_text"] or "取得できませんでした")

        self.max_label.config(text=f"{data['max_temp']}℃" if data["max_temp"] is not None else "--℃")
        self.min_label.config(text=f"{data['min_temp']}℃" if data["min_temp"] is not None else "--℃")
        self.avg_label.config(text=f"{data['avg_temp']}℃" if data["avg_temp"] is not None else "--℃")

        self.am_pop_label.config(text=f"{data['am_pop']}%" if data["am_pop"] is not None else "--%")
        self.pm_pop_label.config(text=f"{data['pm_pop']}%" if data["pm_pop"] is not None else "--%")

        message, color = judge_umbrella(data["am_pop"], data["pm_pop"])
        self.umbrella_frame.config(bg=color)
        self.umbrella_label.config(text=message, bg=color)

        self.status_label.config(text=f"データ提供: {SOURCE_NAME}（{datetime.now().strftime('%H:%M')} 更新）")


def main():
    app = WeatherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
