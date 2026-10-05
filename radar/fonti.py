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

# Attualità, solo titoli: nome, indirizzo, lingua, peso, zona ("auto" = dalla categoria del feed)
ATTUALITA = [
    ("ANSA", "https://www.ansa.it/sito/notizie/politica/politica_rss.xml", "it", 1, "italia"),
    ("ANSA", "https://www.ansa.it/sito/notizie/economia/economia_rss.xml", "it", 1, "italia"),
    ("ANSA", "https://www.ansa.it/sito/notizie/cronaca/cronaca_rss.xml", "it", 0, "italia"),
    ("ANSA", "https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml", "it", 1, "estero"),
    ("Il Fatto Quotidiano", "https://www.ilfattoquotidiano.it/feed/", "it", 1, "auto"),
    ("ISTAT", "https://www.istat.it/feed/", "it", 4, "italia"),
]

# Bandi e concorsi per un ingegnere informatico: Concorsando (concorsi di tutta Italia) e ricerche mirate su Google News.
# Un bando resta aperto settimane, quindi la finestra è larga.
BANDI = [
    ("Concorsando", "https://www.concorsando.it/blog/feed/", "it", 0),
    ("Google News", _gnews('concorso ("ingegnere informatico" OR "funzionario informatico" OR "funzionario tecnico informatico" OR "esperto ICT")', "it", 14), "it", 0),
    ("Google News", _gnews('bando OR avviso ("ingegnere informatico" OR "ingegneria informatica" OR "servizi informatici") (incarico OR selezione OR professionisti)', "it", 14), "it", 0),
    ("Google News", _gnews('avviso OR concorso informatico OR ICT OR cybersicurezza (Roma OR Lazio) (selezione OR assunzione OR incarico)', "it", 14), "it", 0),
    ("Google News", _gnews('"albo degli ingegneri" informatica (avviso OR incarico OR elenco OR professionisti)', "it", 14), "it", 0),
]

# Gaming: italiane e inglesi; le inglesi le traduce il modello. Eurogamer.it ha un feed con XML rotto.
GAMING = [
    ("Everyeye", "https://www.everyeye.it/feed/", "it", 0),
    ("IGN Italia", "https://it.ign.com/feed.xml", "it", 1),
    ("GameSpot", "https://www.gamespot.com/feeds/news/", "en", 1),
    ("PC Gamer", "https://www.pcgamer.com/rss/", "en", 0),
    ("Rock Paper Shotgun", "https://www.rockpapershotgun.com/feed", "en", 1),
    ("Polygon", "https://www.polygon.com/rss/index.xml", "en", 0),
    ("The Verge", "https://www.theverge.com/rss/games/index.xml", "en", 0),
    ("GamesIndustry.biz", "https://www.gamesindustry.biz/feed", "en", 1),
    ("Push Square", "https://www.pushsquare.com/feeds/latest", "en", 0),
    ("Nintendo Life", "https://www.nintendolife.com/feeds/latest", "en", 0),
    ("Google News", _gnews("videogiochi (uscita OR annunciato OR recensione OR annuncia)", "it", 2), "it", 0),
]

# Sport: corsa, atletica, tennis, pallavolo, bici. Professionisti e gare amatoriali a Roma.
SPORT = [
    ("OA Sport", "https://www.oasport.it/feed/", "it", 1),
    ("FIDAL", "https://www.fidal.it/rss.php", "it", 2),
    ("Runner's World", "https://www.runnersworld.com/it/rss/all.xml/", "it", 1),
    ("ANSA", "https://www.ansa.it/sito/notizie/sport/sport_rss.xml", "it", 1),
    ("Google News", _gnews('(podistica OR "corsa su strada" OR "mezza maratona" OR "10 km" OR granfondo) Roma', "it", 5), "it", 0),
]

