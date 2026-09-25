"""Impagina un'edizione come prima pagina di un quotidiano, in bianco e nero e stampabile.

A sinistra (3/4): apertura, notizie, repository GitHub, sport (o il weekend a Roma). A destra (1/4), per tutta
l'altezza: i titoli (in breve, Italia, estero, sport, ricerca).
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


def breve(s):
    """Il modello sfora spesso il limite di parole: sulla pagina al massimo due frasi."""
    return " ".join(re.split(r"(?<=[.!?])\s+", (s or "").strip())[:2])


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
    nascosta, la mostra lo script (al posto dell'articolo) se in stampa non si sta in due pagine."""
    classe = f' class="riserva" data-di="{escape(riserva_di)}"' if riserva_di else ""
    return (f'<li{classe}><a href="{escape(r["url"])}">{escape(_titolo(r))}</a>'
            f'<span>{escape(r["fonte"])}</span></li>')


def articolo(r, classe=""):
    if r["sezione"] == "sport":
        occhiello = f"{SPORT.get(r['rubrica'], 'Sport')} · {escape(r['fonte'])}"
    else:
        occhiello = f"{RUBRICHE.get(r['rubrica'], 'Notizie')} · {escape(r['fonte'])}"
    if r["copertura"] > 1:
        occhiello += f" · su {r['copertura']} testate"
    originale = f'<p class="originale">{escape(r["titolo"])}</p>' if _titolo(r) != r["titolo"] else ""
    corpo = f'<p class="corpo">{escape(r["riassunto"])}</p>' if r["riassunto"] else ""
    return f"""
<article class="{classe}" id="{escape(r['id'])}" data-punti="{r['punti']}">
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
    return f"""
<article class="repo" id="{escape(r['id'])}">
  <p class="occhiello">{escape(r['rubrica'] or '')} · ★ {punto(x['stelle'])} · {crescita}{linguaggio}</p>
  <h3><a href="{escape(r['url'])}">{escape(padrone)}/<b>{escape(nome)}</b></a></h3>
  {corpo}
  {f'<p class="firma">{escape(temi)}</p>' if temi else ''}
  {pulsanti(r)}
