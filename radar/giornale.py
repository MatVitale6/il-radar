"""Impagina un'edizione come prima pagina di un quotidiano, in bianco e nero e stampabile.

Ordine: notizie (apertura, spalle, "In breve", poi le rubriche), repository GitHub, ricerca.
"""
import datetime as dt
import json
import re
from html import escape

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]
RUBRICHE = {"norme": "Governi e regole", "sicurezza": "Cybersicurezza", "tecnologia": "AI e sviluppo"}
RICERCA = {"ai": "Intelligenza artificiale", "sicurezza": "Sicurezza informatica"}


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


def articolo(r, classe=""):
    titolo = r["titolo_it"] or r["titolo"]
    if r["sezione"] == "notizie":
        occhiello = f"{RUBRICHE.get(r['rubrica'], 'Notizie')} · {escape(r['fonte'])}"
        if r["copertura"] > 1:
            occhiello += f" · su {r['copertura']} testate"
        firma = f'<a href="{escape(r["url"])}">Leggi su {escape(r["fonte"])}</a>'
    else:
        occhiello = f"{RICERCA.get(r['rubrica'], 'Ricerca')} · rilevanza {voto(r)}/10"
        firma = f'{escape(autori(r["autori"]))} — <a href="{escape(r["url"])}">{escape(r["fonte"])}</a>'
    originale = (f'<p class="originale">{escape(r["titolo"])}</p>'
                 if r["titolo_it"] and r["titolo_it"] != r["titolo"] else "")
    corpo = f'<p class="corpo">{escape(breve(r["riassunto"]))}</p>' if r["riassunto"] else ""
    return f"""
<article class="{classe}" id="{escape(r['id'])}">
  <p class="occhiello">{occhiello}</p>
  <h3><a href="{escape(r['url'])}">{escape(titolo)}</a></h3>
  {originale}{corpo}
  <p class="perche"><span>Perché è qui.</span> {escape(r['parole'])}</p>
  <p class="firma">{firma}</p>
  {pulsanti(r)}
</article>"""


def scheda_repo(r):
    x = json.loads(r["extra"])
    padrone, nome = r["titolo"].split("/", 1)
    stelle = f"{x['stelle']:,}".replace(",", ".")
    linguaggio = f" · {escape(x['linguaggio'])}" if x["linguaggio"] else ""
    temi = " · ".join(x["temi"][:4])
    corpo = f'<p class="corpo">{escape(breve(r["riassunto"]))}</p>' if r["riassunto"] else ""
    return f"""
<article class="repo" id="{escape(r['id'])}">
  <p class="occhiello">★ {stelle}{linguaggio}</p>
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
    return (f'<div class="orecchio destra meteo"><b>Il tempo a {escape(m["citta"])}</b><br>{m["cielo"]}<br>'
            f'{m["min"]}° – {m["max"]}° · pioggia {m["pioggia"]}%</div>')


def pagina(con, data, profilo):
    q = lambda sql, *a: con.execute(sql, (data, *a)).fetchall()
    notizie = q("SELECT * FROM elementi WHERE visto_il=? AND sezione='notizie' AND ruolo='articolo'"
                " ORDER BY punti DESC, copertura DESC")
    brevi = q("SELECT * FROM elementi WHERE visto_il=? AND sezione='notizie' AND ruolo='breve' ORDER BY punti DESC")
    repo = q("SELECT * FROM elementi WHERE visto_il=? AND sezione='github' AND ruolo='articolo' ORDER BY punti DESC")
    ricerca = q("SELECT * FROM elementi WHERE visto_il=? AND sezione='ricerca' AND ruolo='articolo' ORDER BY punti DESC")
    d = dt.date.fromisoformat(data)
    eventi = []
    if d.weekday() >= 5:            # sabato e domenica: il weekend a Roma (la domenica anche ciò che è uscito sabato)
        sabato = (d - dt.timedelta(days=d.weekday() - 5)).isoformat()
        eventi = con.execute("SELECT * FROM elementi WHERE sezione='weekend' AND ruolo='articolo' AND visto_il"
                             " BETWEEN ? AND ? ORDER BY punti DESC", (sabato, data)).fetchall()
    fuori = q("SELECT * FROM elementi WHERE visto_il=? AND ruolo IS NULL AND punti>0 AND sezione!='github'"
              " ORDER BY sezione='ricerca', punti DESC LIMIT ?", profilo["giornale"]["fondo"])
    numero = con.execute("SELECT COUNT(DISTINCT visto_il) FROM elementi WHERE visto_il<=? AND ruolo IS NOT NULL",
                         (data,)).fetchone()[0] or 1
    primo = con.execute("SELECT MIN(visto_il) FROM elementi").fetchone()[0] or data
    anno = romano(int(data[:4]) - int(primo[:4]) + 1)
    giorno = f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]} {d.year}"

    # apertura: la notizia più forte che abbia anche un testo (quelle di Google News hanno solo il titolo)
    apertura = next((r for r in notizie if r["riassunto"]), notizie[0] if notizie else None)
    resto = [r for r in notizie if r is not apertura]
    spalle, resto = resto[:2], resto[2:]
    in_breve = "".join(f'<li><a href="{escape(r["url"])}">{escape(r["titolo_it"] or r["titolo"])}</a>'
                       f'<span>{escape(r["fonte"])}</span></li>' for r in brevi) or "<li>Nient'altro oggi.</li>"
    if apertura:
        prima = f"""