# Codici meteo WMO (quelli di Open-Meteo), in parole
TEMPO = {0: "sereno", 1: "quasi sereno", 2: "poco nuvoloso", 3: "nuvoloso", 45: "nebbia", 48: "nebbia",
         51: "pioviggine", 53: "pioviggine", 55: "pioviggine", 56: "pioviggine gelata", 57: "pioviggine gelata",
         61: "pioggia debole", 63: "pioggia", 65: "pioggia forte", 66: "pioggia gelata", 67: "pioggia gelata",
         71: "neve debole", 73: "neve", 75: "neve forte", 77: "nevischio", 80: "rovesci", 81: "rovesci",
         82: "rovesci forti", 85: "rovesci di neve", 86: "rovesci di neve", 95: "temporale",
         96: "temporale con grandine", 99: "temporale con grandine"}


# Icone dell'Aeronautica Militare (legenda: meteoam.it/it/legenda-simboli). 31-35 sono le varianti notturne.
ICONE_AM = {"01": "sereno", "02": "parzialmente velato", "03": "velato", "04": "poco nuvoloso",
            "05": "molto nuvoloso", "06": "coperto", "07": "pioggia debole", "08": "pioggia forte",
            "09": "temporale", "10": "pioggia mista a neve", "11": "pioggia che gela", "12": "foschia",
            "13": "nebbia", "14": "grandine", "15": "neve", "16": "trombe d'aria", "17": "fumo",
            "18": "tempesta di sabbia", "31": "sereno", "32": "parzialmente velato", "33": "velato",
            "34": "poco nuvoloso", "35": "molto nuvoloso"}


def meteo(lat, lon):
    """Il tempo di oggi: Aeronautica Militare, e Open-Meteo se quella non risponde."""
    try:
        return meteo_am(lat, lon)
    except Exception:
        return meteo_open(lat, lon)


def meteo_am(lat, lon):
    """Dal meteogramma di meteoam.it (lo stesso indirizzo che usa il loro sito: non è un'API pubblica
    documentata, può cambiare). Uso personale, una chiamata al giorno, niente ridistribuzione."""
    d = json.loads(scarica(f"https://api.meteoam.it/deda-meteograms/api/GetMeteogram/preset1/{lat},{lon}"))
    oggi = d["extrainfo"]["stats"][0]
    serie = dict(zip(d["paramlist"], d["datasets"]["0"].values()))
    inizio = dt.datetime.fromisoformat(oggi["localDate"])            # mezzanotte ora italiana, con lo scarto (+02:00)
    ore = [i for i, t in enumerate(d["timeseries"])
           if inizio <= dt.datetime.fromisoformat(t.replace("Z", "+00:00")) < inizio + dt.timedelta(days=1)]
    pioggia = sum(float(serie["tpp"][str(i)] or 0) for i in ore)       # mm previsti nella giornata
    return {"cielo": ICONE_AM.get(oggi["icon"], "variabile"), "min": oggi["minCelsius"], "max": oggi["maxCelsius"],
            "pioggia_mm": round(pioggia, 1), "fonte": "Aeronautica Militare"}


def meteo_open(lat, lon):
    """Riserva: Open-Meteo (gratuito, senza chiave), col modello italiano ICON-2I."""
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "Europe/Rome", "forecast_days": 1,
        "models": "italia_meteo_arpae_icon_2i",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"})
    g = json.loads(scarica(url))["daily"]
    return {"cielo": TEMPO.get(g["weather_code"][0], "variabile"), "min": round(g["temperature_2m_min"][0]),
            "max": round(g["temperature_2m_max"][0]), "pioggia_mm": round(g["precipitation_sum"][0] or 0, 1),
            "fonte": "Open-Meteo"}