</article>"""


def _testatina(nome):
    return f'<h2 class="testatina"><span>{nome}</span></h2>'


WEEKEND = {"guide": "Guide", "musica": "Musica", "sagre": "Sagre e feste", "mostre": "Mostre"}


def sezione_weekend(eventi):
    colonne = ""
    for chiave, nome in WEEKEND.items():
        voci = "".join(f'<li id="{escape(r["id"])}"><a href="{escape(r["url"])}">{escape(r["titolo"])}</a>'
                       f'<span>{escape(r["fonte"])}</span>{pulsanti(r)}</li>'
                       for r in eventi if r["rubrica"] == chiave)
        if voci:
            colonne += f'<div class="agenda"><h3>{nome}</h3><ol>{voci}</ol></div>'
    return f'<section class="sezione weekend">{_testatina("Il weekend a Roma e dintorni")}<div class="agende">{colonne}</div></section>'


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
    italia, estero = scelti("attualita", "breve", "AND rubrica='italia'"), scelti("attualita", "breve", "AND rubrica='estero'")
    ricerca = scelti("ricerca", "breve")
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

    # Il giornale è su due colonne per tutta la sua altezza, come un quotidiano: a sinistra (3/4) il contenuto
    # principale, a destra (1/4) la barra dei titoli. Le "riserve" sono gli articoli in versione ridotta:
    # nascoste, le mostra lo script (al posto dell'articolo) se in stampa non si sta in due fogli.
    lista = lambda righe, riserve=(): "".join(voce(r) for r in righe) + "".join(voce(r, r["id"]) for r in riserve)
    laterale = [("brevi", "In breve", lista(brevi, resto)), ("italia", "Italia", lista(italia)),
                ("estero", "Estero", lista(estero)), ("sport", "Sport", lista(sport_brevi, sport)),
                ("ricerca", "Dalla ricerca", lista(ricerca))]
    laterale = "".join(f'<h2>{nome}</h2><ol class="{chiave}">{voci}</ol>' for chiave, nome, voci in laterale if voci)

    # le altre notizie in un solo flusso di colonne, con le rubriche come titoletti; il terzo più forte più grande
    forti = {r["id"] for r in sorted(resto, key=lambda r: -r["punti"])[:max(1, len(resto) // 3)]}
    gruppi = ""
    for chiave, nome in RUBRICHE.items():
        pezzi = [r for r in resto if r["rubrica"] == chiave]
        if pezzi:
            gruppi += (f'<div class="gruppo"><h2 class="rubrica">{nome}</h2>'
                       f'{"".join(articolo(r, "forte" if r["id"] in forti else "") for r in pezzi)}</div>')
    sezioni = articolo(apertura, "apertura") if apertura else '<p class="vuota">Nessuna notizia per esteso oggi.</p>'
    sezioni += f'<section class="sezione notizie"><div class="colonne">{gruppi}</div></section>' if gruppi else ""
    if repo:
        sezioni += (f'<section class="sezione codice">{_testatina("Dal codice · i più in crescita nei tuoi temi")}'
                    f'<div class="repos">{"".join(scheda_repo(r) for r in repo)}</div></section>')
    if sport:
        sezioni += (f'<section class="sezione sport">{_testatina("Sport")}'
                    f'<div class="colonne">{"".join(articolo(r) for r in sport)}</div></section>')
    if eventi:
        sezioni += sezione_weekend(eventi)
    giornale = f'<div class="giornale"><div class="principale">{sezioni}</div><aside class="laterale">{laterale}</aside></div>'

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
<link href="https://fonts.googleapis.com/css2?family=UnifrakturMaguntia&family=Playfair+Display:ital,wght@0,700;0,900;1,400&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="strumenti"><a href="?carta">Anteprima di stampa</a><button class="stampa">Stampa</button></div>
<main class="foglio">
<header class="testata">
  <div class="orecchio">Notizie {len(notizie) + len(brevi)}<br>Codice {len(repo)}<br>Sport {len(sport) + len(sport_brevi)}</div>
  <h1>Il Radar</h1>
  {orecchio_meteo(con, data)}
  <p class="riga"><span>Anno {anno} · N. {numero}</span><span>{giorno}</span><span>Tutte le notizie che ti riguardano</span></p>
</header>
{giornale}
{fondo}
<footer class="colophon">Notizie: The Verge, TechCrunch, The Register, The Record, BleepingComputer, Ars Technica,
Rest of World, Hacker News, Il Post, Agenda Digitale, Key4biz, Google News · attualità: ANSA, Il Fatto Quotidiano,
ISTAT · sport: OA Sport, FIDAL, Runner's World, ANSA · codice: GitHub · ricerca: arXiv · meteo: Aeronautica
Militare<br>Scelti dalle parole chiave del profilo · tradotti e riassunti in locale da MiniCPM4.1 · nessun testo
inviato a servizi esterni</footer>
</main>
<script>{JS}</script>
</body>
</html>"""


