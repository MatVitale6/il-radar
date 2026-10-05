"""Impagina un'edizione come prima pagina di un quotidiano, in bianco e nero e stampabile.

Sullo schermo: a sinistra (3/4) l'apertura e un unico flusso a due colonne (notizie, repository GitHub, sport o il
weekend a Roma); a destra (1/4) la barra dei titoli.

In stampa (e nell'anteprima ?carta) i fogli A4 li costruisce lo script della pagina, a misura fissa: misura ogni
articolo e lo dispone nelle colonne del foglio 1 e del foglio 2. Il browser non deve spezzare niente, e questo conta:
Firefox, Edge e Chrome spezzano griglie e colonne in modi diversi (Firefox sposta intera sul foglio dopo una griglia
che non ci sta, lasciando sul primo solo la testata).
"""
import datetime as dt
import json
import re
from html import escape

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]
RUBRICHE = {"norme": "Governi e regole", "sicurezza": "Cybersicurezza", "tecnologia": "AI e sviluppo"}


def romano(n):
    out = ""
    for v, s in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                 (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out, n = out + s, n - v
    return out


def voto(r):
    return max(0, min(10, r["punti"]))


ABBREVIAZIONI = {"u.s.", "u.k.", "sens.", "sen.", "rep.", "reps.", "gov.", "mr.", "mrs.", "ms.", "dr.", "inc.",
                 "corp.", "co.", "ltd.", "vs.", "st.", "no.", "jr.", "sr.", "prof.", "dott.", "sig.", "ing.", "avv.",
                 "ecc.", "e.g.", "i.e.", "a.m.", "p.m."}


def breve(s, n=2):
    """Le prime `n` frasi. Non si ferma dopo un'abbreviazione ("U.S. Sens. Mark Warner...") né dopo un'iniziale
    ("J. Smith"), e toglie il "[...]" con cui i feed troncano il testo."""
    s = re.sub(r"\s*\[(?:…|\.\.\.)\]\s*$", "", (s or "").strip())
    frasi = []
    for pezzo in re.split(r"(?<=[.!?])\s+", s):
        ultima = frasi[-1].split()[-1] if frasi else ""
        if frasi and (ultima.lower() in ABBREVIAZIONI or re.fullmatch(r"[A-ZÀ-Ú]\.", ultima)):
            frasi[-1] += " " + pezzo
        else:
            frasi.append(pezzo)
    return " ".join(frasi[:n])


def autori(s):
    nomi = [n for n in s.split(", ") if n]
    return ", ".join(nomi[:3]) + (" e altri" if len(nomi) > 3 else "")


def pulsanti(r):
    g = r["giudizio"]
    return (f'<div class="giudizio" data-id="{escape(r["id"])}">'
            f'<button data-g="1" aria-pressed="{str(g == 1).lower()}">▲ utile</button>'
            f'<button data-g="-1" aria-pressed="{str(g == -1).lower()}">▼ non mi interessa</button></div>')


SPORT = {"atletica": "Atletica e corsa", "tennis": "Tennis", "pallavolo": "Pallavolo", "ciclismo": "Ciclismo",
         "roma": "Gare a Roma"}


def _titolo(r):
    return r["titolo_it"] or r["titolo"]


def voce(r, riserva_di=None):
    """Una riga della barra laterale: titolo e testata. Con `riserva_di` è la versione ridotta di un articolo:
    nascosta, la usa lo script (al posto dell'articolo) se in stampa non si sta in due fogli."""
    classe = f' class="riserva" data-di="{escape(riserva_di)}"' if riserva_di else ""
    return (f'<li{classe}><a href="{escape(r["url"])}">{escape(_titolo(r))}</a>'
            f'<span>{escape(r["fonte"])}</span></li>')


def articolo(r, classe="", gruppo=None):
    if r["sezione"] == "sport":
        occhiello = f"{SPORT.get(r['rubrica'], 'Sport')} · {escape(r['fonte'])}"
    elif r["sezione"] == "gaming":
        occhiello = f"Gaming · {escape(r['fonte'])}"
    else:
        occhiello = f"{RUBRICHE.get(r['rubrica'], 'Notizie')} · {escape(r['fonte'])}"
    if r["copertura"] > 1:
        occhiello += f" · su {r['copertura']} testate"
    originale = f'<p class="originale">{escape(r["titolo"])}</p>' if _titolo(r) != r["titolo"] else ""
    corpo = f'<p class="corpo">{escape(r["riassunto"])}</p>' if r["riassunto"] else ""
    dati = f' data-gruppo="{gruppo}"' if gruppo else ""
    return f"""
<article class="{classe}" id="{escape(r['id'])}" data-punti="{r['punti']}"{dati}>
  <p class="occhiello">{occhiello}</p>
  <h3><a href="{escape(r['url'])}">{escape(_titolo(r))}</a></h3>
  {originale}{corpo}
  <p class="perche"><span>Perché è qui.</span> {escape(r['parole'])}</p>
  <p class="firma"><a href="{escape(r['url'])}">Leggi su {escape(r['fonte'])}</a></p>
  {pulsanti(r)}
</article>"""


def scheda_repo(r):
    x = json.loads(r["extra"])
    padrone, nome = r["titolo"].split("/", 1)
    punto = lambda n: f"{n:,}".replace(",", ".")
    crescita = (f"+{punto(x['settimana'])} in 7 giorni" if x.get("misurata")
                else f"~{punto(x['settimana'])} a settimana")          # stima dalla media, finché manca lo storico
    linguaggio = f" · {escape(x['linguaggio'])}" if x["linguaggio"] else ""
    corpo = f'<p class="corpo">{escape(r["riassunto"])}</p>' if r["riassunto"] else ""
    temi = " · ".join(x["temi"][:4])
    # data-fisso: i repository non si declassano a titolo, sono una sezione a parte
    return f"""
<article class="repo" id="{escape(r['id'])}" data-punti="{r['punti']}" data-gruppo="codice" data-fisso="1">
  <p class="occhiello">{escape(r['rubrica'] or '')} · ★ {punto(x['stelle'])} · {crescita}{linguaggio}</p>
  <h3><a href="{escape(r['url'])}">{escape(padrone)}/<b>{escape(nome)}</b></a></h3>
  {corpo}
  {f'<p class="firma">{escape(temi)}</p>' if temi else ''}
  {pulsanti(r)}
</article>"""


def _testatina(nome):
    return f'<h2 class="testatina"><span>{nome}</span></h2>'


def intesta(gruppo, nome, tag="h2", classe="rubrica"):
    """Un titoletto nel flusso: viaggia con la voce che segue, e sparisce se il suo gruppo si svuota."""
    return f'<{tag} class="{classe}" data-gruppo="{gruppo}">{nome}</{tag}>'


WEEKEND = {"guide": "Guide", "musica": "Musica", "sagre": "Sagre e feste", "mostre": "Mostre"}


def sezione_weekend(eventi):
    out = intesta("weekend", "Il weekend a Roma e dintorni")
    for chiave, nome in WEEKEND.items():
        righe = [r for r in eventi if r["rubrica"] == chiave]
        if righe:
            g = f"weekend:{chiave}"
            out += intesta(g, nome, "h3", "sottorubrica") + "".join(
                f'<div class="voce" id="{escape(r["id"])}" data-gruppo="{g}"><a href="{escape(r["url"])}">'
                f'{escape(r["titolo"])}</a><span>{escape(r["fonte"])}</span>{pulsanti(r)}</div>' for r in righe)
    return out


def orecchio_meteo(con, data):
    riga = con.execute("SELECT dati FROM meteo WHERE data=?", (data,)).fetchone()
    if not riga:
        return '<div class="orecchio destra">Tutte le notizie<br>che ti riguardano</div>'
    m = json.loads(riga[0])
    mm = m.get("pioggia_mm")
    pioggia = ("niente pioggia" if mm is not None and mm < 0.5 else f"pioggia {mm:g} mm" if mm is not None
               else f"pioggia {m['pioggia']}%")                          # edizioni vecchie: probabilità
    return (f'<div class="orecchio destra meteo"><b>Il tempo a {escape(m["citta"])}</b><br>{m["cielo"]}<br>'
            f'{m["min"]}° – {m["max"]}° · {pioggia}</div>')


def pagina(con, data, profilo):
    q = lambda sql, *a: con.execute(sql, (data, *a)).fetchall()
    scelti = lambda sezione, ruolo, altro="": q(f"SELECT * FROM elementi WHERE visto_il=? AND sezione=? AND ruolo=? {altro}"
                                                " ORDER BY punti DESC, copertura DESC", sezione, ruolo)
    notizie, brevi = scelti("notizie", "articolo"), scelti("notizie", "breve")
    repo = scelti("github", "articolo")
    sport, sport_brevi = scelti("sport", "articolo"), scelti("sport", "breve")
    gaming, gaming_brevi = scelti("gaming", "articolo"), scelti("gaming", "breve")
    italia, estero = scelti("attualita", "breve", "AND rubrica='italia'"), scelti("attualita", "breve", "AND rubrica='estero'")
    ricerca, bandi = scelti("ricerca", "breve"), scelti("bandi", "breve")
    d = dt.date.fromisoformat(data)
    eventi = []
    if d.weekday() >= 5:            # sabato e domenica: il weekend a Roma (la domenica anche ciò che è uscito sabato)
        sabato = (d - dt.timedelta(days=d.weekday() - 5)).isoformat()
        eventi = con.execute("SELECT * FROM elementi WHERE sezione='weekend' AND ruolo='articolo' AND visto_il"
                             " BETWEEN ? AND ? ORDER BY punti DESC", (sabato, data)).fetchall()
    fuori = q("SELECT * FROM elementi WHERE visto_il=? AND ruolo IS NULL AND punti>0 AND sezione IN ('notizie', 'ricerca')"
              " ORDER BY sezione='ricerca', punti DESC LIMIT ?", profilo["giornale"]["fondo"])
    numero = con.execute("SELECT COUNT(DISTINCT visto_il) FROM elementi WHERE visto_il<=? AND ruolo IS NOT NULL",
                         (data,)).fetchone()[0] or 1
    primo = con.execute("SELECT MIN(visto_il) FROM elementi").fetchone()[0] or data
    anno = romano(int(data[:4]) - int(primo[:4]) + 1)
    giorno = f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]} {d.year}"

    apertura, resto = (notizie[0], notizie[1:]) if notizie else (None, [])

    # Barra dei titoli. Le "riserve" sono gli articoli in versione ridotta: nascoste, le usa lo script quando
    # per stare in due fogli deve trasformare un articolo in titolo. L'ordine è anche quello con cui, se la barra
    # non ci sta, si toglie dal fondo: prima la ricerca, poi l'estero, l'Italia, lo sport.
    lista = lambda righe, riserve=(): "".join(voce(r, r["id"]) for r in riserve) + "".join(voce(r) for r in righe)
    laterale = [("brevi", "In breve", lista(brevi, resto)), ("sport", "Sport", lista(sport_brevi, sport)),
                ("gaming", "Gaming", lista(gaming_brevi, gaming)), ("bandi", "Bandi e concorsi", lista(bandi)),
                ("italia", "Italia", lista(italia)), ("estero", "Estero", lista(estero)),
                ("ricerca", "Dalla ricerca", lista(ricerca))]
    laterale = "".join(f'<h2>{nome}</h2><ol class="{chiave}">{voci}</ol>' for chiave, nome, voci in laterale if voci)

    # Il flusso: tutto in fila, a colonne. Ogni voce sa a che gruppo appartiene (data-gruppo).
    forti = {r["id"] for r in sorted(resto, key=lambda r: -r["punti"])[:max(1, len(resto) // 3)]}
    flusso = ""
    for chiave, nome in RUBRICHE.items():
        pezzi = [r for r in resto if r["rubrica"] == chiave]
        if pezzi:
            g = f"notizie:{chiave}"
            flusso += intesta(g, nome) + "".join(articolo(r, "forte" if r["id"] in forti else "", g) for r in pezzi)
    if repo:
        flusso += intesta("codice", "Dal codice · i più in crescita nei tuoi temi") + "".join(scheda_repo(r) for r in repo)
    if sport:
        flusso += intesta("sport", "Sport") + "".join(articolo(r, "", "sport") for r in sport)
    if gaming:
        flusso += intesta("gaming", "Gaming") + "".join(articolo(r, "", "gaming") for r in gaming)
    if eventi:
        flusso += sezione_weekend(eventi)
    testa = articolo(apertura, "apertura") if apertura else '<p class="vuota">Nessuna notizia per esteso oggi.</p>'
    giornale = (f'<div class="giornale"><aside class="laterale">{laterale}</aside>'
                f'<div class="principale">{testa}<div class="flusso">{flusso}</div></div></div>')

    fondo = "".join(f'<li><span class="voto">{voto(r)}</span> <a href="{escape(r["url"])}">{escape(r["titolo"])}</a>'
                    f' <span class="fonte">{escape(r["fonte"])}</span>{pulsanti(r)}</li>' for r in fuori)
    fondo = (f'<section class="fondo">{_testatina("Rimasti fuori")}'
             f'<p class="nota">Toccano il tuo profilo ma non sono entrati. Se uno ti interessa, segnalalo: '
             f'serve a tarare le parole chiave.</p><ol>{fondo}</ol></section>') if fuori else ""

    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Il Radar — {giorno}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=UnifrakturMaguntia&family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="strumenti"><a href="?carta">Anteprima di stampa</a><button class="stampa">Stampa</button></div>
<main class="foglio">
<header class="testata">
  <div class="orecchio">Notizie {len(notizie) + len(brevi)}<br>Codice {len(repo)}<br>Sport {len(sport) + len(sport_brevi)}<br>Gaming {len(gaming) + len(gaming_brevi)}</div>
  <h1>Il Radar</h1>
  {orecchio_meteo(con, data)}
  <p class="riga"><span>Anno {anno} · N. {numero}</span><span>{giorno}</span><span>Tutte le notizie che ti riguardano</span></p>
</header>
{giornale}
{fondo}
<footer class="colophon">Notizie: The Verge, TechCrunch, The Register, The Record, BleepingComputer, Ars Technica,
Rest of World, Hacker News, Il Post, Agenda Digitale, Key4biz, Google News · attualità: ANSA, Il Fatto Quotidiano,
ISTAT · bandi: Concorsando, Google News · sport: OA Sport, FIDAL, Runner's World, ANSA · codice: GitHub · ricerca: arXiv · meteo: Aeronautica
Militare<br>Scelti dalle parole chiave del profilo · tradotti e riassunti in locale da MiniCPM4.1 · nessun testo
inviato a servizi esterni</footer>
</main>
<div class="fogli"></div>
<script>{JS}</script>
</body>
</html>"""


CSS = """
:root { color-scheme: light; --inchiostro: #111; --grigio: #5a5a5a; --filetto: #111; --carta: #fff; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--carta); color: var(--inchiostro);
  font: 400 17px/1.5 "Source Serif 4", Georgia, serif; font-optical-sizing: auto; }
a { color: inherit; text-decoration: none; }
a:hover { text-decoration: underline; text-underline-offset: 2px; }
.foglio { max-width: 1180px; margin: 0 auto; padding: 24px 16px 48px; }
h2, h3 { font-family: "Playfair Display", Georgia, serif; }
h3 { overflow-wrap: break-word; }

/* testata (sullo schermo e in cima al foglio 1) */
.testata { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 16px;
  border-bottom: 1px solid var(--filetto); }
.testata h1 { margin: 0; font: 400 clamp(52px, 10vw, 118px)/1 "UnifrakturMaguntia", serif; text-align: center;
  letter-spacing: .01em; padding: 8px 0 4px; }
.orecchio { justify-self: start; border: 1px solid var(--filetto); padding: 6px 10px; font-size: 12px; line-height: 1.35;
  font-variant: small-caps; letter-spacing: .04em; }
.orecchio.destra { justify-self: end; text-align: right; font-style: italic; font-variant: normal; }
.orecchio.meteo { font-style: normal; line-height: 1.4; }
.orecchio.meteo b { font-variant: small-caps; letter-spacing: .05em; font-weight: 600; }
.riga { grid-column: 1 / -1; margin: 0; display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  border-top: 3px double var(--filetto); padding: 6px 0; font-size: 13px; text-transform: uppercase; letter-spacing: .12em; }

/* il giornale: principale (3/4) e barra dei titoli (1/4) per tutta l'altezza, come un quotidiano */
.giornale { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 1fr); gap: 28px; align-items: start;
  padding-top: 18px; }
.principale { grid-column: 1; grid-row: 1; min-width: 0; }
.laterale { grid-column: 2; grid-row: 1; }
.laterale, .barra { border-left: 1px solid var(--filetto); padding-left: 20px; }
.laterale h2, .barra h2, .coda h2 { margin: 4px 0 10px; font-size: 15px; text-transform: uppercase; letter-spacing: .14em; }
.laterale ol + h2, .barra ol + h2 { margin-top: 20px; }
.laterale ol, .barra ol, .coda ol { margin: 0; padding: 0; list-style: none; counter-reset: s; }
.laterale li, .barra li, .coda li { display: grid; grid-template-columns: auto 1fr; gap: 0 10px; padding: 8px 0;
  border-top: 1px solid #0003; font: 400 16px/1.3 "Playfair Display", serif; counter-increment: s; }
.laterale li::before, .barra li::before, .coda li::before { content: counter(s); font-weight: 700; }
.laterale li span, .barra li span, .coda li span { grid-column: 2; font: italic 400 13px/1.3 "Source Serif 4", serif; color: var(--grigio); }
.laterale li.riserva { display: none; }

.apertura { padding-bottom: 18px; border-bottom: 3px double var(--filetto); }
.apertura h3 { font-size: clamp(30px, 4.4vw, 50px); line-height: 1.05; font-weight: 900; margin: 6px 0 8px; }
.apertura .originale { font-size: 16px; }
.apertura .corpo { font-size: 20px; line-height: 1.45; text-align: justify; hyphens: auto; }
.apertura .corpo::first-letter { float: left; font: 900 3.4em/.8 "Playfair Display", serif; padding: 6px 8px 0 0; }

/* il flusso: notizie, repository, sport (o weekend) di seguito, a due colonne */
.flusso { column-count: 2; column-gap: 28px; column-rule: 1px solid #0004; padding-top: 18px; }
.flusso > article { break-inside: avoid; padding-bottom: 16px; margin-bottom: 16px; border-bottom: 1px solid #0003; }
.flusso h3 { font-size: 20px; line-height: 1.15; margin: 4px 0; }
.flusso .forte h3 { font-size: 27px; font-weight: 900; line-height: 1.08; }
.flusso .repo h3 { font: 400 19px/1.2 "Playfair Display", serif; margin: 4px 0 8px; overflow-wrap: anywhere; }
.repo h3 b { font-weight: 900; }
.repo .corpo { font-size: 15px; line-height: 1.4; }
.rubrica { margin: 0 0 12px; padding: 5px 0 4px; border-top: 3px double var(--filetto); border-bottom: 1px solid var(--filetto);
  font: 600 13px/1.2 "Source Serif 4", serif; text-transform: uppercase; letter-spacing: .18em; text-align: center;
  break-after: avoid; }
.sottorubrica { margin: 10px 0 4px; font-size: 20px; break-after: avoid; }
.voce { break-inside: avoid; padding: 8px 0; border-top: 1px solid #0002; font: 400 15px/1.35 "Source Serif 4", serif; }
.voce > span { display: block; font-style: italic; color: var(--grigio); font-size: 13px; }

.occhiello { margin: 0; font-size: 12px; text-transform: uppercase; letter-spacing: .12em; color: var(--grigio); }
.originale { margin: 0 0 8px; font-style: italic; font-size: 14px; color: var(--grigio); line-height: 1.35; }
.corpo { margin: 0 0 8px; }
.perche { margin: 0 0 8px; font-style: italic; }
.perche span { font-style: normal; font-weight: 600; font-variant: small-caps; letter-spacing: .03em; }
.firma { margin: 0; font-size: 13px; font-variant: small-caps; letter-spacing: .03em; color: var(--grigio); }

.testatina { display: flex; align-items: center; gap: 14px; margin: 26px 0 16px; font-size: 14px;
  text-transform: uppercase; letter-spacing: .2em; }
.testatina::before, .testatina::after { content: ""; flex: 1; border-top: 1px solid var(--filetto); }

/* pulsanti e giudizi */
.giudizio { display: flex; gap: 8px; margin-top: 10px; }
.giudizio button { font: 600 12px/1 "Source Serif 4", serif; letter-spacing: .06em; text-transform: uppercase;
  background: none; color: var(--inchiostro); border: 1px solid var(--filetto); padding: 7px 10px; cursor: pointer; }
.giudizio button[aria-pressed="true"] { background: var(--inchiostro); color: var(--carta); }
.statico .giudizio { display: none; }

.fondo .nota { margin: 0 0 10px; font-style: italic; color: var(--grigio); font-size: 15px; }
.fondo ol { margin: 0; padding: 0; list-style: none; columns: 2; column-gap: 28px; column-rule: 1px solid #0004; }
.fondo li { break-inside: avoid; padding: 8px 0; border-top: 1px solid #0002; font-size: 15px; line-height: 1.35; }
.fondo .voto { display: inline-block; min-width: 1.6em; font-weight: 600; }
.fondo .fonte { font-style: italic; color: var(--grigio); font-size: 13px; }
.fondo .giudizio { margin-top: 6px; }
.fondo .giudizio button { padding: 4px 8px; font-size: 11px; }
.vuota { padding: 60px 0; text-align: center; font-style: italic; border-bottom: 3px double var(--filetto); }
.colophon { margin-top: 32px; padding-top: 8px; border-top: 1px solid var(--filetto); font-size: 12px; text-align: center;
  letter-spacing: .08em; text-transform: uppercase; color: var(--grigio); }
.strumenti { position: fixed; top: 12px; right: 12px; z-index: 1; display: flex; gap: 8px; }
.strumenti button, .strumenti a { font: 600 13px "Source Serif 4", serif; letter-spacing: .08em; text-transform: uppercase;
  background: var(--carta); color: var(--inchiostro); border: 1px solid var(--filetto); padding: 8px 12px; cursor: pointer; }

/* schermi stretti (le regole riguardano solo .foglio: i fogli A4 hanno misure fisse) */
@media screen and (max-width: 900px) {
  .giornale { grid-template-columns: minmax(0, 1fr); }
  .laterale { grid-column: 1; grid-row: 2; border-left: 0; border-top: 3px double var(--filetto); padding: 12px 0 0; }
}
@media screen and (max-width: 620px) {
  .foglio .flusso, .foglio .fondo ol { column-count: 1; }
  .foglio .testata { grid-template-columns: minmax(0, 1fr); }
  .foglio .orecchio { display: none; }
  .foglio .apertura .corpo { text-align: left; }
  .foglio .riga { justify-content: center; }
  .strumenti { position: static; justify-content: flex-end; padding: 8px 16px 0; }
}

/* ── i fogli A4 (costruiti dallo script) ──
   Vengono costruiti appena si apre la pagina, fuori schermo e invisibili, poi restano nascosti: si mostrano
   nell'anteprima (?carta) e in stampa. Così anche il Ctrl+P del browser trova i fogli già pronti. */
.fogli { display: none; }
html.fogli-in-costruzione .fogli { display: block; position: absolute; left: -99999px; top: 0; visibility: hidden; }
html.fogli-pronti.carta .fogli { display: block; }
html.fogli-pronti.carta .foglio { display: none; }
@media screen { html.fogli-pronti.carta body { background: #e8e8e8; } }

/* Margine del foglio a zero: il browser non ha dove stampare titolo, data e indirizzo. I 10 mm li dà .pagina. */
@page { size: A4; margin: 0; }
@media print {
  html.fogli-pronti .foglio { display: none; }
  html.fogli-pronti .fogli { display: block; }
  .strumenti, .giudizio, .fondo { display: none !important; }
  .foglio { max-width: none; padding: 10mm; }          /* ripiego se lo script non ha costruito i fogli */
}

.pagina { width: 210mm; height: 296mm; padding: 10mm; background: #fff; overflow: hidden; display: flex; flex-direction: column;
  font: 400 8.8pt/1.35 "Source Serif 4", Georgia, serif; color: var(--inchiostro);
  break-after: page; page-break-after: always; }
.pagina:last-child { break-after: auto; page-break-after: auto; }
@media screen { html.carta .pagina { margin: 6mm auto; box-shadow: 0 0 8px #0005; } }
.pagina .testata { flex: none; }
.pagina .corpo { flex: 1; min-height: 0; display: flex; gap: 12px; padding-top: 8px; }
.pagina .zona { flex: 3; min-width: 0; display: flex; flex-direction: column; }
.pagina .fisse { flex: 1; min-height: 0; display: flex; }
.pagina .col { flex: 1; min-width: 0; overflow: hidden; padding: 0 7px; }
.pagina .col:first-child { padding-left: 0; }
.pagina .col + .col { border-left: 1px solid #0004; padding-right: 0; }
.pagina .barra { flex: 1; min-width: 0; overflow: hidden; padding-left: 10px; }
.pagina .colophon { flex: none; margin-top: 6px; padding-top: 4px; font-size: 6.5pt; letter-spacing: .06em; }

.pagina .giudizio, .pagina .perche, .pagina .originale, .pagina .repo .firma { display: none !important; }
.pagina .testata h1 { font-size: 46pt; padding: 2px 0 0; }
.pagina .orecchio { font-size: 7pt; padding: 4px 7px; }
.pagina .riga { font-size: 7.5pt; padding: 3px 0; }
.pagina .apertura { padding-bottom: 6px; margin-bottom: 6px; }
.pagina .apertura h3 { font-size: 22pt; margin: 2px 0 4px; }
.pagina .apertura .corpo { font-size: 10.5pt; line-height: 1.35; }
.pagina .apertura .corpo::first-letter { font-size: 3em; padding: 3px 5px 0 0; }
.pagina article { break-inside: avoid; padding-bottom: 5px; margin-bottom: 5px; border-bottom: 1px solid #0003; }
.pagina article h3 { font-size: 10.5pt; line-height: 1.15; margin: 1px 0 2px; }
.pagina article.forte h3 { font-size: 13pt; }
.pagina .repo h3 { font-size: 9.5pt; margin: 1px 0 2px; }
.pagina .repo .corpo { font-size: 8pt; line-height: 1.3; }
.pagina .corpo { margin: 0 0 2px; }
.pagina .occhiello, .pagina .firma { font-size: 6.8pt; }
.pagina .rubrica { font-size: 7.5pt; margin: 0 0 5px; padding: 3px 0 2px; }
.pagina .sottorubrica { font-size: 10pt; margin: 4px 0 3px; }
.pagina .voce { padding: 3px 0; font-size: 8.3pt; }
.pagina .voce > span { font-size: 6.8pt; }
.pagina .barra h2 { font-size: 8.5pt; margin: 0 0 3px; }
.pagina .barra ol + h2 { margin-top: 7px; }
.pagina .barra li, .pagina .coda li { font-size: 8.6pt; line-height: 1.22; padding: 2px 0; gap: 0 5px; }
.pagina .barra li span, .pagina .coda li span { font-size: 6.8pt; }
.pagina .coda { margin-top: 5px; padding-top: 3px; border-top: 3px double var(--filetto); }
.pagina .coda h2 { font-size: 8.5pt; margin: 0 0 3px; }
"""

JS = """
const radice = document.documentElement;
if (location.protocol === "file:") radice.classList.add("statico");
const anteprima = new URLSearchParams(location.search).has("carta");     // ?carta: i fogli come usciranno in stampa
radice.classList.toggle("carta", anteprima);
const verso = document.querySelector(".strumenti a");
if (verso && anteprima) { verso.href = location.pathname; verso.textContent = "Torna al giornale"; }

document.addEventListener("click", async (ev) => {
  const b = ev.target.closest(".giudizio button");
  if (!b) return;
  const box = b.parentElement, g = b.getAttribute("aria-pressed") === "true" ? 0 : +b.dataset.g;
  const r = await fetch("/giudizio", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: box.dataset.id, g }) });
  if (r.ok) box.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(+x.dataset.g === g)));
});

// ── i fogli A4 ──
// Due fogli a misura fissa, costruiti qui. Si misura ogni articolo (una volta), poi lo si dispone a mano nelle
// quattro colonne (2 per foglio) come farebbe un menabò: in ordine, senza spezzare un articolo. Se non ci sta
// tutto in due fogli, l'articolo meno importante diventa un titolo nella barra (prima lo sport, poi le notizie),
// e si riprova. I riassunti non si accorciano mai. La barra dei titoli si riempie allo stesso modo; ciò che
// non ci sta, dal fondo, non si stampa. Il browser non spezza niente: il risultato è identico in ogni browser.
const S = (tag, classe = "") => Object.assign(document.createElement(tag), { className: classe });
const copia = (el) => {
  const c = el.cloneNode(true);
  c.removeAttribute("id");
  c.querySelectorAll("[id]").forEach((x) => x.removeAttribute("id"));
  return c;
};
const alt = (el) => {
  const s = getComputedStyle(el);
  return el.getBoundingClientRect().height + parseFloat(s.marginTop) + parseFloat(s.marginBottom);
};
const eTitolo = (el) => el.classList.contains("rubrica") || el.classList.contains("sottorubrica");
const flusso = document.querySelector(".flusso");
const barraFonte = document.querySelector(".laterale");
const contenitore = document.querySelector(".fogli");

function creaPagina(n) {
  const p = S("div", "pagina"), corpo = S("div", "corpo"), zona = S("div", "zona"), fisse = S("div", "fisse");
  const cols = [S("div", "col"), S("div", "col")], barra = S("aside", "barra");
  const testata = document.querySelector(".testata"), apertura = document.querySelector(".apertura");
  if (n === 0 && testata) p.append(copia(testata));
  if (n === 0 && apertura) zona.append(copia(apertura));
  fisse.append(...cols);
  zona.append(fisse);
  corpo.append(zona, barra);
  p.append(corpo);
  return { p, cols, barra };
}

// Le voci del flusso in "unità": un titolo (o più, di fila) va sempre con la voce che segue, e un titolo il cui
// gruppo si è svuotato sparisce.
function unita(declassati) {
  const figli = [...flusso.children].filter((e) => !declassati.has(e));
  const voci = figli.filter((e) => !eTitolo(e));
  const regge = (t) => voci.some((v) => v.dataset.gruppo === t.dataset.gruppo
    || v.dataset.gruppo.startsWith(t.dataset.gruppo + ":"));
  const out = [];
  let coda = [];
  for (const e of figli) {
    if (eTitolo(e) && !regge(e)) continue;
    coda.push(e);
    if (!eTitolo(e)) { out.push(coda); coda = []; }
  }
  return out;
}

// Colonne una dopo l'altra, come nei giornali: si riempie la prima, poi la seconda, poi il foglio dopo.
function disponi(lista, cap) {
  const colonne = cap.map(() => []), resto = [], max = Math.max(...cap);
  let c = 0, usato = 0;
  for (const x of lista) {
    if (x.h > max) { resto.push(x); continue; }
    while (c < cap.length && usato + x.h > cap[c]) { c++; usato = 0; }
    if (c >= cap.length) { resto.push(x); continue; }
    colonne[c].push(x);
    usato += x.h;
  }
  return { colonne, resto };
}

// L'ultimo foglio in uso: colonne pari (la minima altezza comune) invece di una piena e l'altra vuota.
function pari(lista, cap) {
  const tot = lista.reduce((s, x) => s + x.h, 0);
  for (let H = Math.max(tot / 2, ...lista.map((x) => x.h)); H < cap; H += 3) {
    const r = disponi(lista, [H, H]);
    if (!r.resto.length) return r.colonne;
  }
  return disponi(lista, [cap, cap]).colonne;
}

// Prima si sacrificano sport e gaming, poi le notizie; dentro ogni gruppo, dal meno importante. Ma l'articolo più
// forte di sport e di gaming è protetto: una sezione con un articolo vero non resta solo titoli in barra (si
// sacrifica solo quando non c'è più nient'altro da togliere).
const livello = (a) => (a.dataset.gruppo === "sport" || a.dataset.gruppo === "gaming" ? 0 : 1);
const protetti = new Set(["sport", "gaming"].map((g) => [...flusso.querySelectorAll(`article[data-gruppo="${g}"]`)]
  .sort((x, y) => y.dataset.punti - x.dataset.punti)[0]).filter(Boolean));
const piuDebole = (declassati) => {
  const ordinati = (lista) => lista.sort((x, y) => livello(x) - livello(y) || x.dataset.punti - y.dataset.punti);
  const tutti = [...flusso.querySelectorAll("article[data-gruppo]")].filter((a) => !a.dataset.fisso && !declassati.has(a));
  return ordinati(tutti.filter((a) => !protetti.has(a)))[0] || ordinati(tutti)[0];
};

// Riempie le barre foglio dopo foglio, con al massimo `limiti.get(chiave)` voci per sezione. Restituisce ciò che
// non ci sta, per sezione: { titolo, chiave, inizio, voci }.
function riempiUna(pagine, sezioni, limiti) {
  const sfora = (b) => b.scrollHeight > b.clientHeight + 1;
  const fuori = [];
  let pi = 0, pieno = false;
  for (const s of sezioni) {
    const voci = s.voci.slice(0, limiti.get(s.chiave));
    if (!voci.length) continue;
    if (pieno) { fuori.push({ ...s, inizio: 0, voci }); continue; }
    let h2, ol;
    const apri = (fatti) => {
      h2 = S("h2");
      h2.textContent = s.titolo;
      ol = S("ol", s.chiave);
      ol.style.counterReset = "s " + fatti;
      pagine[pi].barra.append(h2, ol);
    };
    apri(0);
    for (let i = 0; i < voci.length; i++) {
      const li = copia(voci[i]);
      li.classList.remove("riserva");
      ol.append(li);
      if (!sfora(pagine[pi].barra)) continue;
      li.remove();
      if (!ol.children.length) { h2.remove(); ol.remove(); }
      if (++pi < pagine.length) {
        apri(i);
        ol.append(li);
        if (!sfora(pagine[pi].barra)) continue;
        li.remove();
        ol.children.length || (h2.remove(), ol.remove());
      }
      pieno = true;                                        // niente altri fogli: il resto si prova in coda alle colonne
      fuori.push({ ...s, inizio: i, voci: voci.slice(i) });
      break;
    }
  }
  return fuori;
}

// Ogni sezione della barra (sport, gaming, Italia, estero, ricerca) mantiene almeno MINIMO titoli: se una sezione
// in fondo resta senza spazio perché "In breve" (dove finiscono anche gli articoli declassati) è lungo, si tolgono
// voci dalle sezioni che la precedono, la più lunga per prima, finché il minimo c'è per tutte. Le voci tolte si
// provano poi in coda alle colonne, come quelle che non ci stavano.
const MINIMO = 3;

function riempiBarre(pagine, declassati) {
  const ids = new Set([...declassati].map((a) => a.id));
  const sezioni = [...barraFonte.querySelectorAll("h2")].map((h) => {
    const ol = h.nextElementSibling;
    return { titolo: h.textContent, chiave: ol.className,
      voci: [...ol.children].filter((li) => !li.classList.contains("riserva") || ids.has(li.dataset.di)) };
  }).filter((s) => s.voci.length);
  const limiti = new Map(sezioni.map((s) => [s.chiave, s.voci.length]));
  let fuori;
  for (let giro = 0; giro < 80; giro++) {
    pagine.forEach((g) => g.barra.replaceChildren());
    fuori = riempiUna(pagine, sezioni, limiti);
    const fuoriDi = (s) => fuori.find((f) => f.chiave === s.chiave)?.voci.length ?? 0;
    const senzaMinimo = sezioni.findIndex((s) => s.chiave !== "brevi"
      && limiti.get(s.chiave) - fuoriDi(s) < Math.min(s.voci.length, MINIMO));
    if (senzaMinimo < 0) break;
    const candidate = sezioni.slice(0, senzaMinimo)
      .filter((s) => limiti.get(s.chiave) > (s.chiave === "brevi" ? 0 : MINIMO));
    if (!candidate.length) break;
    const s = candidate.reduce((a, b) => (limiti.get(b.chiave) > limiti.get(a.chiave) ? b : a));
    limiti.set(s.chiave, limiti.get(s.chiave) - 1);
  }
  // fuori dalla barra = ciò che non ci sta + ciò che il limite ha tolto, sezione per sezione, in ordine
  return sezioni.map((s) => {
    const dentro = s.voci.slice(0, limiti.get(s.chiave)), f = fuori.find((x) => x.chiave === s.chiave);
    const inizio = f ? f.inizio : dentro.length;
    return { titolo: s.titolo, chiave: s.chiave, inizio, voci: [...(f ? f.voci : []), ...s.voci.slice(dentro.length)] };
  }).filter((f) => f.voci.length);
}

// I titoli che nella barra non stanno finiscono in coda alle colonne dell'ultimo foglio, dove un articolo intero
// non entrava e restava uno spazio bianco. Restituisce quanti ne restano fuori.
function riempiCoda(pagina, fuori) {
  const sfora = (c) => c.scrollHeight > c.clientHeight + 1;
  let persi = 0;
  for (const s of fuori) {
    const blocchi = new Map();                             // per ogni colonna, il blocco di questa sezione
    let fatti = s.inizio;
    s.voci.forEach((v, i) => {
      if (i && fatti < s.inizio + i) { persi++; return; }  // una voce non è entrata: le seguenti restano fuori con lei
      for (const c of pagina.cols) {
        let b = blocchi.get(c);
        const nuovo = !b;
        if (nuovo) {
          b = S("div", "coda");
          const h2 = S("h2");
          h2.textContent = s.titolo;
          const ol = S("ol", s.chiave);
          ol.style.counterReset = "s " + fatti;
          b.append(h2, ol);
          c.append(b);
          blocchi.set(c, b);
        }
        const li = copia(v);
        li.classList.remove("riserva");
        b.querySelector("ol").append(li);
        if (!sfora(c)) { fatti++; return; }
        li.remove();
        if (nuovo) { b.remove(); blocchi.delete(c); }
      }
      persi++;
    });
  }
  return persi;
}

// nFogli = 1: prova a stare in un foglio solo (null se non ci sta senza togliere nulla). nFogli = 2: il caso normale.
function componi(margine, nFogli) {
  contenitore.replaceChildren();
  const pagine = Array.from({ length: nFogli }, (_, n) => creaPagina(n));
  const colophon = document.querySelector(".colophon");
  if (colophon) pagine[nFogli - 1].p.append(copia(colophon));
  pagine.forEach((g) => contenitore.append(g.p));
  const cap = pagine.flatMap((g) => g.cols.map((c) => c.getBoundingClientRect().height - margine));

  const altezze = new Map();                               // ogni voce si misura una volta sola, dentro una colonna vera
  for (const e of flusso.children) {
    const n = copia(e);
    pagine[0].cols[0].append(n);
    altezze.set(e, alt(n));
    n.remove();
  }
  const declassati = new Set();
  let esito;
  for (;;) {
    const lista = unita(declassati).map((u) => ({ u, h: u.reduce((s, e) => s + altezze.get(e), 0) }));
    esito = disponi(lista, cap);
    if (!esito.resto.length) break;
    if (nFogli === 1) return null;                         // un foglio solo va bene se il flusso ci sta senza togliere nulla
    const debole = piuDebole(declassati);
    if (!debole) break;                                    // niente più da togliere: ciò che non entra resta fuori
    declassati.add(debole);
  }
  const ultimo = Math.max(0, ...esito.colonne.map((c, i) => (c.length ? i >> 1 : 0)));
  const dellUltimo = esito.colonne.slice(ultimo * 2, ultimo * 2 + 2).flat();
  const bilanciate = pari(dellUltimo, Math.min(cap[ultimo * 2], cap[ultimo * 2 + 1]));
  esito.colonne[ultimo * 2] = bilanciate[0];
  esito.colonne[ultimo * 2 + 1] = bilanciate[1];
  esito.colonne.forEach((col, i) => col.forEach((x) => pagine[i >> 1].cols[i & 1].append(...x.u.map(copia))));

  const fuori = riempiBarre(pagine, declassati);
  if (pagine[1] && !pagine[1].cols.some((c) => c.children.length) && !pagine[1].barra.children.length) pagine[1].p.remove();
  const persi = riempiCoda([...pagine].reverse().find((g) => g.p.isConnected), fuori);
  if (nFogli === 1 && persi > 2) return null;              // troppi titoli lasciati fuori: meglio due fogli
  radice.dataset.fogli = JSON.stringify({ pagine: contenitore.children.length, declassati: declassati.size, persi, margine });
  return pagine.every((g) => g.cols.every((c) => c.scrollHeight <= c.clientHeight + 1));
}

function costruisciFogli() {
  if (!flusso || !contenitore) return;
  radice.classList.remove("fogli-pronti");
  radice.classList.add("fogli-in-costruzione");
  for (let margine = 0, prova = 0; prova < 6; prova++, margine += 8) {
    const uno = componi(margine, 1);                       // un foglio solo, se basta
    if (uno === true) break;
    if (uno === null && componi(margine, 2)) break;        // altrimenti due; se una colonna sfora, si riprova con margine
  }
  radice.classList.remove("fogli-in-costruzione");
  radice.classList.add("fogli-pronti");
}

document.querySelector(".strumenti .stampa")?.addEventListener("click", () => {
  if (!radice.classList.contains("fogli-pronti")) costruisciFogli();
  print();
});
addEventListener("beforeprint", () => { if (!radice.classList.contains("fogli-pronti")) costruisciFogli(); });

// i fogli si misurano con i caratteri veri: prima si caricano, poi si costruisce (e di nuovo se ne arrivano altri)
const carattere = ["900 20px 'Playfair Display'", "700 20px 'Playfair Display'", "400 20px 'Playfair Display'",
  "italic 400 20px 'Playfair Display'", "400 20px 'Source Serif 4'", "600 20px 'Source Serif 4'",
  "italic 400 20px 'Source Serif 4'", "400 20px 'UnifrakturMaguntia'"];
let attesa;
const ricostruisci = () => { clearTimeout(attesa); attesa = setTimeout(costruisciFogli, 120); };
Promise.all(carattere.map((f) => document.fonts.load(f).catch(() => null))).then(() => {
  costruisciFogli();
  document.fonts.addEventListener("loadingdone", ricostruisci);
});
"""
