import os
import re
import json
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CONFIGURED_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
BRAVE_API_KEY = os.environ["BRAVE_SEARCH_API_KEY"]
EVENT_NAME = os.environ.get("GITHUB_EVENT_NAME", "")
HOME_REGION = "Valencia"

STATE = Path("data/seen.json")
LATEST = Path("data/latest.json")
STATE.parent.mkdir(parents=True, exist_ok=True)

SEARCHES = [
    (
        "Wallapop · CRT / vídeo",
        'site:es.wallapop.com/item/ ("Sony PVM" OR "Sony BVM" OR "Sony Trinitron" OR "JVC TM" OR "monitor broadcast" OR "monitor profesional video" OR "monitor BNC" OR "TV de tubo" OR "televisor CRT" OR "videowall CRT" OR "video wall" OR "muro de televisores" OR "Edirol V4" OR "Edirol V8" OR "Roland LVS-400" OR "Time Base Corrector" OR "TBC video" OR "Extron" OR "Ikegami" OR "VIDEONICS")',
    ),
    (
        "Vinted · CRT / vídeo",
        'site:vinted.es/items/ ("Sony PVM" OR "Sony BVM" OR "Sony Trinitron" OR "JVC TM" OR "monitor broadcast" OR "monitor profesional video" OR "monitor BNC" OR "TV de tubo" OR "televisor CRT" OR "videowall CRT" OR "Edirol V4" OR "Edirol V8" OR "Time Base Corrector" OR "TBC video" OR "Extron" OR "Ikegami" OR "VIDEONICS")',
    ),
    (
        "Facebook Marketplace · CRT / vídeo",
        'site:facebook.com/marketplace/item/ ("España" OR "Spain" OR "Madrid" OR "Barcelona" OR "Valencia" OR "Sevilla" OR "Zaragoza" OR "Málaga" OR "Alicante" OR "Murcia" OR "Bilbao" OR "Valladolid" OR "Vigo" OR "A Coruña" OR "Granada" OR "Córdoba" OR "Palma" OR "Tenerife" OR "Las Palmas") ("Sony PVM" OR "Sony BVM" OR "Sony Trinitron" OR "JVC TM" OR "monitor broadcast" OR "monitor profesional video" OR "monitor BNC" OR "TV de tubo" OR "televisor CRT" OR "videowall CRT" OR "video wall" OR "muro de televisores" OR "Edirol V4" OR "Edirol V8" OR "Roland LVS-400" OR "Time Base Corrector" OR "TBC video" OR "Extron" OR "Ikegami" OR "VIDEONICS")',
    )
]


def brave_search(query):
    params = urllib.parse.urlencode(
        {
            "q": query,
            "country": "ES",
            "search_lang": "es",
            "count": 20,
            "safesearch": "off",
        }
    )
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": BRAVE_API_KEY,
            "User-Agent": "CRTStalker/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Brave Search API error {exc.code}: {body}") from exc

    results = []
    for item in data.get("web", {}).get("results", []):
        results.append(
            {
                "title": (item.get("title") or "").strip(),
                "link": (item.get("url") or "").strip(),
                "desc": (item.get("description") or "").strip(),
            }
        )
    return results


def platform_for(link):
    host = urlparse(link).netloc.lower()
    if "wallapop.com" in host:
        return "Wallapop"
    if "vinted.es" in host:
        return "Vinted"
    if "facebook.com" in host:
        return "Facebook Marketplace"
    return None


def is_facebook_spain(item):
    if item.get("platform") != "Facebook Marketplace":
        return True

    text = f"{item.get('title', '')} {item.get('desc', '')}".lower()

    spain_terms = [
        "españa", "spain", "madrid", "barcelona", "valencia", "valència",
        "sevilla", "zaragoza", "málaga", "malaga", "alicante", "murcia",
        "bilbao", "valladolid", "vigo", "a coruña", "coruña", "granada",
        "córdoba", "cordoba", "palma", "mallorca", "tenerife", "las palmas",
        "castellón", "castellon", "gijón", "gijon", "oviedo", "pamplona",
        "santander", "salamanca", "toledo", "albacete", "badajoz"
    ]
    return any(term in text for term in spain_terms)