BASE = """
:root { color-scheme: light; --inchiostro: #111; --grigio: #5a5a5a; --filetto: #111; --carta: #fff; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--carta); color: var(--inchiostro);
  font: 400 17px/1.5 "Source Serif 4", Georgia, serif; font-optical-sizing: auto; }
a { color: inherit; text-decoration: none; }
a:hover { text-decoration: underline; text-underline-offset: 2px; }
.foglio { max-width: 1180px; margin: 0 auto; padding: 24px 16px 48px; }
h2, h3 { font-family: "Playfair Display", Georgia, serif; }
h3 { overflow-wrap: break-word; }

/* testata */
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
.apertura { padding-bottom: 18px; border-bottom: 3px double var(--filetto); }
.apertura h3 { font-size: clamp(30px, 4.4vw, 50px); line-height: 1.05; font-weight: 900; margin: 6px 0 8px; }
.apertura .originale { font-size: 16px; }
.apertura .corpo { font-size: 20px; line-height: 1.45; text-align: justify; hyphens: auto; }
.apertura .corpo::first-letter { float: left; font: 900 3.4em/.8 "Playfair Display", serif; padding: 6px 8px 0 0; }
.laterale { border-left: 1px solid var(--filetto); padding-left: 20px; }
.laterale h2 { margin: 4px 0 10px; font-size: 15px; text-transform: uppercase; letter-spacing: .14em; }
.laterale ol + h2 { margin-top: 20px; }
.laterale ol { margin: 0; padding: 0; list-style: none; counter-reset: s; }
.laterale li { display: grid; grid-template-columns: auto 1fr; gap: 0 10px; padding: 8px 0; border-top: 1px solid #0003;
  font: 400 16px/1.3 "Playfair Display", serif; counter-increment: s; }
.laterale li::before { content: counter(s); font-weight: 700; }
.laterale li span { grid-column: 2; font: italic 400 13px/1.3 "Source Serif 4", serif; color: var(--grigio); }

/* per stare in due fogli lo script nasconde un articolo e mostra la sua riga di riserva in lista */
li.riserva:not(.attiva), .declassata, .tagliata { display: none !important; }

/* flussi a colonne: notizie, ricerca. Il browser riempie le colonne una dopo l'altra, senza buchi. */
.testatina { display: flex; align-items: center; gap: 14px; margin: 26px 0 16px; font-size: 14px;
  text-transform: uppercase; letter-spacing: .2em; }
.testatina::before, .testatina::after { content: ""; flex: 1; border-top: 1px solid var(--filetto); }
.notizie { padding-top: 22px; }
.colonne { column-count: 2; column-gap: 28px; column-rule: 1px solid #0004; }
.colonne article { break-inside: avoid; padding-bottom: 16px; margin-bottom: 16px; border-bottom: 1px solid #0003; }
.colonne h3 { font-size: 20px; line-height: 1.15; margin: 4px 0; }
.colonne .forte h3 { font-size: 27px; font-weight: 900; line-height: 1.08; }
.rubrica { margin: 0 0 12px; padding: 5px 0 4px; border-top: 3px double var(--filetto); border-bottom: 1px solid var(--filetto);
  font: 600 13px/1.2 "Source Serif 4", serif; text-transform: uppercase; letter-spacing: .18em; text-align: center;
  break-after: avoid; }
.gruppo[hidden] { display: none; }

.occhiello { margin: 0; font-size: 12px; text-transform: uppercase; letter-spacing: .12em; color: var(--grigio); }
.originale { margin: 0 0 8px; font-style: italic; font-size: 14px; color: var(--grigio); line-height: 1.35; }
.corpo { margin: 0 0 8px; }
.perche { margin: 0 0 8px; font-style: italic; }
.perche span { font-style: normal; font-weight: 600; font-variant: small-caps; letter-spacing: .03em; }
.firma { margin: 0; font-size: 13px; font-variant: small-caps; letter-spacing: .03em; color: var(--grigio); }

/* repository: anche loro in flusso (a griglia ogni riga era alta quanto la scheda più lunga) */
.repos { column-count: 2; column-gap: 24px; column-rule: 1px solid #0004; }
.repo { break-inside: avoid; padding-bottom: 14px; margin-bottom: 14px; border-bottom: 1px solid #0003; }
.repo h3 { font: 400 19px/1.2 "Playfair Display", serif; margin: 4px 0 8px; overflow-wrap: anywhere; }
.repo h3 b { font-weight: 900; }
.repo .corpo { font-size: 15px; line-height: 1.4; }

/* il weekend a Roma: le quattro rubriche scorrono in colonna una dopo l'altra */
.agende { column-count: 2; column-gap: 24px; column-rule: 1px solid #0004; }
.agenda h3 { margin: 0 0 6px; font-size: 20px; break-after: avoid; }
.agenda h3:not(:first-child), .agenda + .agenda h3 { margin-top: 14px; }
.agenda ol { margin: 0; padding: 0; list-style: none; }
.agenda li { break-inside: avoid; padding: 8px 0; border-top: 1px solid #0002; font: 400 15px/1.35 "Source Serif 4", serif; }
.agenda li > span { display: block; font-style: italic; color: var(--grigio); font-size: 13px; }
.agenda .giudizio button { padding: 4px 8px; font-size: 11px; }

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
@media screen {      /* l'anteprima ?carta sembra un foglio; in stampa questo non serve */
  .carta body { background: #e8e8e8; }
  .carta .foglio { background: var(--carta); margin: 6mm auto; }
}

/* schermi stretti: solo a schermo e non nell'anteprima di stampa (un A4 è largo ~720px e le prenderebbe) */
@media screen and (max-width: 900px) {
  html:not(.carta) .giornale { grid-template-columns: minmax(0, 1fr); }
  html:not(.carta) .laterale { border-left: 0; border-top: 3px double var(--filetto); padding: 12px 0 0; }
}
@media screen and (max-width: 620px) {
  html:not(.carta) .colonne, html:not(.carta) .agende, html:not(.carta) .repos,
  html:not(.carta) .fondo ol { column-count: 1; }
  html:not(.carta) .testata { grid-template-columns: minmax(0, 1fr); }
  html:not(.carta) .orecchio { display: none; }
  html:not(.carta) .apertura .corpo { text-align: left; }
  html:not(.carta) .riga { justify-content: center; }
  html:not(.carta) .strumenti { position: static; justify-content: flex-end; padding: 8px 16px 0; }
}
"""

