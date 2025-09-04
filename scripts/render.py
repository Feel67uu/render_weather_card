# scripts/render.py
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:
    ZoneInfo = None


# ---------- пути ----------
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ICONS = ASSETS / "icons"
BASE_PANEL = ASSETS / "base_weather_plain_panel.png"
OUT_DIR = ROOT / "weather"


# ---------- шрифты ----------
def load_first_font(size: int, candidates=None):
    if candidates is None:
        candidates = [
            ASSETS / "fonts" / "Manrope-SemiBold.ttf",
            ASSETS / "fonts" / "PTSansCaption-Bold.ttf",
            ASSETS / "fonts" / "Inter-SemiBold.ttf",
            ASSETS / "fonts" / "Roboto-Bold.ttf",
        ]
    for p in candidates:
        try:
            return ImageFont.truetype(str(p), size=size)
        except Exception:
            continue
    # запасной вариант
    return ImageFont.load_default()


FONT_TITLE = load_first_font(64)
FONT_DATE = load_first_font(36, [
    ASSETS / "fonts" / "Manrope-Regular.ttf",
    ASSETS / "fonts" / "PTSansCaption-Regular.ttf",
    ASSETS / "fonts" / "Inter-Regular.ttf",
    ASSETS / "fonts" / "Roboto-Regular.ttf",
])
FONT_BIG = load_first_font(72)
FONT_REG = load_first_font(44, [
    ASSETS / "fonts" / "Manrope-Medium.ttf",
    ASSETS / "fonts" / "PTSansCaption-Regular.ttf",
    ASSETS / "fonts" / "Inter-Medium.ttf",
    ASSETS / "fonts" / "Roboto-Medium.ttf",
])
FONT_SMALL = load_first_font(40, [
    ASSETS / "fonts" / "Manrope-Regular.ttf",
    ASSETS / "fonts" / "PTSansCaption-Regular.ttf",
    ASSETS / "fonts" / "Inter-Regular.ttf",
    ASSETS / "fonts" / "Roboto-Regular.ttf",
])

WHITE = (255, 255, 255, 255)


# ---------- форматтеры ----------
def fmt_temp(v) -> str:
    try:
        fv = float(v)
    except Exception:
        return "--°C"
    return f"{int(round(fv)):+d}°C"  # +12°C / -5°C


def fmt_wind(v) -> str:
    try:
        fv = float(v)
    except Exception:
        return "ветер --"
    return f"ветер {int(round(fv))}"


def fmt_rain(p) -> str:
    try:
        fp = float(p)
    except Exception:
        return "дождь --%"
    return f"дождь {int(round(fp))}%"


