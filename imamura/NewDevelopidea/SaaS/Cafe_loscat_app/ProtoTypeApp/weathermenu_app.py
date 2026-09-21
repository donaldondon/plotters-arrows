"""
Hestiā（カフェ）向け 天気連動メニュー提案・自動発信ツール

今日／明日の天気（ウェザーニュース）を取得し、天気に合った
おすすめメニューを在庫状況（stock_input.csv）から選び、
  1) 店内デジタル看板用の一言コピー
  2) SNS投稿の下書き文
  3) 簡単な看板画像（PNG）
を自動で作成します。

文章はまずルールベースで下書きを作り、OpenAI APIキーが入力されて
いる場合はその下書きをHestiāのブランドトーン（家族でゆっくりできる、
あたたかい雰囲気）に沿って仕上げます。APIキーが未入力の場合は
ルールベースの下書きをそのまま使用します。

このアプリは fetch した天気予報・在庫データをもとに動作するツールです。
天気予報はウェザーニュースの予報ページの構造に依存するため、
サイト側の変更で取得に失敗する場合があります。
"""

import os
import re
import sys
import csv
import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

import cafe_menu_data

# ---------------------------------------------------------------------------
# 設定（店舗ごとに変更する場合はここを編集してください）
# ---------------------------------------------------------------------------

STORE_NAME = "Hestiā"
STORE_CATEGORY = "カフェ"
LOCATION_NAME = "栃木県宇都宮市"
SOURCE_URL = "https://weathernews.jp/onebox/tenki/tochigi/09201/"
SOURCE_NAME = "ウェザーニュース"