# Regole della carta: valgono in stampa e, con la classe .carta, nell'anteprima e mentre lo script misura.
# Scritte una volta sola: CSS le ripete sotto @media print e con il prefisso html.carta.
CARTA = """
body { font-size: 8.8pt; line-height: 1.35; }
.strumenti, .giudizio, .fondo, .perche, .originale, .repo .firma { display: none !important; }
.foglio { max-width: none; width: 210mm; padding: 10mm; box-decoration-break: clone; -webkit-box-decoration-break: clone; }
.testata h1 { font-size: 46pt; padding: 2px 0 0; }
.orecchio { font-size: 7pt; padding: 4px 7px; }
.riga { font-size: 7.5pt; padding: 3px 0; }
.giornale { padding-top: 8px; gap: 12px; }
.apertura { padding-bottom: 6px; }
.apertura h3 { font-size: 22pt; margin: 2px 0 4px; }
.apertura .corpo { font-size: 10.5pt; line-height: 1.35; }
.apertura .corpo::first-letter { font-size: 3em; padding: 3px 5px 0 0; }
.laterale { padding-left: 10px; }
.laterale h2 { font-size: 8.5pt; margin: 0 0 3px; }
.laterale li { font-size: 8.6pt; line-height: 1.22; padding: 2px 0; gap: 0 5px; }
.laterale li span { font-size: 6.8pt; }
.testatina { margin: 8px 0 6px; font-size: 8.5pt; }
.notizie { padding-top: 8px; }
.colonne { column-gap: 14px; }
.colonne article { padding-bottom: 5px; margin-bottom: 5px; }
.colonne h3 { font-size: 10.5pt; margin: 1px 0 2px; }
.colonne .forte h3 { font-size: 13pt; }
.rubrica { font-size: 7.5pt; margin-bottom: 5px; padding: 3px 0 2px; }
.occhiello, .firma { font-size: 6.8pt; }
.corpo { margin: 0 0 2px; }
.laterale ol + h2 { margin-top: 7px; }
.repos { column-gap: 12px; }
.repo { padding-bottom: 5px; margin-bottom: 5px; }
.repo h3 { font-size: 9.5pt; margin: 1px 0 2px; }
.repo .corpo { font-size: 8pt; line-height: 1.3; }
.agende { column-gap: 12px; }
.agenda h3 { font-size: 10pt; margin-bottom: 3px; }
.agenda h3:not(:first-child), .agenda + .agenda h3 { margin-top: 6px; }
.agenda li { font-size: 8.3pt; padding: 3px 0; }
.agenda li > span { font-size: 6.8pt; }
.colophon { margin-top: 8px; font-size: 6.5pt; }
a:hover { text-decoration: none; }
"""


def _in_carta(regole):
    """'a, b { ... }' -> 'html.carta a, html.carta b { ... }'"""
    return re.sub(r"([^{}]+)\{", lambda m: ", ".join("html.carta " + s.strip() for s in m[1].split(",")) + " {",
                  regole)


# Margine del foglio a zero: così il browser non ha dove stampare le sue intestazioni (titolo, data, indirizzo).
# I 10 mm di margine li dà .foglio, ripetuti su ogni pagina da box-decoration-break: clone.
CSS = BASE + "\n@page { size: A4; margin: 0; }\n@media print {" + CARTA + "}\n" + _in_carta(CARTA)

