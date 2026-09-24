"""Sorgenti: ognuna restituisce dizionari con le stesse chiavi. Nessuna AI qui."""
import re
import urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "radar-personale/0.1 (uso privato)"}
NS = {"arxiv": "http://arxiv.org/schemas/atom", "dc": "http://purl.org/dc/elements/1.1/"}


def scarica(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


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
            "sezione": "sicurezza" if "cs.CR" in cat else "ai",
            "titolo": senza_latex(" ".join(item.findtext("title").split())),
            "url": item.findtext("link"),
            "testo": " ".join(item.findtext("description").split("Abstract:", 1)[-1].split()),
            "autori": item.findtext("dc:creator", namespaces=NS) or "",
        }
