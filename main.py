import re
import os
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from generate_image import create_menu_image

NTFY_URL = os.getenv("NTFY_KEY")
base = "http://remote.gyri.cz:81/webkredit/"  # ověř přesnou adresu
url = base + "ZalozkaObjednavani.aspx"

DNY = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]
ALERGENY = {
    "1": "obiloviny", "1a": "pšenice", "1b": "žito", "1c": "ječmen", "1d": "oves",
    "2": "korýši", "3": "vejce", "4": "ryby", "5": "arašídy", "6": "sója",
    "7": "mléko", "8": "skořápkové plody", "9": "celer", "10": "hořčice",
    "11": "sezam", "12": "oxid siřičitý", "13": "vlčí bob", "14": "měkkýši",
}


def get_meals():
    s = requests.Session()
    s.get(base, timeout=15)

    soup = BeautifulSoup(s.get(url, timeout=15).text, "html.parser")
    data = {i["name"]: i.get("value", "") for i in soup.select("input[name]")}
    r = s.post(url, data=data, timeout=15)
    r.encoding = "utf-8"

    lines = BeautifulSoup(r.text, "html.parser").get_text("\n", strip=True).split("\n")

    meals = {}
    date = None
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"(Oběd|Snídaně|Svačina|Večeře)\s*-\s*(\d{1,2}\.\d{1,2}\.\d{4})", line)
        if m:
            date = m.group(2)
            meals[date] = []
        elif date and line.isdigit() and i + 1 < len(lines):
            text = lines[i + 1]
            a = re.search(r"A:\s*([\w,]+)", text)
            allergens = a.group(1).split(",") if a else []
            name = re.sub(r"\s+", " ", re.sub(r"A:\s*[\w,]+", "", text)).strip(" ,")
            meals[date].append({"alt": int(line), "name": name, "allergens": allergens})
            i += 1
        elif line.startswith("Jídla obsahují alergeny"):
            date = None
        i += 1
    return meals


def format_meal(it):
    alerg = ", ".join(ALERGENY.get(a, a) for a in it["allergens"])
    line = f"{it['alt']}) {it['name']}"
    return f"{line}\n    ⚠ alergeny: {alerg}" if alerg else line


def send_ntfy(title, message):
    r = requests.post(
        NTFY_URL,
        data=message.encode("utf-8"),                       # prostý text jako UTF-8
        params={"title": title, "tags": "fork_and_knife"},  # titulek přes URL
        headers={"Content-Type": "text/plain; charset=utf-8"},
        timeout=15,
    )
    r.raise_for_status()


if __name__ == "__main__":
    meals = get_meals()
    now = datetime.now()
    items = meals.get(now.strftime("%d.%m.%Y")) or meals.get(now.strftime("%d.%m.%Y").lstrip("0"))

    if items:
        title = f"🍽 Oběd – {DNY[now.weekday()]} {now.day}. {now.month}."
        message = "\n\n".join(format_meal(it) for it in items)
        send_ntfy(title, message)
        image_path = create_menu_image(message, title=title, output_path="menu.png")
        print(f"Obrázek pro Instagram byl uložen do: {image_path}")
    else:
        print("Dnes žádné menu (víkend/prázdniny?), nic se neposílá.")