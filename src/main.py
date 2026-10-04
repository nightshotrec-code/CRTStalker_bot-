import os, re, json, html, urllib.parse, urllib.request, urllib.error
from pathlib import Path
from xml.etree import ElementTree as ET

CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
EVENT_NAME = os.environ.get("GITHUB_EVENT_NAME", "")

SEARCHES = [
    # Monitores profesionales / CRT
    'site:es.wallapop.com ("Sony PVM" OR "Sony BVM" OR "JVC TM" OR "monitor broadcast" OR "monitor profesional video" OR "monitor BNC")',
    'site:vinted.es ("Sony PVM" OR "Sony BVM" OR "JVC TM" OR "monitor broadcast" OR "monitor profesional video" OR "monitor BNC")',

    # TV de tubo / videowall
    'site:es.wallapop.com ("TV de tubo" OR "televisor de tubo" OR "televisor CRT" OR "CRT TV" OR "videowall CRT" OR "video wall antiguo" OR "muro de televisores")',
    'site:vinted.es ("TV de tubo" OR "televisor de tubo" OR "televisor CRT" OR "CRT TV" OR "videowall CRT" OR "video wall antiguo")',

    # Mezcla y procesado
    'site:es.wallapop.com ("Edirol V4" OR "Edirol V8" OR "Roland LVS-400" OR "Time Base Corrector" OR "TBC video" OR "frame synchronizer" OR "video mixer" OR "mezclador de video")',
    'site:vinted.es ("Edirol V4" OR "Edirol V8" OR "Time Base Corrector" OR "TBC video" OR "video mixer" OR "mezclador de video")',

    # Cámaras de vídeo analógicas
    'site:es.wallapop.com ("camara VHS" OR "videocamara VHS" OR "VHS-C" OR "S-VHS" OR "Video8" OR "Hi8" OR "Betacam" OR "U-matic" OR "camara ENG" OR "camara broadcast")',
    'site:vinted.es ("camara VHS" OR "videocamara VHS" OR "VHS-C" OR "S-VHS" OR "Video8" OR "Hi8" OR "Betacam" OR "camara analogica")',

    # Cámaras de cine antiguas
    'site:es.wallapop.com ("camara Super 8" OR "camara 8mm" OR "camara 16mm" OR "camara de cine antigua" OR "film camera")',
    'site:vinted.es ("camara Super 8" OR "camara 8mm" OR "camara 16mm" OR "camara de cine antigua" OR "film camera")',

    # CCTV / procesadores / accesorios de vídeo
    'site:es.wallapop.com ("camara CCTV antigua" OR "Ikegami" OR "Extron" OR "matrix BNC" OR "video processor" OR "scan converter" OR "C-mount")',
    'site:vinted.es ("camara CCTV" OR "Ikegami" OR "Extron" OR "C-mount" OR "lente CCTV")',
]

STATE = Path("data/seen.json")
STATE.parent.mkdir(parents=True, exist_ok=True)

def fetch_rss(query):
    q = urllib.parse.quote(query)
    url = f"https://www.bing.com/search?q={q}&format=rss"
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        data = r.read()
    root = ET.fromstring(data)
    out = []
    for item in root.findall(".//item"):
        title = html.unescape(item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = html.unescape(item.findtext("description") or "").strip()
        out.append({"title": title, "link": link, "desc": re.sub("<.*?>","",desc)})
    return out

def is_target(link):
    return "es.wallapop.com" in link or "wallapop.com" in link or "vinted.es" in link

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": msg,
        "disable_web_page_preview": "false",
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API error {e.code}: {body}") from e

def telegram_diagnostics():
    def api_get(method):
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
        req = urllib.request.Request(url, headers={"User-Agent": "CRTStalker/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))

    me = api_get("getMe")
    username = me.get("result", {}).get("username", "(sin username)")
    updates = api_get("getUpdates")
    chats = []
    for update in updates.get("result", []):
        msg = update.get("message") or update.get("edited_message") or update.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if "id" in chat:
            chats.append({
                "id": chat.get("id"),
                "type": chat.get("type"),
                "first_name": chat.get("first_name"),
                "username": chat.get("username"),
            })
    print(f"Telegram bot: @{username}")
    print("Chats detectados:", json.dumps(chats, ensure_ascii=False))

if EVENT_NAME == "push":
    telegram_diagnostics()
elif EVENT_NAME == "workflow_dispatch":
    send("✅ CRTStalker conectado y funcionando. A partir de ahora buscaré anuncios nuevos automáticamente.")

seen = set()
if STATE.exists():
    try:
        seen = set(json.loads(STATE.read_text(encoding="utf-8")))
    except Exception:
        seen = set()

found = []
for query in SEARCHES:
    try:
        for item in fetch_rss(query):
            if item["link"] and is_target(item["link"]):
                found.append(item)
    except Exception as e:
        print(f"Search failed: {query}: {e}")

dedup = {}
for x in found:
    dedup[x["link"]] = x
found = list(dedup.values())

first_run = not STATE.exists() or not seen
new_items = [x for x in found if x["link"] not in seen]

if first_run:
    print(f"Primera ejecución: guardando {len(found)} resultados existentes.")
else:
    for x in new_items:
        platform = "Wallapop" if "wallapop.com" in x["link"] else "Vinted"
        msg = f"🔴 {x['title']}\n{platform}\n{x['link']}"
        send(msg)
        print("Sent:", x["link"])

seen.update(x["link"] for x in found)
STATE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")
# telegram retest trigger