<section class="prima">
  <div class="principale">
    {articolo(apertura, "apertura")}
    <div class="spalle">{"".join(articolo(r, "spalla") for r in spalle)}</div>
  </div>
  <aside class="sommario"><h2>In breve</h2><ol>{in_breve}</ol></aside>
</section>"""
    else:
        prima = '<section class="vuota"><p>Nessuna notizia sopra la soglia oggi.</p></section>'

    sezioni = ""
    for chiave, nome in RUBRICHE.items():
        pezzi = [r for r in resto if r["rubrica"] == chiave]
        if pezzi:
            sezioni += (f'<section class="sezione">{_testatina(nome)}'
                        f'<div class="colonne">{"".join(articolo(r) for r in pezzi)}</div></section>')
    if repo:
        sezioni += (f'<section class="sezione codice">{_testatina("Dal codice · repository nuovi della settimana")}'
                    f'<div class="repos">{"".join(scheda_repo(r) for r in repo)}</div></section>')
    if eventi:
        sezioni += sezione_weekend(eventi)
    elif ricerca:
        sezioni += (f'<section class="sezione ricerca">{_testatina("Dalla ricerca")}'
                    f'<div class="colonne">{"".join(articolo(r) for r in ricerca)}</div></section>')

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
<div class="strumenti"><button onclick="print()">Stampa</button></div>
<main class="foglio">
<header class="testata">
  <div class="orecchio">Notizie {len(notizie) + len(brevi)}<br>Repository {len(repo)}<br>Ricerca {len(ricerca)}</div>
  <h1>Il Radar</h1>
  {orecchio_meteo(con, data)}
  <p class="riga"><span>Anno {anno} · N. {numero}</span><span>{giorno}</span><span>Tutte le notizie che ti riguardano</span></p>
</header>
{prima}
{sezioni}
{fondo}
<footer class="colophon">Notizie: The Verge, TechCrunch, The Register, The Record, BleepingComputer, Ars Technica,
Rest of World, Hacker News, Il Post, Agenda Digitale, Key4biz, Google News · codice: GitHub · ricerca: arXiv<br>
Scelti dalle parole chiave del profilo · tradotti e riassunti in locale da MiniCPM4.1 · nessun testo inviato a servizi esterni</footer>
</main>
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

.testata { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 16px;
  border-bottom: 1px solid var(--filetto); }
.testata h1 { margin: 0; font: 400 clamp(52px, 10vw, 118px)/1 "UnifrakturMaguntia", serif; text-align: center;
  letter-spacing: .01em; padding: 8px 0 4px; }
.orecchio { justify-self: start; border: 1px solid var(--filetto); padding: 6px 10px; font-size: 12px; line-height: 1.35;
  font-variant: small-caps; letter-spacing: .04em; }
.orecchio.destra { justify-self: end; text-align: right; font-style: italic; font-variant: normal; }
.riga { grid-column: 1 / -1; margin: 0; display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  border-top: 3px double var(--filetto); padding: 6px 0; font-size: 13px; text-transform: uppercase; letter-spacing: .12em; }

h2, h3 { font-family: "Playfair Display", Georgia, serif; }
.prima { display: grid; grid-template-columns: minmax(0, 2.2fr) minmax(0, 1fr); gap: 28px; padding: 22px 0; border-bottom: 3px double var(--filetto); }
.apertura h3 { font-size: clamp(30px, 4.4vw, 50px); line-height: 1.05; font-weight: 900; margin: 6px 0 8px; }
.apertura .originale { font-size: 16px; }
.apertura .corpo { font-size: 20px; line-height: 1.45; }
.apertura .corpo::first-letter { float: left; font: 900 3.4em/.8 "Playfair Display", serif; padding: 6px 8px 0 0; }
.spalle { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); margin-top: 22px; padding-top: 18px;
  border-top: 1px solid var(--filetto); }
.spalle:empty { display: none; }
.spalla + .spalla { border-left: 1px solid #0004; padding-left: 24px; margin-left: 24px; }
.spalla h3 { font-size: 24px; line-height: 1.12; margin: 4px 0 6px; }
.sommario { border-left: 1px solid var(--filetto); padding-left: 24px; }
.sommario h2 { margin: 4px 0 12px; font-size: 15px; text-transform: uppercase; letter-spacing: .14em; }
.sommario ol { margin: 0; padding: 0; list-style: none; counter-reset: s; }
.sommario li { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; padding: 9px 0; border-top: 1px solid #0003;
  font: 400 16px/1.3 "Playfair Display", serif; counter-increment: s; }
.sommario li::before { content: counter(s); font-weight: 700; }
.sommario li span { font: 600 13px/1.6 "Source Serif 4", serif; color: var(--grigio); }

.testatina { display: flex; align-items: center; gap: 14px; margin: 26px 0 16px; font-size: 14px;
  text-transform: uppercase; letter-spacing: .2em; }
.testatina::before, .testatina::after { content: ""; flex: 1; border-top: 1px solid var(--filetto); }
.colonne { column-count: 3; column-gap: 28px; column-rule: 1px solid #0004; }
.colonne article { break-inside: avoid; padding-bottom: 16px; margin-bottom: 16px; border-bottom: 1px solid #0003; }
.colonne h3 { font-size: 22px; line-height: 1.15; margin: 4px 0 4px; }

.occhiello { margin: 0; font-size: 12px; text-transform: uppercase; letter-spacing: .12em; color: var(--grigio); }
.originale { margin: 0 0 8px; font-style: italic; font-size: 14px; color: var(--grigio); line-height: 1.35; }
.corpo { margin: 0 0 8px; }
.apertura .corpo { text-align: justify; hyphens: auto; }
h3 { overflow-wrap: break-word; }
.perche { margin: 0 0 8px; font-style: italic; }
.perche span { font-style: normal; font-weight: 600; font-variant: small-caps; letter-spacing: .03em; }
.firma { margin: 0; font-size: 13px; font-variant: small-caps; letter-spacing: .03em; color: var(--grigio); }

.giudizio { display: flex; gap: 8px; margin-top: 10px; }
.giudizio button { font: 600 12px/1 "Source Serif 4", serif; letter-spacing: .06em; text-transform: uppercase;
  background: none; color: var(--inchiostro); border: 1px solid var(--filetto); padding: 7px 10px; cursor: pointer; }
.giudizio button[aria-pressed="true"] { background: var(--inchiostro); color: var(--carta); }
.statico .giudizio { display: none; }

.fondo .nota { margin: 0 0 10px; font-style: italic; color: var(--grigio); font-size: 15px; }
.fondo ol { margin: 0; padding: 0; list-style: none; columns: 2; column-gap: 28px; column-rule: 1px solid #0004; }
.fondo li { break-inside: avoid; padding: 8px 0; border-top: 1px solid #0002; font-size: 15px; line-height: 1.35; }
.fondo .voto { display: inline-block; min-width: 1.6em; font-weight: 600; }
.fondo .giudizio { margin-top: 6px; }
.fondo .giudizio button { padding: 4px 8px; font-size: 11px; }
.vuota { padding: 60px 0; text-align: center; font-style: italic; border-bottom: 3px double var(--filetto); }
.colophon { margin-top: 32px; padding-top: 8px; border-top: 1px solid var(--filetto); font-size: 12px; text-align: center;
  letter-spacing: .08em; text-transform: uppercase; color: var(--grigio); }

.strumenti { position: fixed; top: 12px; right: 12px; z-index: 1; }
.strumenti button { font: 600 13px "Source Serif 4", serif; letter-spacing: .08em; text-transform: uppercase;
  background: var(--carta); color: var(--inchiostro); border: 1px solid var(--filetto); padding: 8px 12px; cursor: pointer; }

@media (max-width: 900px) { .colonne { column-count: 2; } .prima { grid-template-columns: minmax(0, 1fr); }
  .sommario { border-left: 0; border-top: 1px solid var(--filetto); padding: 12px 0 0; } }
@media (max-width: 620px) { .colonne, .fondo ol { column-count: 1; } .testata { grid-template-columns: minmax(0, 1fr); }
  .spalle { grid-template-columns: minmax(0, 1fr); }
  .spalla + .spalla { border-left: 0; padding-left: 0; margin-left: 0; border-top: 1px solid #0003; padding-top: 14px; margin-top: 14px; }
  .orecchio { display: none; } .apertura .corpo { text-align: left; } .riga { justify-content: center; } .strumenti { position: static; text-align: right; padding: 8px 16px 0; } }

@page { size: A4; margin: 12mm 11mm; }
@media print {
  body { font-size: 9.5pt; }
  .strumenti, .giudizio, .fondo { display: none !important; }
  .foglio { max-width: none; padding: 0; }
  .testata h1 { font-size: 64pt; }
  .orecchio { display: block; font-size: 7.5pt; }
  .apertura h3 { font-size: 28pt; }
  .apertura .corpo { font-size: 12pt; }
  .prima { grid-template-columns: minmax(0, 2.2fr) minmax(0, 1fr); }
  .spalla h3 { font-size: 14pt; }
  .sommario li { font-size: 10pt; padding: 5px 0; }
  .colonne { column-count: 3; }
  .colonne h3 { font-size: 13pt; }
  .originale, .firma, .occhiello { font-size: 7.5pt; }
  .testatina { break-after: avoid; }
  a:hover { text-decoration: none; }
}

/* sommario diventato "In breve": la fonte sotto il titolo */
.sommario li { grid-template-columns: auto 1fr; }
.sommario li span { grid-column: 2; font: italic 400 13px/1.3 "Source Serif 4", serif; margin-top: -6px; }

/* repository */
.repos { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.repo { padding: 0 18px 18px; border-left: 1px solid #0004; }
.repo:nth-child(4n + 1) { border-left: 0; padding-left: 0; }
.repo:nth-child(n + 5) { border-top: 1px solid #0003; padding-top: 16px; }
.repo h3 { font: 400 19px/1.2 "Playfair Display", serif; margin: 4px 0 8px; overflow-wrap: anywhere; }
.repo h3 b { font-weight: 900; }
.repo .corpo { font-size: 15px; line-height: 1.4; }
.fondo .fonte { font-style: italic; color: var(--grigio); font-size: 13px; }
@media (max-width: 900px) { .repos { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .repo:nth-child(4n + 1) { border-left: 1px solid #0004; padding-left: 18px; }
  .repo:nth-child(2n + 1) { border-left: 0; padding-left: 0; }
  .repo:nth-child(n + 3) { border-top: 1px solid #0003; padding-top: 16px; } }
@media (max-width: 620px) { .repos { grid-template-columns: minmax(0, 1fr); }
  .repo { border-left: 0 !important; padding-left: 0 !important; }
  .repo:nth-child(n + 2) { border-top: 1px solid #0003; padding-top: 16px; } }
@media print { .repos { grid-template-columns: repeat(4, minmax(0, 1fr)); } .repo { break-inside: avoid; }
  .repo h3 { font-size: 11pt; } .repo .corpo { font-size: 8.5pt; } }

/* meteo nell'orecchio destro */
.orecchio.meteo { font-style: normal; font-variant: normal; line-height: 1.4; }
.orecchio.meteo b { font-variant: small-caps; letter-spacing: .05em; font-weight: 600; }

/* il weekend a Roma: quattro colonne di agenda */
.agende { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.agenda { padding: 0 18px; border-left: 1px solid #0004; }
.agenda:first-child { border-left: 0; padding-left: 0; }
.agenda h3 { margin: 0 0 8px; font-size: 20px; }
.agenda ol { margin: 0; padding: 0; list-style: none; }
.agenda li { padding: 8px 0; border-top: 1px solid #0002; font: 400 15px/1.35 "Source Serif 4", serif; }
.agenda li > span { display: block; font-style: italic; color: var(--grigio); font-size: 13px; }
.agenda .giudizio button { padding: 4px 8px; font-size: 11px; }
@media (max-width: 900px) { .agende { grid-template-columns: repeat(2, minmax(0, 1fr)); row-gap: 18px; }
  .agenda:nth-child(3) { border-left: 0; padding-left: 0; } }
@media (max-width: 620px) { .agende { grid-template-columns: minmax(0, 1fr); } .agenda { border-left: 0; padding-left: 0; } }

/* stampa quotidiana: 2-3 fogli. Via ciò che serve solo a schermo, caratteri e spazi più stretti. */
@page { size: A4; margin: 10mm 10mm; }
@media print {
  body { font-size: 8.8pt; line-height: 1.35; }
  .perche, .originale, .repo .firma { display: none !important; }
  .testata h1 { font-size: 46pt; padding: 2px 0 0; }
  .orecchio { font-size: 7pt; padding: 4px 7px; }
  .riga { font-size: 7.5pt; padding: 3px 0; }
  .prima { padding: 10px 0; gap: 16px; }
  .apertura h3 { font-size: 22pt; margin: 2px 0 4px; }
  .apertura .corpo { font-size: 10.5pt; line-height: 1.35; }
  .apertura .corpo::first-letter { font-size: 3em; padding: 3px 5px 0 0; }
  .spalle { margin-top: 10px; padding-top: 8px; }
  .spalla h3 { font-size: 12pt; }
  .sommario h2 { font-size: 9pt; margin: 0 0 6px; }
  .sommario li { font-size: 9pt; padding: 4px 0; gap: 6px; }
  .sommario li span { font-size: 7.5pt; margin-top: -3px; }
  .testatina { margin: 10px 0 8px; font-size: 8.5pt; }
  .colonne { column-gap: 16px; }
  .colonne article { padding-bottom: 7px; margin-bottom: 7px; }
  .colonne h3 { font-size: 11pt; margin: 2px 0; }
  .occhiello, .firma { font-size: 6.8pt; }
  .corpo { margin: 0 0 3px; }
  .repo { padding: 0 10px 8px; }
  .repo:nth-child(n + 5) { padding-top: 8px; }
  .repo h3 { font-size: 9.5pt; margin: 2px 0 3px; }
  .repo .corpo { font-size: 8pt; line-height: 1.3; }
  .agenda { padding: 0 10px; }
  .agenda h3 { font-size: 10.5pt; margin-bottom: 4px; }
  .agenda li { font-size: 8.3pt; padding: 3px 0; }
  .agenda li > span { font-size: 6.8pt; }
  .colophon { margin-top: 10px; font-size: 6.5pt; }
}
"""

JS = """
if (location.protocol === "file:") document.documentElement.classList.add("statico");
document.addEventListener("click", async (ev) => {
  const b = ev.target.closest(".giudizio button");
  if (!b) return;
  const box = b.parentElement, g = b.getAttribute("aria-pressed") === "true" ? 0 : +b.dataset.g;
  const r = await fetch("/giudizio", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: box.dataset.id, g }) });
  if (r.ok) box.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(+x.dataset.g === g)));
});
"""
