# scripts/render.py
# Рендер карточки погоды для двух городов.
# Читает client_payload из GITHUB_EVENT_PATH (repository_dispatch),
# рисует PNG и сохраняет в weather/<job_id>.png

from __future__ import annotations
import json, os
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:
    ZoneInfo = None

ROOT       = Path(__file__).resolve().parents[1]
ASSETS     = ROOT / "assets"
FONTS_DIR  = ASSETS / "fonts"
ICONS_DIR  = ASSETS / "icons"
PANEL_PATH = ASSETS / "base_weather_plain_panel.png"

WHITE = (255, 255, 255, 255)
RU_DOW = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
RU_MON = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]

# ---------- helpers ----------

def load_payload() -> dict:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        return {}
    with open(event_path, "r", encoding="utf-8") as f:
        evt = json.load(f)
    return evt.get("client_payload") or {}

def ru_date_tomorrow(today_iso: str, tz: str) -> str:
    try:
        dt = datetime.strptime(today_iso, "%Y-%m-%d")
    except Exception:
        dt = datetime.utcnow()
    if ZoneInfo and tz:
        try:
            dt = dt.replace(tzinfo=ZoneInfo(tz))
        except Exception:
            pass
    d = (dt + timedelta(days=1)).date()
    return f"{RU_DOW[d.weekday()]}, {d.day} {RU_MON[d.month-1]}"

def to_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def fmt_temp(v) -> str:
    return f"{int(round(to_float(v))):+d}°C"

def fmt_wind(v) -> str:
    return f"ветер {int(round(to_float(v)))}"

def fmt_rain(p) -> str:
    return f"дождь {int(round(to_float(p)))}%"

def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    # 1) Пробуем твои Roboto
    prefer = FONTS_DIR / ("Roboto-Bold.ttf" if bold else "Roboto-Regular.ttf")
    if prefer.exists():
        return ImageFont.truetype(str(prefer), size=size)

    # 2) Любые другие шрифты в assets/fonts
    for cand in FONTS_DIR.glob("*.ttf"):
        try:
            return ImageFont.truetype(str(cand), size=size)
        except Exception:
            pass

    # 3) Системные фолбэки (на хосте GitHub Actions есть DejaVu)
    sys_regular = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    sys_bold    = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    try:
        return ImageFont.truetype(str(sys_bold if bold else sys_regular), size=size)
    except Exception:
        return ImageFont.load_default()

def icon_path(code: int) -> Path:
    c = int(to_float(code))
    if c in (95, 96, 99):                          # гроза
        name = "storm.png"
    elif c in (71, 73, 75, 77, 85, 86):            # снег
        name = "snow.png"
    elif c in (51, 53, 55, 61, 63, 65, 80, 81, 82):# дождь/морось
        name = "rain.png"
    elif c in (0, 1):                              # ясно
        name = "sun.png"
    else:                                          # облачно (дефолт)
        name = "cloud.png"
    p = ICONS_DIR / name
    return p if p.exists() else ICONS_DIR / "cloud.png"

def paste_center(dst: Image.Image, src: Image.Image, cx: int, cy: int):
    w, h = src.size
    dst.paste(src, (int(cx - w/2), int(cy - h/2)), src if src.mode == "RGBA" else None)

# ---------- drawing ----------

def draw_city(draw: ImageDraw.ImageDraw, canvas: Image.Image, cx: int, top_y: int,
              city: dict, payload: dict, fonts: dict):
    W, H = canvas.size

    # Название
    title = (city.get("name") or "—").strip()
    draw.text((cx, top_y), title, fill=WHITE, font=fonts["title"], anchor="mm")

    # Дата ЗАВТРА сразу под названием
    date_text = ru_date_tomorrow(payload.get("date", ""), payload.get("tz", ""))
    draw.text((cx, top_y + fonts["title_lead"]), date_text, fill=WHITE, font=fonts["small"], anchor="mm")

    # Иконка
    cur = city.get("current") or {}
    code = cur.get("code", 3)
    try:
        ico = Image.open(icon_path(code)).convert("RGBA")
    except Exception:
        ico = Image.new("RGBA", (256,256), (255,255,255,0))
    ih = int(H * 0.28)
    iw = int(ih * ico.width / ico.height)
    ico = ico.resize((iw, ih), Image.LANCZOS)
    paste_center(canvas, ico, cx, int(H*0.48))

    # Текущие: температура со знаком и ветер
    temp_txt = fmt_temp(cur.get("temp", 0))
    wind_txt = fmt_wind(cur.get("wind", 0))
    main_line = f"{temp_txt}  •  {wind_txt}"
    draw.text((cx, int(H*0.70)), main_line, fill=WHITE, font=fonts["medium"], anchor="mm")

    # Низ: диапазон и вероятность дождя
    daily = city.get("daily") or {}
    range_txt = f"{fmt_temp(daily.get('tmin', 0))}…{fmt_temp(daily.get('tmax', 0))}"
    rain_txt  = fmt_rain(daily.get("precip_prob", 0))

    col_w  = W // 2
    left_x = cx - col_w//2 + int(W*0.06)
    right_x= cx + col_w//2 - int(W*0.06)

    draw.text((left_x,  int(H*0.86)), range_txt, fill=WHITE, font=fonts["small"], anchor="lm")
    draw.text((right_x, int(H*0.86)), rain_txt,  fill=WHITE, font=fonts["small"], anchor="rm")

# ---------- main ----------

def main():
    payload = load_payload()
    job_id  = str(payload.get("job_id") or "no_job").strip()

    out_dir = ROOT / "weather"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{job_id}.png"

    # База
    if PANEL_PATH.exists():
        img = Image.open(PANEL_PATH).convert("RGBA")
    else:
        img = Image.new("RGBA", (1600, 900), (17, 22, 30, 255))
    draw = ImageDraw.Draw(img)
    W, H = img.size

    cities = payload.get("cities") or []
    if len(cities) < 2:
        draw.text((W//2, H//2), "Нет данных", fill=WHITE, font=load_font(64, True), anchor="mm")
        img.save(out_path)
        print(f"Saved: {out_path}")
        return

    # Шрифты Roboto
    fonts = {
        "title":      load_font(int(H*0.060), bold=True),
        "title_lead": int(H*0.050),  # вертикальный сдвиг под датой
        "medium":     load_font(int(H*0.050), bold=False),
        "small":      load_font(int(H*0.040), bold=False),
    }

    cx_left, cx_right = W//4, 3*W//4
    title_y = int(H*0.12)

    draw_city(draw, img, cx_left,  title_y, cities[0], payload, fonts)
    draw_city(draw, img, cx_right, title_y, cities[1], payload, fonts)

    img.save(out_path)
    print(f"Saved: {out_path}")

if __name__ == "__main__":
    main()