RU_DOW = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
RU_MON = ["янв", "фев", "мар", "apr", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


def ru_date_short_for_tomorrow(today_iso: str, tz: str) -> str:
    """
    today_iso: 'YYYY-MM-DD'
    tz: IANA timezone, напр. 'Asia/Novokuznetsk'
    Возвращает 'Чт, 5 сен' для ЗАВТРА.
    """
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
    return f"{RU_DOW[d.weekday()]}, {d.day} {RU_MON[d.month - 1]}"


# ---------- иконки ----------
def icon_path_for_code(code_val) -> Path:
    """
    Примитивный маппинг кодов в иконки.
    Поддерживает типичные диапазоны: гроза, снег, дождь, облачно, ясно.
    """
    try:
        code = int(code_val)
    except Exception:
        code = None

    name = "cloud"  # по умолчанию

    if code is None:
        name = "cloud"
    else:
        if code >= 95:
            name = "storm"
        elif 71 <= code <= 79 or code in (85, 86):
            name = "snow"
        elif 80 <= code <= 84 or 51 <= code <= 67 or 61 <= code <= 65:
            name = "rain"
        elif code == 0:
            name = "sun"
        else:
            # лёгкая облачность/облачно
            name = "cloud"

    p = ICONS / f"{name}.png"
    if not p.exists():
        # запасные имена
        for alt in ("cloud.png", "sun.png", "rain.png", "snow.png", "storm.png"):
            q = ICONS / alt
            if q.exists():
                return q
    return p


# ---------- чтение payload ----------
def load_client_payload():
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    payload = None

    if event_path and Path(event_path).exists():
        with open(event_path, "r", encoding="utf-8") as f:
            event = json.load(f)
        payload = event.get("client_payload")

        # Если пришла строка — распарсим в объект
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                pass

    # страховка: если никак, попробуем локальный файл
    if payload is None:
        local = ROOT / "client_payload.json"
        if local.exists():
            with open(local, "r", encoding="utf-8") as f:
                payload = json.load(f)

    return payload or {}


# ---------- рендер одной колонки ----------
def render_city(draw: ImageDraw.ImageDraw, panel: Image.Image, city: dict, cx: int, top_y: int, date_text: str):
    """
    cx — центр колонки по X
    top_y — верхняя базовая Y для заголовка
    """
    name = str(city.get("name", "—")).strip()

    # заголовок (название города)
    draw.text((cx, top_y), name, font=FONT_TITLE, fill=WHITE, anchor="mm")

    # дата (на завтра) под названием
    draw.text((cx, top_y + 42), date_text, font=FONT_DATE, fill=WHITE, anchor="mm")

    # иконка
    code = (city.get("current") or {}).get("code")
    icon_file = icon_path_for_code(code)
    try:
        icon = Image.open(icon_file).convert("RGBA")
    except Exception:
        icon = Image.new("RGBA", (256, 256), (255, 255, 255, 0))

    # подгоним иконку до приятного размера
    max_w = int(panel.width * 0.22)
    if icon.width > max_w:
        ratio = max_w / icon.width
        icon = icon.resize((int(icon.width * ratio), int(icon.height * ratio)), Image.LANCZOS)

    icon_y = top_y + 120
    panel.alpha_composite(icon, (cx - icon.width // 2, icon_y))

    # текущие показатели
    cur = city.get("current") or {}
    temp = fmt_temp(cur.get("temp"))
    wind = fmt_wind(cur.get("wind"))

    # строка "температура • ветер"
    text_line = f"{temp}  •  {wind}"
    draw.text((cx, icon_y + icon.height + 60), text_line, font=FONT_REG, fill=WHITE, anchor="mm")

    # нижняя строка: диапазон и осадки
    daily = city.get("daily") or {}
    tmin = fmt_temp(daily.get("tmin"))
    tmax = fmt_temp(daily.get("tmax"))
    precip = fmt_rain(daily.get("precip_prob") if "precip_prob" in daily else daily.get("precip"))

    range_text = f"{tmin}…{tmax}"
    bottom_y = panel.height - 90

    # слева диапазон, справа осадки
    draw.text((cx - 150, bottom_y), range_text, font=FONT_SMALL, fill=WHITE, anchor="rm")
    draw.text((cx + 150, bottom_y), precip, font=FONT_SMALL, fill=WHITE, anchor="lm")


def main():
    payload = load_client_payload()

    # базовая панель
    if not BASE_PANEL.exists():
        raise FileNotFoundError(f"Не найден фон: {BASE_PANEL}")
    panel = Image.open(BASE_PANEL).convert("RGBA")
    draw = ImageDraw.Draw(panel)

    # данные
    tz = payload.get("tz") or payload.get("timezone") or ""
    today_iso = payload.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
    date_tomorrow_text = ru_date_short_for_tomorrow(today_iso, tz)

    cities = payload.get("cities") or []
    # ожидаем 2 города; если пришёл 1 — дублируем; если больше — берём первые два
    if len(cities) == 0:
        cities = [{"name": "—", "current": {}, "daily": {}} , {"name": "—", "current": {}, "daily": {}}]
    elif len(cities) == 1:
        cities = cities * 2
    else:
        cities = cities[:2]

    # геометрия: центры колонок
    W, H = panel.size
    cx_left, cx_right = int(W * 0.25), int(W * 0.75)
    title_y = 110  # базовый y для заголовка

    # РИСУЕМ ДВЕ КОЛОНКИ
    render_city(draw, panel, cities[0], cx_left, title_y, date_tomorrow_text)
    render_city(draw, panel, cities[1], cx_right, title_y, date_tomorrow_text)

    # сохранение
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    job_id = (payload.get("job_id") or "").strip()
    if not job_id:
        out = OUT_DIR / "no_job.png"
    else:
        out = OUT_DIR / f"filler-{job_id}.png"

    panel.save(out)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
