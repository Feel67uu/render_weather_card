# scripts/render.py
import os, json, math
from PIL import Image, ImageDraw, ImageFont

# ---------- utils ----------
def _payload():
    """Read client_payload from the GitHub event file."""
    ev_path = os.environ.get("GITHUB_EVENT_PATH")
    if not ev_path or not os.path.exists(ev_path):
        return {}
    with open(ev_path, "r", encoding="utf-8") as f:
        ev = json.load(f)
    return (ev or {}).get("client_payload", {}) or {}

def _as_lines(x):
    """Accept list or string with \\n, return list[str] without empties around."""
    if x is None:
        return []
    if isinstance(x, list):
        return [str(s).strip() for s in x if str(s).strip() != ""]
    # string
    return [s.strip() for s in str(x).replace("\r", "").split("\n")]

def _pick_font(size, bold=False):
    """Pick a font with Cyrillic support."""
    cands = []
    if bold:
        cands += [
            "assets/fonts/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        cands += [
            "assets/fonts/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for p in cands:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                pass
    return ImageFont.load_default()

# ---------- main ----------
def main():
    p = _payload()
    job_id = str(p.get("job_id") or "demo").strip()

    head  = str(p.get("head") or "").strip()
    left  = _as_lines(p.get("left"))
    right = _as_lines(p.get("right"))
    icon  = str(p.get("icon") or "sun").strip().lower()

    # base & icons
    base_path = "assets/base_weather_plain_panel.png"
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"Missing {base_path}")

    base = Image.open(base_path).convert("RGBA")
    W, H = base.size
    draw = ImageDraw.Draw(base)

    # fonts
    head_font = _pick_font(size=max(34, H // 13), bold=True)
    body_font = _pick_font(size=max(20, H // 23), bold=False)

    # icon
    icon_path = f"assets/icons/{icon}.png"
    if os.path.exists(icon_path):
        ico = Image.open(icon_path).convert("RGBA")
        size = int(min(W, H) * 0.22)
        ico = ico.resize((size, size), Image.LANCZOS)
        base.paste(ico, (int(W * 0.06), int(H * 0.20)), ico)

    # head
    if head:
        draw.text((int(W * 0.40), int(H * 0.10)), head, fill=(255, 255, 255, 255), font=head_font)

    # columns
    start_y = int(H * 0.55)
    line_h = int(body_font.size * 1.4)
    left_x  = int(W * 0.08)
    right_x = int(W * 0.56)

    for i, line in enumerate(left[:10]):   # ограничим, чтобы не вылезало
        draw.text((left_x, start_y + i * line_h), line, fill=(255, 255, 255, 255), font=body_font)

    for i, line in enumerate(right[:10]):
        draw.text((right_x, start_y + i * line_h), line, fill=(255, 255, 255, 255), font=body_font)

    # output
    out_dir = "weather"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{job_id}.png")
    base.save(out_path, "PNG")
    print("Saved:", out_path)

if __name__ == "__main__":
    main()