def extract_price_value(text):
    match = re.search(r"(?<!\d)(\d{1,5}(?:[\.,]\d{1,2})?)\s?(?:€|EUR)", text or "", re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def extract_price(text):
    value = extract_price_value(text)
    if value is None:
        return None
    if value.is_integer():
        return f"{int(value)} €"
    return f"{value:.2f} €".replace(".", ",")


def is_consumer_crt_tv(item):
    title = (item.get("title") or "").lower()
    desc = (item.get("desc") or "").lower()
    text = f"{title} {desc}"

    professional_terms = [
        "sony pvm", "sony bvm", "jvc tm", "monitor broadcast",
        "monitor profesional", "monitor bnc", "ikagami", "ikegami"
    ]
    if any(term in text for term in professional_terms):
        return False

    tv_terms = [
        "sony trinitron", "tv de tubo", "televisor de tubo",
        "television de tubo", "televisión de tubo", "televisor crt",
        "television crt", "televisión crt", "tv crt",
        "tubo catodico", "tubo catódico"
    ]
    return any(term in text for term in tv_terms)


def is_allowed_by_price(item):
    if not is_consumer_crt_tv(item):
        return True

    price = extract_price_value(f"{item.get('title', '')} {item.get('desc', '')}")
    return price is not None and price < 400


def is_sold_or_unavailable(item):
    text = f"{item.get('title', '')} {item.get('desc', '')}".lower()

    unavailable_terms = [
        "vendido", "vendida", "sold", "reservado", "reservada",
        "no disponible", "ya no está disponible", "ya no esta disponible",
        "artículo vendido", "articulo vendido", "producto vendido",
        "agotado", "retirado", "retirada"
    ]
    return any(term in text for term in unavailable_terms)


def is_valencia(item):
    text = f"{item.get('title', '')} {item.get('desc', '')}".lower()
    terms = [
        "valencia", "valència", "torrent", "paterna", "mislata",
        "burjassot", "sagunto", "sagunt", "gandia", "gandía",
        "alzira", "xirivella", "manises", "quart de poblet"
    ]
    return any(term in text for term in terms)


def is_unwanted_vhs_media(item):
    """
    Descarta anuncios de cintas/cassettes/películas VHS,
    pero conserva hardware VHS como cámaras, reproductores y grabadores.
    """
    title = (item.get("title") or "").lower()
    desc = (item.get("desc") or "").lower()
    text = f"{title} {desc}"

    camera_terms = [
        "camara", "cámara", "videocamara", "videocámara", "camcorder"
    ]
    if any(term in title for term in camera_terms):
        return False

    unwanted_vhs_hardware = [
        "reproductor vhs", "grabador vhs", "videograbador", "video grabador",
        "vcr", "magnetoscopio", "vhs player", "vhs recorder",
        "video recorder", "video player", "deck vhs", "vhs deck"
    ]
    if any(term in text for term in unwanted_vhs_hardware):
        return True

    media_terms_title = [
        "cinta vhs", "cintas vhs", "cassette vhs", "cassettes vhs",
        "casete vhs", "casetes vhs", "pelicula vhs", "película vhs",
        "peliculas vhs", "películas vhs", "lote vhs", "vhs tape",
        "vhs tapes", "video cassette", "videocassette",
        "cinta virgen", "cintas virgenes", "cintas vírgenes"
    ]
    if any(term in title for term in media_terms_title):
        return True

    strong_desc_terms = [
        "lote de cintas vhs", "lote cintas vhs", "coleccion de vhs",
        "colección de vhs", "peliculas en vhs", "películas en vhs",
        "cassettes vhs", "cintas vhs grabadas"
    ]
    return any(term in text for term in strong_desc_terms)


def telegram_private_chats():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    req = urllib.request.Request(url, headers={"User-Agent": "CRTStalker/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    chats = {}
    for update in data.get("result", []):
        msg = update.get("message") or update.get("edited_message") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") == "private" and "id" in chat:
            chats[str(chat["id"])] = {
                "id": str(chat["id"]),
                "first_name": chat.get("first_name"),
                "username": chat.get("username"),
            }
    return list(chats.values())


def send_to_chat(chat_id, message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": "false",
        }
    ).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API error {exc.code}: {body}") from exc


def send(message):
    if CONFIGURED_CHAT_ID:
        try:
            send_to_chat(CONFIGURED_CHAT_ID, message)
            return
        except RuntimeError as exc:
            if "chat not found" not in str(exc):
                raise
            print("El TELEGRAM_CHAT_ID configurado no existe para este bot; intentando detectar el chat privado.")

    chats = telegram_private_chats()
    if len(chats) != 1:
        raise RuntimeError(
            f"No pude seleccionar un único chat privado de Telegram. Chats detectados: {json.dumps(chats, ensure_ascii=False)}"
        )

    fallback_id = chats[0]["id"]
    print(f"Usando automáticamente el chat privado detectado: {fallback_id}")
    send_to_chat(fallback_id, message)


seen = set()
if STATE.exists():
    try:
        seen = set(json.loads(STATE.read_text(encoding="utf-8")))
    except Exception:
        seen = set()

found = []
for label, query in SEARCHES:
    try:
        results = brave_search(query)
        valid = 0
        for item in results:
            platform = platform_for(item["link"])
            if platform:
                item["platform"] = platform

            if (
                platform
                and is_facebook_spain(item)
                and not is_unwanted_vhs_media(item)
                and is_allowed_by_price(item)
                and not is_sold_or_unavailable(item)
            ):
                found.append(item)
                valid += 1
        print(f"{label}: {len(results)} resultados Brave, {valid} anuncios válidos.")
    except Exception as exc:
        print(f"Search failed [{label}]: {exc}")

dedup = {}
for item in found:
    dedup[item["link"]] = item
found = list(dedup.values())

latest_snapshot = []
for item in found:
    text_for_price = f"{item.get('title', '')} {item.get('desc', '')}"
    latest_snapshot.append(
        {
            "title": item.get("title", ""),
            "platform": item.get("platform", ""),
            "price": extract_price(text_for_price),
            "location": "Valencia / cerca" if is_valencia(item) else "España",
            "link": item.get("link", ""),
        }
    )

LATEST.write_text(
    json.dumps(latest_snapshot, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

for item in latest_snapshot:
    print(
        f"VALID | {item['platform']} | {item['price'] or 'sin precio'} | "
        f"{item['title']} | {item['link']}"
    )

first_run = not seen
new_items = [item for item in found if item["link"] not in seen]
new_items.sort(key=lambda item: (not is_valencia(item), item["platform"], item["title"].lower()))

if first_run:
    print(f"Primera ejecución con Brave: guardando {len(found)} anuncios existentes sin notificar.")
    if EVENT_NAME in {"push", "workflow_dispatch"}:
        send(
            f"✅ CRTStalker conectado. Brave Search funciona y he cargado {len(found)} anuncios como base. "
            "A partir de ahora te avisaré solo de enlaces nuevos."
        )
else:
    print(f"Encontrados {len(found)} anuncios; nuevos: {len(new_items)}.")
    for item in new_items:
        price = extract_price(item["title"] + " " + item["desc"])
        price_line = f" · {price}" if price else ""
        location_line = "📍 Valencia / cerca" if is_valencia(item) else "🇪🇸 España"
        message = (
            f"🔴 {item['title']}\n"
            f"{item['platform']}{price_line}\n"
            f"{location_line}\n"
            f"{item['link']}"
        )
        send(message)
        print("Sent:", item["link"])

seen.update(item["link"] for item in found)
STATE.write_text(
    json.dumps(sorted(seen), ensure_ascii=False, indent=2),
    encoding="utf-8",
)
