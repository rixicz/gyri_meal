"""Generátor obrázků jídelního lístku pro Instagram.

Přebírá text z main.py (formátovaný pro ntfy) a vytváří moderní čtvercový obrázek (1080x1080 px)
vhodný pro sdílení na Instagramu (post, story).
"""

from __future__ import annotations

import argparse
import os
import re
from typing import Any, Sequence
from PIL import Image, ImageDraw, ImageFont

# Barevná schémata pro grafiku
THEMES = {
    "dark": {
        "bg": "#0B0F19",
        "header_tag": "#38BDF8",  # sky blue
        "title": "#F8FAFC",
        "divider": "#1E293B",
        "card_bg": "#131C2E",
        "card_border": "#1E293B",
        "name": "#F8FAFC",
        "allergen": "#94A3B8",
        "footer": "#64748B",
        "badges": ["#2563EB", "#059669", "#D97706", "#7C3AED"],
    },
    "light": {
        "bg": "#F8FAFC",
        "header_tag": "#0284C7",
        "title": "#0F172A",
        "divider": "#E2E8F0",
        "card_bg": "#FFFFFF",
        "card_border": "#E2E8F0",
        "name": "#0F172A",
        "allergen": "#64748B",
        "footer": "#94A3B8",
        "badges": ["#2563EB", "#059669", "#D97706", "#7C3AED"],
    },
}


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Načte vhodný systémový TTF font s podporou české diakritiky."""
    names = (
        [
            "DejaVuSans-Bold.ttf",
            "LiberationSans-Bold.ttf",
            "Arial-Bold.ttf",
            "arialbd.ttf",
            "Helvetica-Bold.ttf",
        ]
        if bold
        else [
            "DejaVuSans.ttf",
            "LiberationSans-Regular.ttf",
            "Arial.ttf",
            "arial.ttf",
            "Helvetica.ttf",
        ]
    )

    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass

    # Zkusit běžné cesty na linuxových a unixových distribucích
    system_paths = [
        f"/usr/share/fonts/truetype/dejavu/{'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'}",
        f"/usr/share/fonts/truetype/liberation/{'LiberationSans-Bold.ttf' if bold else 'LiberationSans-Regular.ttf'}",
        f"/usr/share/fonts/TTF/{'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'}",
        f"/usr/share/fonts/liberation/{'LiberationSans-Bold.ttf' if bold else 'LiberationSans-Regular.ttf'}",
    ]
    for path in system_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass

    return ImageFont.load_default()


def wrap_text_by_width(
    text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw
) -> list[str]:
    """Zalamuje text po slovech tak, aby nepřekročil maximální šířku v pixelech."""
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current_line: list[str] = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_w = bbox[2] - bbox[0]
        if line_w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []

    if current_line:
        lines.append(" ".join(current_line))

    return lines


def parse_menu_text(message: str) -> list[dict[str, str]]:
    """Převede text ze zprávy ntfy na strukturovaný seznam jídel.

    Očekává formát jako:
    1) Jméno jídla
        ⚠ alergeny: pšenice, vejce
    """
    meals: list[dict[str, str]] = []
    blocks = [b.strip() for b in message.strip().split("\n\n") if b.strip()]

    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        first_line = lines[0]
        match_num = re.match(r"^(\d+)[\.\)]\s*(.+)$", first_line)
        if match_num:
            num = match_num.group(1)
            name = match_num.group(2).strip()
        else:
            num = str(len(meals) + 1)
            name = first_line

        allergens = ""
        for line in lines[1:]:
            al_match = re.search(r"alergeny:\s*(.+)", line, re.IGNORECASE)
            if al_match:
                allergens = al_match.group(1).strip()
            elif not allergens:
                name += " " + line

        meals.append({"num": num, "name": name, "allergens": allergens})

    return meals


def clean_title_text(raw_title: str) -> str:
    """Odstraní problematické emoji pro vykreslení a hezky naformátuje titulek."""
    # Odstranění emoji bloků
    cleaned = re.sub(r"[\U00010000-\U0010ffff]", "", raw_title).strip()
    cleaned = re.sub(r"^[🍽🍲🍴\s\-–]+", "", cleaned).strip()

    # Zvýraznění velkého písmena po pomlčce, pokud jde např. o 'Oběd – středa 21. 10.'
    if "–" in cleaned or "-" in cleaned:
        parts = re.split(r"(\s*[\-–]\s*)", cleaned, maxsplit=1)
        if len(parts) == 3:
            prefix, sep, rest = parts
            rest = rest[:1].upper() + rest[1:] if rest else ""
            cleaned = f"{prefix}{sep}{rest}"

    return cleaned or "Dnešní obědové menu"


def create_menu_image(
    message: str | Sequence[dict[str, Any]],
    title: str = "Obědové menu",
    output_path: str = "menu.png",
    theme: str = "dark",
    width: int = 1080,
    height: int = 1920,
) -> str:
    """Vytvoří obrázek s jídelním lístkem pro Instagram a uloží jej do souboru.

    Args:
        message: Buď řetězec z main.py odesílaný do ntfy, nebo seznam slovníků jídel.
        title: Titulek menu (např. '🍽 Oběd – středa 21. 10.').
        output_path: Cesta pro uložení výsledného PNG/JPG.
        theme: Barevné schéma ('dark' nebo 'light').
        width: Šířka obrázku v pixelech (výchozí 1080).
        height: Výška obrázku v pixelech (výchozí 1080).

    Returns:
        Cesta k vygenerovanému obrázku.
    """
    colors = THEMES.get(theme, THEMES["dark"])

    # Příprava jídel – podpora jak řetězce z ntfy, tak přímo objektů z get_meals()
    if isinstance(message, str):
        meals = parse_menu_text(message)
    elif isinstance(message, (list, tuple)):
        meals = []
        for it in message:
            num = str(it.get("alt", len(meals) + 1))
            name = it.get("name", "")
            raw_al = it.get("allergens", [])
            al_str = ", ".join(raw_al) if isinstance(raw_al, list) else str(raw_al)
            meals.append({"num": num, "name": name, "allergens": al_str})
    else:
        meals = []

    # Inicializace plátna
    img = Image.new("RGB", (width, height), color=colors["bg"])
    draw = ImageDraw.Draw(img)

    # Načtení fontů různých velikostí
    font_header_tag = get_font(20, bold=True)
    font_title = get_font(42, bold=True)
    font_badge = get_font(28, bold=True)
    font_meal_name = get_font(28, bold=True)
    font_allergen = get_font(20, bold=False)
    font_footer = get_font(20, bold=False)

    # 1. Horní záhlaví (Header)
    header_x = 70
    header_y = 65

    draw.text(
        (header_x, header_y),
        "GYMNÁZIUM RUMBURK • ŠKOLNÍ JÍDELNA",
        fill=colors["header_tag"],
        font=font_header_tag,
    )

    clean_title = clean_title_text(title)
    draw.text(
        (header_x, header_y + 32),
        clean_title,
        fill=colors["title"],
        font=font_title,
    )

    # Dělící linka pod hlavičkou
    draw.line(
        [(header_x, header_y + 96), (width - header_x, header_y + 96)],
        fill=colors["divider"],
        width=2,
    )

    # 2. Zápatí (Footer)
    footer_y = height - 65
    draw.text(
        (width // 2, footer_y),
        "gyri.cz • Dobrou chuť!",
        fill=colors["footer"],
        font=font_footer,
        anchor="mm",
    )

    # 3. Karty s jídly
    if meals:
        card_x = 70
        card_w = width - 140
        start_y_area = header_y + 120
        end_y_area = footer_y - 45
        available_h = end_y_area - start_y_area

        gap = 22
        # Maximální výška karty, aby při malém počtu jídel nebyly karty nepřirozeně obří
        max_card_h = 240
        raw_card_h = (available_h - (len(meals) - 1) * gap) // len(meals)
        card_h = min(max_card_h, raw_card_h)

        # Vertikální vystředění skupiny karet
        total_group_h = len(meals) * card_h + (len(meals) - 1) * gap
        offset_y = start_y_area + (available_h - total_group_h) // 2

        badge_w, badge_h = 64, 64
        badges = colors["badges"]

        for i, meal in enumerate(meals):
            cy = offset_y + i * (card_h + gap)

            # Rámeček karty
            draw.rounded_rectangle(
                [card_x, cy, card_x + card_w, cy + card_h],
                radius=24,
                fill=colors["card_bg"],
                outline=colors["card_border"],
                width=2,
            )

            # Číselný odznak (badge)
            badge_color = badges[i % len(badges)]
            bx = card_x + 30
            by = cy + 28
            draw.rounded_rectangle(
                [bx, by, bx + badge_w, by + badge_h],
                radius=18,
                fill=badge_color,
            )

            num_bbox = draw.textbbox((0, 0), meal["num"], font=font_badge)
            num_w = num_bbox[2] - num_bbox[0]
            num_h = num_bbox[3] - num_bbox[1]
            draw.text(
                (bx + (badge_w - num_w) // 2, by + (badge_h - num_h) // 2 - 2),
                meal["num"],
                fill="#FFFFFF",
                font=font_badge,
            )

            # Název jídla s automatickým zalamováním
            text_x = bx + badge_w + 24
            max_text_w = card_w - (text_x - card_x) - 30
            wrapped_lines = wrap_text_by_width(meal["name"], font_meal_name, max_text_w, draw)

            ty = cy + 28
            for line in wrapped_lines:
                draw.text((text_x, ty), line, fill=colors["name"], font=font_meal_name)
                ty += 38

            # Alergeny
            if meal["allergens"]:
                ay = cy + card_h - 48
                draw.text(
                    (text_x, ay),
                    f"Alergeny: {meal['allergens']}",
                    fill=colors["allergen"],
                    font=font_allergen,
                )

    # Uložení obrázku
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, quality=95)
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generátor obrázků jídelního lístku pro Instagram")
    parser.add_argument("--title", default="Oběd – Dnes", help="Titulek obrázku")
    parser.add_argument("--theme", default="dark", choices=["dark", "light"], help="Téma vzhledu")
    parser.add_argument("--output", default="menu.png", help="Výstupní soubor")
    args = parser.parse_args()

    sample_message = """1) Fazolové lusky na smetaně, vejce, brambory
    ⚠ alergeny: pšenice, vejce, mléko

2) Rozlítaný ptáček, rýže
    ⚠ alergeny: pšenice, vejce, hořčice

3) Bramborové nočky s ovocným přelivem , mléko
    ⚠ alergeny: pšenice, vejce, mléko"""

    out = create_menu_image(sample_message, title=args.title, output_path=args.output, theme=args.theme)
    print(f"Obrázek byl úspěšně vygenerován: {out}")
