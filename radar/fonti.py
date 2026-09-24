"""Sorgenti: ognuna restituisce dizionari con le stesse chiavi. Nessuna AI qui."""
import datetime as dt
import email.utils
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape

UA = {"User-Agent": "Mozilla/5.0 (radar-personale; lettore RSS privato)"}
NS = {"arxiv": "http://arxiv.org/schemas/atom", "dc": "http://purl.org/dc/elements/1.1/"}
ATOM = "{http://www.w3.org/2005/Atom}"


def _gnews(q, lingua, giorni=2):
    paese = {"it": ("it", "IT", "IT:it"), "en": ("en-US", "US", "US:en")}[lingua]
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": f"{q} when:{giorni}d", "hl": paese[0], "gl": paese[1], "ceid": paese[2]})


# nome, indirizzo, lingua, peso (bonus di partenza: le fonti più mirate valgono di più)
NOTIZIE = [
    ("The Verge", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "en", 1),
    ("TechCrunch", "https://techcrunch.com/category/artificial-intelligence/feed/", "en", 1),
    ("The Register", "https://www.theregister.com/headlines.atom", "en", 0),
    ("The Record", "https://therecord.media/feed", "en", 2),
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/", "en", 0),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab", "en", 0),
    ("Rest of World", "https://restofworld.org/feed/latest", "en", 1),
    ("Hacker News", "https://hnrss.org/frontpage?points=100", "en", 0),
    ("Il Post", "https://www.ilpost.it/tecnologia/feed/", "it", 1),
    ("Agenda Digitale", "https://www.agendadigitale.eu/feed/", "it", 1),
    ("Key4biz", "https://www.key4biz.it/feed/", "it", 0),
    # Google News: ricerche mirate sul lato istituzionale, in Italia e nel mondo
    ("Google News", _gnews('"intelligenza artificiale" (legge OR regolamento OR divieto OR governo)', "it"), "it", 1),
    ("Google News", _gnews('"data center" (acqua OR energia OR legge)', "it"), "it", 1),
    ("Google News", _gnews('"attacco informatico" OR ransomware', "it"), "it", 1),
    ("Google News", _gnews('"sovranità digitale" OR "cloud europeo" OR "software libero"', "it"), "it", 1),
    ("Google News", _gnews('AI (law OR ban OR regulation OR bill) government', "en"), "en", 1),
    ("Google News", _gnews('"data center" (water OR electricity) (law OR ban OR moratorium)', "en"), "en", 1),
    ("Google News", _gnews('cyberattack (government OR ministry OR hospital OR country)', "en"), "en", 1),
]


# Il weekend a Roma (solo sabato e domenica). Quasi nessun sito di eventi romano ha un feed che funzioni
# (RomaToday 403, 060608 vuoto, Wanted in Rome 404): si passa dalle guide e dagli annunci indicizzati da Google News.
EVENTI = [
    ("Google News", _gnews('"weekend a Roma" OR "cosa fare a Roma" OR "eventi a Roma" OR "weekend nel Lazio"', "it", 4), "it", 0),
    ("Google News", _gnews('sagra (Roma OR Lazio OR "Castelli Romani" OR Tuscia OR Sabina)', "it", 7), "it", 0),
    ("Google News", _gnews('mostra Roma (inaugura OR apre OR "fino al")', "it", 7), "it", 0),
    ("Google News", _gnews('concerto Roma (sabato OR domenica OR stasera)', "it", 5), "it", 0),
    ("Il Messaggero", "https://www.ilmessaggero.it/rss/roma.xml", "it", 1),
]

# Codici meteo WMO (quelli di Open-Meteo), in parole
TEMPO = {0: "sereno", 1: "quasi sereno", 2: "poco nuvoloso", 3: "nuvoloso", 45: "nebbia", 48: "nebbia",
         51: "pioviggine", 53: "pioviggine", 55: "pioviggine", 56: "pioviggine gelata", 57: "pioviggine gelata",
         61: "pioggia debole", 63: "pioggia", 65: "pioggia forte", 66: "pioggia gelata", 67: "pioggia gelata",
         71: "neve debole", 73: "neve", 75: "neve forte", 77: "nevischio", 80: "rovesci", 81: "rovesci",
         82: "rovesci forti", 85: "rovesci di neve", 86: "rovesci di neve", 95: "temporale",
         96: "temporale con grandine", 99: "temporale con grandine"}


def meteo(lat, lon):
    """Il tempo di oggi da Open-Meteo (gratuito, senza chiave)."""
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "Europe/Rome", "forecast_days": 1,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"})
    g = json.loads(scarica(url))["daily"]
    return {"cielo": TEMPO.get(g["weather_code"][0], "variabile"), "min": round(g["temperature_2m_min"][0]),
            "max": round(g["temperature_2m_max"][0]), "pioggia": g["precipitation_probability_max"][0]}