# Hestiā = ギリシャ語で「暖炉・かまど」。家族の団らんの象徴とされる。
BRAND_CONCEPT = (
    "店名「Hestiā」はギリシャ語で暖炉・家族を意味する言葉に由来しています。"
    "家族でゆっくりくつろげる、あたたかい雰囲気のカフェです。"
)
SNS_STYLE_HINT = "家族でゆったり過ごせる、あたたかく親しみやすい雰囲気"
HASHTAGS = ["#Hestia", "#宇都宮カフェ", "#家族カフェ"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# 天気タグ判定のしきい値（cafe_menu_data.py のタグ定義と対応）
COLD_DAY_MAX_TEMP = 10       # これ以下で「寒い日」
HOT_DAY_MAX_TEMP = 28        # これ以上で「暑い日」
HEATWAVE_MAX_TEMP = 35       # これ以上で「猛暑日」
RAIN_POP_THRESHOLD = 50      # 降水確率(%)がこれ以上で「雨の日」扱い

# メニュー候補・選択に関する設定
CANDIDATE_COUNT = 8          # 一覧に表示する候補数
DEFAULT_SELECT_COUNT = 4     # 自動で選択状態にする件数

# 看板画像の保存先（このスクリプト／exeと同じ場所に作成）
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STOCK_CSV_PATH = os.path.join(BASE_DIR, "stock_input.csv")
SIGNAGE_OUTPUT_DIR = os.path.join(BASE_DIR, "signage_output")

DEFAULT_MODEL = "gpt-4o-mini"

# 看板画像の配色（暖色系）
COLOR_BG_TOP = (255, 247, 235)
COLOR_BG_BOTTOM = (255, 209, 145)
COLOR_HEADER = (183, 96, 45)      # 暖炉を思わせるテラコッタ
COLOR_ACCENT = (224, 122, 34)
COLOR_TEXT_DARK = (69, 42, 24)
COLOR_CARD_BG = (255, 255, 255)
COLOR_CARD_BORDER = (224, 168, 118)
COLOR_RIBBON = (163, 76, 30)

FONT_BOLD_CANDIDATES = [
    r"C:\Windows\Fonts\YuGothB.ttc",
    r"C:\Windows\Fonts\meiryob.ttc",
    r"C:\Windows\Fonts\msgothic.ttc",
    r"C:\Windows\Fonts\HGRGY.TTC",
]
FONT_REGULAR_CANDIDATES = [
    r"C:\Windows\Fonts\YuGothR.ttc",
    r"C:\Windows\Fonts\meiryo.ttc",
    r"C:\Windows\Fonts\msgothic.ttc",
]


# ---------------------------------------------------------------------------
# 天気データの取得・解析（weather_app.py のロジックを今日／明日に一般化）
# ---------------------------------------------------------------------------

def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _find_day_container(soup: BeautifulSoup, heading_text: str):
    """指定した見出し（"今日の天気" または "明日の天気"）を含む祖先要素のうち、
    最高/最低気温と降水確率(%)を含む最小のブロックを探して返す"""
    heading = soup.find(string=re.compile(heading_text))
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


def parse_day_weather(html: str, day: str) -> dict:
    """day は "today" または "tomorrow" を指定する。"""
    heading_text = "今日の天気" if day == "today" else "明日の天気"
    soup = BeautifulSoup(html, "html.parser")
    container = _find_day_container(soup, heading_text)

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

    if result["am_pop"] is None:
        am_match = re.search(r"午前\D{0,6}?(\d{1,3})\s*%", text)
        if am_match:
            result["am_pop"] = int(am_match.group(1))
    if result["pm_pop"] is None:
        pm_match = re.search(r"午後\D{0,6}?(\d{1,3})\s*%", text)
        if pm_match:
            result["pm_pop"] = int(pm_match.group(1))

    return result


def weather_emoji_char(weather_text):
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


def weather_icon_category(weather_text):
    if not weather_text:
        return "unknown"
    if "雷" in weather_text:
        return "thunder"
    if "雪" in weather_text:
        return "snow"
    if "雨" in weather_text:
        return "rain"
    if "曇" in weather_text or "くもり" in weather_text:
        return "cloudy"
    if "晴" in weather_text:
        return "sunny"
    return "unknown"


# ---------------------------------------------------------------------------
# 天気 → タグ判定
# ---------------------------------------------------------------------------

def classify_weather_tags(weather_text, max_temp, min_temp, am_pop, pm_pop):
    """cafe_menu_data.MENU_ITEMS の tags と対応する気象タグの集合を返す。"""
    tags = set()

    if max_temp is not None:
        if max_temp >= HEATWAVE_MAX_TEMP:
            tags.add("猛暑日")
        if max_temp >= HOT_DAY_MAX_TEMP:
            tags.add("暑い日")
        if max_temp <= COLD_DAY_MAX_TEMP:
            tags.add("寒い日")

    is_rainy = bool(weather_text) and any(k in weather_text for k in ("雨", "雪", "雷"))
    pop_values = [v for v in (am_pop, pm_pop) if v is not None]
    if pop_values and max(pop_values) >= RAIN_POP_THRESHOLD:
        is_rainy = True
    if is_rainy:
        tags.add("雨の日")

    if not tags:
        tags.add("普通の日")

    return tags


# ---------------------------------------------------------------------------
# 在庫読み込み・おすすめメニュー選定
# ---------------------------------------------------------------------------

def load_stock(csv_path=STOCK_CSV_PATH):
    """stock_input.csv を読み込み、{メニュー名: {"count": int, "priority": str|None}} を返す。"""
    stock = {}
    if not os.path.exists(csv_path):
        return stock
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("メニュー名") or "").strip()
            if not name:
                continue
            raw_count = (row.get("本日の提供可能数") or "0").strip()
            try:
                count = int(raw_count) if raw_count else 0
            except ValueError:
                count = 0
            priority_col = "優先度(高/中/低・空欄なら自動判定)"
            priority = (row.get(priority_col) or "").strip() or None
            stock[name] = {"count": count, "priority": priority}
    return stock


_PRIORITY_RANK = {"高": 0, "中": 1, "低": 2}


def recommend_menu(tags, stock, menu_items=None, limit=CANDIDATE_COUNT):
    """気象タグに合い、在庫が1以上あるメニューを、
    売り切り優先度（高→低）・在庫数（多い順）で並べて返す。"""
    if menu_items is None:
        menu_items = cafe_menu_data.MENU_ITEMS

    candidates = []
    for item in menu_items:
        st = stock.get(item["name"])
        if st is None or st["count"] <= 0:
            continue
        if not (item["tags"] & tags):
            continue
        rank = _PRIORITY_RANK.get(st["priority"], 1)
        candidates.append({
            "name": item["name"],
            "category": item["category"],
            "price": item["price"],
            "tags": item["tags"],
            "stock": st["count"],
            "priority": st["priority"] or "中(自動)",
            "priority_rank": rank,
        })

    candidates.sort(key=lambda c: (c["priority_rank"], -c["stock"]))
    return candidates[:limit]