def scarica(url, intestazioni=None):
    req = urllib.request.Request(url, headers=UA | (intestazioni or {}))
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def testo_semplice(html):
    testo = " ".join(unescape(re.sub(r"<[^>]+>", " ", html or "")).split())
    # le chiusure automatiche di WordPress: "The post X appeared first on Y." / "L'articolo X proviene da Y."
    return re.sub(r"\s*(?:\[…\]|\[\.\.\.\])?\s*(?:The post .* appeared first on .*|L[’']articolo .* proviene da .*)$",
                  "", testo).strip()


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
            fonte = (v.findtext("source") or titolo.rsplit(" - ", 1)[-1]).strip(" |")
            titolo, corpo = titolo.rsplit(" - ", 1)[0], ""
            if "|" in titolo and titolo.rsplit("|", 1)[1].strip().lower() in fonte.lower():
                titolo = titolo.rsplit("|", 1)[0]          # "Torna a Viterbo... | Viterbo Post": la testata c'è già
        elif nome == "Hacker News":
            corpo = ""                     # solo link e punteggio, niente testo
        titolo = titolo.strip(" |-–—:")                # c'è chi lo manda come "| Torna a Viterbo..."
        if not titolo or not link:
            continue
        uscito = _data(v.findtext("pubDate") or v.findtext(ATOM + "published") or v.findtext(ATOM + "updated"))
        yield {
            "id": "notizia:" + hashlib.sha1(link.encode()).hexdigest()[:16],
            "fonte": fonte, "sezione": "notizie", "titolo": titolo, "url": link,
            "testo": corpo[:1500], "autori": "", "lingua": lingua, "peso": peso,
            "uscito": uscito.isoformat() if uscito else None, "extra": None,
            "categorie": [c.text or "" for c in v.findall("category")],
        }


def _github(url, grezzo=False):
    token = os.environ.get("GITHUB_TOKEN")
    intestazioni = {"Accept": "application/vnd.github.raw" if grezzo else "application/vnd.github+json"}
    if token:
        intestazioni["Authorization"] = f"Bearer {token}"
    try:
        return scarica(url, intestazioni)
    except urllib.error.HTTPError as err:
        if err.code not in (403, 429):
            raise
        time.sleep(61)                     # limite di richieste al minuto: si aspetta e si riprova una volta
        return scarica(url, intestazioni)


def github_forti(temi, stelle_min, attivi_giorni):
    """I repository più seguiti di ogni tema (anche vecchi), purché aggiornati di recente.
    `temi`: {nome: filtro di ricerca GitHub}. Chi vada forte adesso lo decide chi chiama, dalla crescita
    delle stelle giorno per giorno."""
    da = (dt.date.today() - dt.timedelta(days=attivi_giorni)).isoformat()
    for i, (tema, filtro) in enumerate(temi.items()):
        if i:
            time.sleep(1 if os.environ.get("GITHUB_TOKEN") else 7)   # senza token: 10 ricerche al minuto
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
            {"q": f"{filtro} stars:>{stelle_min} pushed:>{da}", "sort": "stars", "order": "desc", "per_page": 40})
        for r in json.loads(_github(url))["items"]:
            yield {"nome": r["full_name"], "url": r["html_url"], "descrizione": r["description"] or "",
                   "stelle": r["stargazers_count"], "linguaggio": r["language"], "temi": r["topics"][:6],
                   "creato": r["created_at"][:10], "tema": tema}


def readme(nome, caratteri=1800):
    """L'inizio del README, ripulito da immagini, badge, codice e HTML: materiale per la spiegazione."""
    md = _github(f"https://api.github.com/repos/{nome}/readme", grezzo=True).decode("utf-8", "replace")
    md = re.sub(r"```.*?```", " ", md, flags=re.S)                     # blocchi di codice
    md = re.sub(r"<[^>]+>", " ", md)                                    # HTML (spesso i badge)
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)                       # immagini
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)                    # link: resta il testo
    righe = [r.strip(" #>*-|\t") for r in md.splitlines()]
    righe = [r for r in righe if len(r) > 25 and not r.startswith(("[!", "http"))]
    return " ".join(" ".join(righe).split())[:caratteri]


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