JS = """
const radice = document.documentElement;
if (location.protocol === "file:") radice.classList.add("statico");
const parametri = new URLSearchParams(location.search);
const anteprima = parametri.has("carta");     // ?carta: la pagina come uscirà in stampa
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

// ── al massimo due fogli ──
// Solo sulla carta (stampa e anteprima). Il giornale ha due colonne alte quanto tutto il giornale: la principale
// e la barra dei titoli. Finché non sta in due fogli: se è più lunga la principale, l'articolo più debole (prima
// lo sport, poi le notizie) diventa un titolo in barra; se è più lunga la barra, si tolgono i titoli dal fondo,
// a cominciare dai meno importanti. I riassunti non si accorciano mai: o l'articolo c'è intero, o è un titolo.
// Le misure si prendono nel formato del foglio: prima di stampare la pagina passa in .carta, poi torna com'era.
const MM = 96 / 25.4;
const LIMITE = (2 * 277 * 0.93 + 20) * MM;    // due fogli da 277 mm utili (+20 mm di margini), meno i salti pagina
const foglio = document.querySelector(".foglio");
const principale = document.querySelector(".principale"), laterale = document.querySelector(".laterale");

function declassa(a) {
  a.classList.add("declassata");
  document.querySelector(`.riserva[data-di="${CSS.escape(a.id)}"]`)?.classList.add("attiva");
  for (const g of document.querySelectorAll(".notizie .gruppo")) g.hidden = !g.querySelector("article:not(.declassata)");
  for (const s of document.querySelectorAll(".sezione.sport")) s.hidden = !s.querySelector("article:not(.declassata)");
}

function impagina() {
  document.querySelectorAll(".declassata").forEach((a) => a.classList.remove("declassata"));
  document.querySelectorAll(".riserva.attiva").forEach((l) => l.classList.remove("attiva"));
  document.querySelectorAll(".tagliata").forEach((l) => l.classList.remove("tagliata"));
  document.querySelectorAll(".gruppo[hidden], .sezione[hidden], .laterale h2[hidden]").forEach((g) => { g.hidden = false; });
  if (!radice.classList.contains("carta") || !principale || !laterale) return;
  const deboli = (sel) => [...document.querySelectorAll(sel)].sort((x, y) => x.dataset.punti - y.dataset.punti);
  const articoli = [...deboli(".sport article"), ...deboli(".notizie article")];
  // titoli da togliere, dal fondo e dal meno importante: ricerca, attualità (estero e Italia alternati), sport,
  // brevi; mai le riserve
  const dal_fondo = (c) => [...laterale.querySelectorAll(`ol.${c} > li:not(.riserva)`)].reverse();
  const estero = dal_fondo("estero"), italia = dal_fondo("italia");
  const attualita = Array.from({ length: Math.max(estero.length, italia.length) }, (_, i) => [estero[i], italia[i]])
    .flat().filter(Boolean);
  const titoli = [...dal_fondo("ricerca"), ...attualita, ...dal_fondo("sport"), ...dal_fondo("brevi")];
  while (foglio.offsetHeight > LIMITE) {
    if (principale.offsetHeight >= laterale.offsetHeight && articoli.length) declassa(articoli.shift());
    else if (titoli.length) titoli.shift().classList.add("tagliata");
    else break;
  }
  // un titoletto senza più voci visibili sparisce
  for (const ol of laterale.querySelectorAll("ol")) {
    ol.previousElementSibling.hidden = ![...ol.children].some((li) => getComputedStyle(li).display !== "none");
  }
}

// "Stampa" passa sempre dall'anteprima: lì la pagina è già nel formato del foglio, anche su quei browser
// (spesso sul telefono) che non avvisano la pagina prima di stampare
document.querySelector(".strumenti .stampa")?.addEventListener("click", () => {
  if (anteprima) print(); else location.href = location.pathname + "?carta&stampa";
});

let attesa;
addEventListener("resize", () => { clearTimeout(attesa); attesa = setTimeout(impagina, 150); });
addEventListener("beforeprint", () => { radice.classList.add("carta"); impagina(); });
addEventListener("afterprint", () => { radice.classList.toggle("carta", anteprima); impagina(); });
document.fonts.ready.then(() => {
  impagina();
  if (parametri.has("stampa")) setTimeout(print, 300);
});


"""
