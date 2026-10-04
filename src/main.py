import os, re, json, html, urllib.parse, urllib.request, urllib.error
from pathlib import Path
from xml.etree import ElementTree as ET

CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
EVENT_NAME = os.environ.get("GITHUB_EVENT_NAME", "")

SEARCHES = [
    'site:wallapop.com "Sony PVM"',
    'site:wallapop.com "Sony BVM"',
    'site:wallapop.com "TV de tubo"',
    'site:wallapop.com "monitor profesional video"',
    'site:wallapop.com "video wall CRT"',
    'site:wallapop.com "Time Base Corrector"',
    'site:wallapop.com TBC video',
    'site:wallapop.com "Edirol V4"',
    'site:wallapop.com "Edirol V8"',
    'site:wallapop.com "camara VHS"',
    'site:wallapop.com "camara analogica"',
    'site:wallapop.com "Super 8"',
    'site:vinted.es "Sony PVM"',
    'site:vinted.es "TV de tubo"',
    'site:vinted.es CRT monitor',
    'site:vinted.es "camara VHS"',
    'site:vinted.es "camara analogica"',
    'site:vinted.es "Super 8"',
]

STATE = Path("data/seen.json")
STATE.parent.mkdir(parents=True, exist_ok=True)

def fetch_rss(query):
    q = urllib.parse.quote(query)
    url = f"https://www.google.com/search?q={q}&output=rss"
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
    return "wallapop.com" in link or "vinted.es" in link

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

if EVENT_NAME == "workflow_dispatch":
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