# ---------------------------------------------------------------------------
# 文章生成（ルールベース下書き → 生成AIで仕上げ）
# ---------------------------------------------------------------------------

def build_rule_based_texts(day_label, weather_data, tags, items):
    weather_text = weather_data["weather_text"] or "不明"
    max_t = weather_data["max_temp"]
    min_t = weather_data["min_temp"]

    if not items:
        item_phrase = "店内メニュー"
    elif len(items) == 1:
        item_phrase = items[0]["name"]
    else:
        item_phrase = "と".join(name for name in [items[0]["name"], items[1]["name"]] if name)

    temp_phrase = ""
    if max_t is not None and min_t is not None:
        temp_phrase = f"最高{max_t}℃・最低{min_t}℃。"

    signage_base = (
        f"{day_label}は{weather_text}、{temp_phrase}"
        f"こんな日は{item_phrase}がおすすめです。"
    )

    tag_word = "・".join(sorted(tags))
    sns_base = (
        f"【{STORE_NAME}より】{day_label}は{weather_text}になりそうです。"
        f"{tag_word}にぴったりの{item_phrase}をご用意してお待ちしています。"
        f"ご家族でゆっくりお過ごしください。 " + " ".join(HASHTAGS)
    )

    return signage_base, sns_base


def build_polish_prompt(day_label, weather_data, items, signage_base, sns_base):
    item_lines = "\n".join(
        f"  - {it['name']}（{it['category']}・{it['price']}円）" for it in items
    ) or "  （該当メニューなし。店内の人気メニュー全般としてください）"

    return (
        "あなたは飲食店のSNS運用・店内販促文の作成が得意な日本語コピーライターです。\n"
        "以下の【店舗情報】【天気データ】【おすすめメニュー】【下書き】を踏まえて、"
        "下書きの内容・事実関係は変えずに、店舗のブランドトーンに合わせて自然な文章に"
        "仕上げてください。\n\n"
        f"【店舗情報】\n"
        f"店名: {STORE_NAME}（{STORE_CATEGORY}）\n"
        f"コンセプト: {BRAND_CONCEPT}\n"
        f"文体イメージ: {SNS_STYLE_HINT}\n\n"
        f"【天気データ（{LOCATION_NAME}・{day_label}）】\n"
        f"天気: {weather_data['weather_text']}\n"
        f"最高気温: {weather_data['max_temp']}℃ / 最低気温: {weather_data['min_temp']}℃\n\n"
        f"【本日おすすめしたいメニュー（在庫を売り切りたい順）】\n{item_lines}\n\n"
        f"【下書き：デジタル看板用】\n{signage_base}\n\n"
        f"【下書き：SNS投稿用】\n{sns_base}\n\n"
        "【出力形式】\n"
        "以下の2つの見出しのみを使い、それぞれの本文だけを出力してください。"
        "見出しや本文以外の説明は書かないでください。\n"
        "【サイネージ用】\n"
        "（1〜2文程度の短いキャッチコピー。絵文字は使わない）\n"
        "【SNS投稿用】\n"
        "（3〜5文程度。最後に元のハッシュタグをそのまま含める）\n"
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
            {"role": "system", "content": "あなたは飲食店の販促文作成が得意な日本語コピーライターです。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()


def parse_polished_output(text):
    """AIの出力を【サイネージ用】【SNS投稿用】で分割する。見つからない場合は全文を両方に使う。"""
    signage_match = re.search(r"【サイネージ用】\s*(.+?)(?=【SNS投稿用】|\Z)", text, re.S)
    sns_match = re.search(r"【SNS投稿用】\s*(.+)", text, re.S)

    signage = signage_match.group(1).strip() if signage_match else None
    sns = sns_match.group(1).strip() if sns_match else None

    if signage is None and sns is None:
        return text.strip(), text.strip()
    return signage or "", sns or ""


# ---------------------------------------------------------------------------
# 看板画像の生成（Pillow）
# ---------------------------------------------------------------------------

def _load_font(candidates, size):
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_vertical_gradient(img, top_color, bottom_color):
    width, height = img.size
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _draw_weather_icon(draw, cx, cy, size, category):
    r = size // 2
    if category == "sunny":
        draw.ellipse([cx - r * 0.6, cy - r * 0.6, cx + r * 0.6, cy + r * 0.6],
                     fill=(250, 175, 64))
        for i in range(8):
            import math
            angle = math.pi * 2 * i / 8
            x1 = cx + math.cos(angle) * r * 0.75
            y1 = cy + math.sin(angle) * r * 0.75
            x2 = cx + math.cos(angle) * r
            y2 = cy + math.sin(angle) * r
            draw.line([(x1, y1), (x2, y2)], fill=(250, 175, 64), width=max(3, size // 20))
    elif category == "cloudy":
        _draw_cloud(draw, cx, cy, size, (176, 190, 197))
    elif category == "rain":
        _draw_cloud(draw, cx, cy - size * 0.12, size * 0.9, (144, 164, 174))
        for i in range(3):
            x = cx - size * 0.28 + i * size * 0.28
            y0 = cy + size * 0.18
            draw.line([(x, y0), (x - size * 0.08, y0 + size * 0.28)],
                      fill=(90, 140, 210), width=max(3, size // 18))
    elif category == "snow":
        _draw_cloud(draw, cx, cy - size * 0.12, size * 0.9, (176, 190, 197))
        for i in range(3):
            x = cx - size * 0.28 + i * size * 0.28
            y = cy + size * 0.30
            draw.ellipse([x - size * 0.04, y - size * 0.04, x + size * 0.04, y + size * 0.04],
                         fill=(255, 255, 255), outline=(176, 190, 197))
    elif category == "thunder":
        _draw_cloud(draw, cx, cy - size * 0.15, size * 0.9, (120, 120, 130))
        bolt = [
            (cx + size * 0.05, cy + size * 0.10),
            (cx - size * 0.10, cy + size * 0.35),
            (cx + size * 0.02, cy + size * 0.35),
            (cx - size * 0.08, cy + size * 0.55),
            (cx + size * 0.18, cy + size * 0.28),
            (cx + size * 0.03, cy + size * 0.28),
        ]
        draw.polygon(bolt, fill=(240, 196, 25))
    else:
        draw.ellipse([cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.5],
                     outline=(150, 150, 150), width=4)


def _draw_cloud(draw, cx, cy, size, color):
    r = size * 0.28
    draw.ellipse([cx - r * 1.6, cy - r * 0.4, cx - r * 0.2, cy + r * 1.0], fill=color)
    draw.ellipse([cx - r * 0.6, cy - r * 1.0, cx + r * 0.9, cy + r * 0.8], fill=color)
    draw.ellipse([cx + r * 0.1, cy - r * 0.3, cx + r * 1.6, cy + r * 1.0], fill=color)
    draw.rectangle([cx - r * 1.5, cy, cx + r * 1.5, cy + r * 0.9], fill=color)


def _wrap_text(draw, text, font, max_width):
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        if draw.textlength(test, font=font) > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def generate_signage_image(output_path, day_label, weather_data, items, catch_copy):
    width, height = 900, 1200
    img = Image.new("RGB", (width, height), COLOR_BG_TOP)
    _draw_vertical_gradient(img, COLOR_BG_TOP, COLOR_BG_BOTTOM)
    draw = ImageDraw.Draw(img)

    font_title = _load_font(FONT_BOLD_CANDIDATES, 64)
    font_sub = _load_font(FONT_REGULAR_CANDIDATES, 26)
    font_weather = _load_font(FONT_BOLD_CANDIDATES, 40)
    font_temp = _load_font(FONT_BOLD_CANDIDATES, 34)
    font_section = _load_font(FONT_BOLD_CANDIDATES, 30)
    font_item_name = _load_font(FONT_BOLD_CANDIDATES, 28)
    font_item_price = _load_font(FONT_REGULAR_CANDIDATES, 24)
    font_catch = _load_font(FONT_BOLD_CANDIDATES, 30)

    # ヘッダー帯
    draw.rectangle([0, 0, width, 150], fill=COLOR_HEADER)
    draw.text((width / 2, 60), STORE_NAME, font=font_title, fill="white", anchor="mm")
    draw.text((width / 2, 115), f"{LOCATION_NAME}  {day_label}のおすすめ", font=font_sub,
              fill="white", anchor="mm")

    # 天気アイコン・気温
    icon_category = weather_icon_category(weather_data["weather_text"])
    _draw_weather_icon(draw, 150, 260, 140, icon_category)

    weather_text = weather_data["weather_text"] or "天気情報なし"
    draw.text((250, 220), weather_text, font=font_weather, fill=COLOR_TEXT_DARK, anchor="lm")
    max_t = weather_data["max_temp"]
    min_t = weather_data["min_temp"]
    temp_str = f"最高 {max_t}℃ / 最低 {min_t}℃" if max_t is not None and min_t is not None else "気温情報なし"
    draw.text((250, 275), temp_str, font=font_temp, fill=COLOR_ACCENT, anchor="lm")

    draw.line([(60, 340), (width - 60, 340)], fill=COLOR_CARD_BORDER, width=3)

    # おすすめメニュー
    draw.text((60, 375), "本日のおすすめメニュー", font=font_section, fill=COLOR_TEXT_DARK, anchor="lm")

    card_top = 420
    card_height = 90
    card_gap = 16
    max_cards = min(len(items), 6) if items else 0

    if max_cards == 0:
        draw.text((width / 2, card_top + 60), "（本日はおすすめ対象メニューがありません）",
                  font=font_item_name, fill=COLOR_TEXT_DARK, anchor="mm")
        content_bottom = card_top + 140
    else:
        for i in range(max_cards):
            item = items[i]
            y0 = card_top + i * (card_height + card_gap)
            y1 = y0 + card_height
            draw.rounded_radius = 16
            draw.rounded_rectangle([60, y0, width - 60, y1], radius=16,
                                    fill=COLOR_CARD_BG, outline=COLOR_CARD_BORDER, width=2)
            draw.text((90, (y0 + y1) / 2), item["name"], font=font_item_name,
                      fill=COLOR_TEXT_DARK, anchor="lm")
            draw.text((width - 90, (y0 + y1) / 2), f"{item['price']}円",
                      font=font_item_price, fill=COLOR_ACCENT, anchor="rm")
        content_bottom = card_top + max_cards * (card_height + card_gap)

    # キャッチコピー（リボン風の帯）
    ribbon_top = max(content_bottom + 30, height - 220)
    draw.rectangle([0, ribbon_top, width, height], fill=COLOR_RIBBON)

    catch_text = catch_copy.strip() or f"{day_label}は{weather_text}。あたたかいひとときをどうぞ。"
    lines = _wrap_text(draw, catch_text, font_catch, width - 100)
    line_height = 42
    total_text_height = line_height * len(lines)
    start_y = ribbon_top + (height - ribbon_top - total_text_height) / 2
    for i, line in enumerate(lines[:4]):
        draw.text((width / 2, start_y + i * line_height), line, font=font_catch,
                  fill="white", anchor="mm")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG")
    return output_path


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class WeatherMenuApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{STORE_NAME} 天気連動メニュー提案ツール")
        self.geometry("720x820")
        self.resizable(False, False)
        self.configure(bg="#fff7ec")

        self.title_font = tkfont.Font(family="Meiryo", size=14, weight="bold")
        self.normal_font = tkfont.Font(family="Meiryo", size=11)
        self.small_font = tkfont.Font(family="Meiryo", size=9)

        self.current_weather = None
        self.current_tags = set()
        self.current_candidates = []

        self._build_widgets()

    # -- 画面構築 -----------------------------------------------------

    def _build_widgets(self):
        header = tk.Frame(self, bg="#b7602d")
        header.pack(fill="x")
        tk.Label(header, text=f"{STORE_NAME}  天気連動メニュー提案・自動発信ツール",
                  font=self.title_font, bg="#b7602d", fg="white", pady=10).pack()
        tk.Label(header, text=BRAND_CONCEPT, font=self.small_font, bg="#b7602d",
                  fg="#ffe8d6", wraplength=680, pady=(0, 8)).pack()

        # 日付選択
        day_frame = tk.Frame(self, bg="#fff7ec")
        day_frame.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(day_frame, text="対象日:", font=self.normal_font, bg="#fff7ec").pack(side="left")
        self.day_var = tk.StringVar(value="today")
        tk.Radiobutton(day_frame, text="今日", variable=self.day_var, value="today",
                        font=self.normal_font, bg="#fff7ec").pack(side="left", padx=(8, 0))
        tk.Radiobutton(day_frame, text="明日", variable=self.day_var, value="tomorrow",
                        font=self.normal_font, bg="#fff7ec").pack(side="left")
        tk.Button(day_frame, text="天気を取得", font=self.normal_font,
                   command=self.on_fetch_weather, bg="#e07a22", fg="white",
                   padx=8).pack(side="left", padx=16)

        self.weather_preview = tk.Label(self, text="「天気を取得」を押してください", font=self.small_font,
                                          bg="#ffe8d6", fg="#4a2c18", justify="left", anchor="w",
                                          wraplength=680, padx=10, pady=6)
        self.weather_preview.pack(fill="x", padx=16, pady=(4, 8))

        # メニュー候補
        tk.Label(self, text="おすすめメニュー候補（複数選択可・在庫と天気タグから自動抽出）",
                  font=self.normal_font, bg="#fff7ec").pack(anchor="w", padx=16)
        list_frame = tk.Frame(self)
        list_frame.pack(padx=16, pady=(2, 8), fill="both")
        self.menu_listbox = tk.Listbox(list_frame, font=self.small_font, height=8,
                                         selectmode="extended", exportselection=False)
        self.menu_listbox.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_frame, command=self.menu_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.menu_listbox.config(yscrollcommand=scrollbar.set)

        tk.Button(self, text="在庫ファイル(stock_input.csv)を再読込", font=self.small_font,
                   command=self.on_fetch_weather).pack(anchor="w", padx=16, pady=(0, 8))

        # APIキー
        api_frame = tk.Frame(self, bg="#fff7ec")
        api_frame.pack(fill="x", padx=16, pady=(0, 4))
        tk.Label(api_frame, text="OpenAI APIキー（任意・未入力ならルールベース文章のみ）",
                  font=self.normal_font, bg="#fff7ec").pack(anchor="w")
        self.api_key_var = tk.StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        tk.Entry(api_frame, textvariable=self.api_key_var, show="*", width=50).pack(anchor="w", pady=(2, 0))

        # 生成ボタン
        self.generate_button = tk.Button(self, text="文章を生成", font=self.normal_font,
                                           bg="#2f6fed", fg="white", padx=10, pady=6,
                                           command=self.on_generate_text)
        self.generate_button.pack(pady=8)

        self.status_label = tk.Label(self, text="", font=self.small_font, bg="#fff7ec",
                                       fg="#c0392b", wraplength=680, justify="left")
        self.status_label.pack(padx=16)

        # 結果表示
        tk.Label(self, text="デジタル看板用コピー", font=self.normal_font, bg="#fff7ec").pack(
            anchor="w", padx=16, pady=(4, 0))
        self.signage_text = tk.Text(self, height=3, width=80, font=self.normal_font, wrap="word")
        self.signage_text.pack(padx=16, pady=(2, 8))

        tk.Label(self, text="SNS投稿の下書き", font=self.normal_font, bg="#fff7ec").pack(
            anchor="w", padx=16)
        self.sns_text = tk.Text(self, height=5, width=80, font=self.normal_font, wrap="word")
        self.sns_text.pack(padx=16, pady=(2, 8))

        # 画像生成
        self.image_button = tk.Button(self, text="看板画像(PNG)を生成して保存", font=self.normal_font,
                                        bg="#e07a22", fg="white", padx=10, pady=6,
                                        command=self.on_generate_image)
        self.image_button.pack(pady=(0, 8))

        tk.Label(self, text="※天気予報はウェザーニュースの公開ページから取得しています。"
                             "サイトの構造変更により取得に失敗する場合があります。",
                  font=self.small_font, bg="#fff7ec", fg="#888888").pack(side="bottom", pady=6)

    # -- 天気取得・候補表示 -----------------------------------------------

    def on_fetch_weather(self):
        self.status_label.config(text="", fg="#c0392b")
        day = self.day_var.get()
        try:
            html = fetch_html(SOURCE_URL)
            weather = parse_day_weather(html, day)
        except Exception as exc:
            self.status_label.config(text=f"天気の取得に失敗しました: {exc}")
            return

        self.current_weather = weather
        self.current_tags = classify_weather_tags(
            weather["weather_text"], weather["max_temp"], weather["min_temp"],
            weather["am_pop"], weather["pm_pop"],
        )

        day_label = "今日" if day == "today" else "明日"
        emoji = weather_emoji_char(weather["weather_text"])
        temp_str = (f"最高{weather['max_temp']}℃ / 最低{weather['min_temp']}℃"
                    if weather["max_temp"] is not None else "気温取得失敗")
        tag_str = "・".join(sorted(self.current_tags))
        self.weather_preview.config(
            text=f"{emoji} {LOCATION_NAME} / {day_label}  天気: {weather['weather_text']}  "
                 f"{temp_str}\n判定した気象タグ: {tag_str}"
        )

        stock = load_stock()
        if not stock:
            self.status_label.config(
                text=f"在庫ファイルが見つからないか空です: {STOCK_CSV_PATH}")
        candidates = recommend_menu(self.current_tags, stock)
        self.current_candidates = candidates

        self.menu_listbox.delete(0, "end")
        for c in candidates:
            self.menu_listbox.insert(
                "end",
                f"[{c['priority']}] {c['name']}（{c['category']}・{c['price']}円・在庫{c['stock']}）"
            )
        for i in range(min(DEFAULT_SELECT_COUNT, len(candidates))):
            self.menu_listbox.selection_set(i)

        if not candidates:
            self.status_label.config(
                text="本日の気象タグに合う、在庫ありのメニューが見つかりませんでした。"
                     "stock_input.csv の在庫数を確認してください。")

    def _get_selected_items(self):
        selection = self.menu_listbox.curselection()
        if not selection:
            return self.current_candidates[:DEFAULT_SELECT_COUNT]
        return [self.current_candidates[i] for i in selection]

    # -- 文章生成 ---------------------------------------------------------

    def on_generate_text(self):
        self.status_label.config(text="", fg="#c0392b")
        if self.current_weather is None:
            self.status_label.config(text="先に「天気を取得」を押してください。")
            return

        day = self.day_var.get()
        day_label = "今日" if day == "today" else "明日"
        items = self._get_selected_items()

        signage_base, sns_base = build_rule_based_texts(
            day_label, self.current_weather, self.current_tags, items)

        api_key = self.api_key_var.get().strip()
        if not api_key:
            self.signage_text.delete("1.0", "end")
            self.signage_text.insert("1.0", signage_base)
            self.sns_text.delete("1.0", "end")
            self.sns_text.insert("1.0", sns_base)
            self.status_label.config(
                text="APIキー未入力のため、ルールベースの文章をそのまま表示しています。",
                fg="#e0a800")
            return

        prompt = build_polish_prompt(day_label, self.current_weather, items, signage_base, sns_base)

        self.generate_button.config(state="disabled", text="生成中...")
        self.update_idletasks()
        try:
            polished = call_openai(api_key, DEFAULT_MODEL, prompt)
            signage_final, sns_final = parse_polished_output(polished)
            self.signage_text.delete("1.0", "end")
            self.signage_text.insert("1.0", signage_final)
            self.sns_text.delete("1.0", "end")
            self.sns_text.insert("1.0", sns_final)
            self.status_label.config(text="生成AIで仕上げた文章を表示しています。", fg="#28a745")
        except Exception as exc:
            self.signage_text.delete("1.0", "end")
            self.signage_text.insert("1.0", signage_base)
            self.sns_text.delete("1.0", "end")
            self.sns_text.insert("1.0", sns_base)
            self.status_label.config(
                text=f"生成AIでの仕上げに失敗したため、ルールベースの文章を表示しています: {exc}",
                fg="#c0392b")
        finally:
            self.generate_button.config(state="normal", text="文章を生成")

    # -- 画像生成 ---------------------------------------------------------

    def on_generate_image(self):
        self.status_label.config(text="", fg="#c0392b")
        if self.current_weather is None:
            self.status_label.config(text="先に「天気を取得」を押してください。")
            return

        day = self.day_var.get()
        day_label = "今日" if day == "today" else "明日"
        items = self._get_selected_items()
        catch_copy = self.signage_text.get("1.0", "end").strip()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(SIGNAGE_OUTPUT_DIR, f"signage_{day}_{timestamp}.png")

        try:
            generate_signage_image(output_path, day_label, self.current_weather, items, catch_copy)
            self.status_label.config(text=f"看板画像を保存しました: {output_path}", fg="#28a745")
        except Exception as exc:
            self.status_label.config(text=f"画像の生成に失敗しました: {exc}", fg="#c0392b")


def main():
    app = WeatherMenuApp()
    app.mainloop()


if __name__ == "__main__":
    main()