def scarica(url, intestazioni=None):
    req = urllib.request.Request(url, headers=UA | (intestazioni or {}))
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def testo_semplice(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html or "")).split())


def _data(s):
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s) if s[0].isalpha() else dt.datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def feed(nome, url, lingua, peso):
    """Un feed RSS o Atom di notizie."""
    radice = ET.fromstring(scarica(url).strip())
    voci = list(radice.iter("item")) or list(radice.iter(ATOM + "entry"))
    for v in voci:
        titolo = testo_semplice(v.findtext("title") or v.findtext(ATOM + "title"))
        link = v.findtext("link") or ""
        if not link:
            nodo = v.find(ATOM + "link")
            link = nodo.get("href", "") if nodo is not None else ""
        corpo = testo_semplice(v.findtext("description") or v.findtext(ATOM + "summary"))
        fonte = nome
        if nome == "Google News":
            # il titolo è "Titolo - Testata" e la descrizione ripete solo il titolo
            fonte = v.findtext("source") or titolo.rsplit(" - ", 1)[-1]
            titolo, corpo = titolo.rsplit(" - ", 1)[0], ""
        elif nome == "Hacker News":
            corpo = ""                     # solo link e punteggio, niente testo
        if not titolo or not link:
            continue
        uscito = _data(v.findtext("pubDate") or v.findtext(ATOM + "published") or v.findtext(ATOM + "updated"))
        yield {
            "id": "notizia:" + hashlib.sha1(link.encode()).hexdigest()[:16],
            "fonte": fonte, "sezione": "notizie", "titolo": titolo, "url": link,
            "testo": corpo[:1500], "autori": "", "lingua": lingua, "peso": peso,
            "uscito": uscito.isoformat() if uscito else None, "extra": None,
        }


def github(temi, giorni):
    """Repository nuovi (creati negli ultimi `giorni`) ordinati per stelle: i più visti in generale e per tema."""
    da = (dt.date.today() - dt.timedelta(days=giorni)).isoformat()
    ricerche = [f"created:>{da} stars:>50"] + [f"topic:{t} created:>{da} stars:>10" for t in temi]
    token = os.environ.get("GITHUB_TOKEN")
    intestazioni = {"Accept": "application/vnd.github+json"} | ({"Authorization": f"Bearer {token}"} if token else {})
    for i, q in enumerate(ricerche):
        if i:
            time.sleep(1 if token else 7)  # senza token GitHub concede 10 ricerche al minuto
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
            {"q": q, "sort": "stars", "order": "desc", "per_page": 20})
        try:
            risposta = scarica(url, intestazioni)
        except urllib.error.HTTPError as err:
            if err.code not in (403, 429):
                raise
            time.sleep(61)                 # limite di ricerche al minuto: si aspetta e si riprova una volta
            risposta = scarica(url, intestazioni)
        for r in json.loads(risposta)["items"]:
            yield {
                "id": "github:" + r["full_name"].lower(),
                "fonte": "GitHub", "sezione": "github", "titolo": r["full_name"], "url": r["html_url"],
                "testo": r["description"] or "", "autori": r["owner"]["login"], "lingua": "en", "peso": 0,
                "uscito": r["created_at"],
                "extra": json.dumps({"stelle": r["stargazers_count"], "linguaggio": r["language"],
                                     "temi": r["topics"][:6]}),
            }


def senza_latex(s):
    """Schr\\"odinger -> Schrodinger, $k$-NN -> k-NN: i titoli arXiv arrivano col LaTeX dentro."""
    return re.sub(r"\\[\"'`^~]\{?(\w)\}?", r"\1", s).replace("$", "")


def arxiv(categorie=("cs.AI", "cs.LG", "cs.CR")):
    """Annunci del giorno dal feed RSS di arXiv (solo lavori nuovi, niente revisioni)."""
    radice = ET.fromstring(scarica("https://rss.arxiv.org/rss/" + "+".join(categorie)))
    for item in radice.iter("item"):
        if item.findtext("arxiv:announce_type", namespaces=NS) not in ("new", "cross"):
            continue
        cat = [c.text for c in item.findall("category")]
        ident = re.sub(r"v\d+$", "", item.findtext("guid").removeprefix("oai:arXiv.org:"))
        yield {
            "id": "arxiv:" + ident,
            "fonte": "arXiv " + ident,
            "sezione": "ricerca",
            "rubrica": "sicurezza" if "cs.CR" in cat else "ai",
            "titolo": senza_latex(" ".join(item.findtext("title").split())),
            "url": item.findtext("link"),
            "testo": " ".join(item.findtext("description").split("Abstract:", 1)[-1].split()),
            "autori": item.findtext("dc:creator", namespaces=NS) or "",
            "lingua": "en", "peso": 0, "uscito": None, "extra": None,
        }
