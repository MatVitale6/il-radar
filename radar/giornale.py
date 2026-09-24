"""Impagina un'edizione come prima pagina di un quotidiano, in bianco e nero e stampabile."""
import datetime as dt
import re
from html import escape

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]
SEZIONI = {"ai": "Intelligenza artificiale", "sicurezza": "Sicurezza informatica"}


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
    return " ".join(re.split(r"(?<=[.!?])\s+", s.strip())[:2])


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
    return f"""
<article class="{classe}" id="{escape(r['id'])}">
  <p class="occhiello">{SEZIONI[r['sezione']]} · rilevanza {voto(r)}/10</p>
  <h3><a href="{escape(r['url'])}">{escape(titolo)}</a></h3>
  <p class="originale">{escape(r['titolo'])}</p>
  <p class="corpo">{escape(breve(r['riassunto']))}</p>
  <p class="perche"><span>Perché è qui.</span> {escape(r['parole'])}</p>
  <p class="firma">{escape(autori(r['autori']))} — <a href="{escape(r['url'])}">{escape(r['fonte'])}</a></p>
  {pulsanti(r)}
</article>"""


def pagina(con, data, regole):
    q = lambda sql, *a: con.execute(sql, (data, *a)).fetchall()
    pubblicati = q("SELECT * FROM elementi WHERE visto_il=? AND riassunto IS NOT NULL ORDER BY punti DESC")
    scartati = q("SELECT * FROM elementi WHERE visto_il=? AND riassunto IS NULL AND punti>0 ORDER BY punti DESC LIMIT ?",
                 regole["fondo"])
    letti = q("SELECT COUNT(*) FROM elementi WHERE visto_il=?")[0][0]
    numero = con.execute("SELECT COUNT(DISTINCT visto_il) FROM elementi WHERE visto_il<=? AND riassunto IS NOT NULL",
                         (data,)).fetchone()[0] or 1
    primo = con.execute("SELECT MIN(visto_il) FROM elementi").fetchone()[0] or data
    anno = romano(int(data[:4]) - int(primo[:4]) + 1)
    d = dt.date.fromisoformat(data)
    giorno = f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]} {d.year}"

    if pubblicati:
        apertura, spalle, resto = pubblicati[0], pubblicati[1:3], pubblicati[3:]
        sommario = "".join(f'<li><a href="#{escape(r["id"])}">{escape(r["titolo_it"] or r["titolo"])}</a>'
                           f'<span>{voto(r)}</span></li>' for r in pubblicati[1:]) or "<li>Nient'altro oggi.</li>"
        prima = f"""
<section class="prima">
  <div class="principale">
    {articolo(apertura, "apertura")}
    <div class="spalle">{"".join(articolo(r, "spalla") for r in spalle)}</div>
  </div>
  <aside class="sommario"><h2>In questo numero</h2><ol>{sommario}</ol></aside>
</section>"""
    else:
        resto, prima = [], '<section class="vuota"><p>Nessuna notizia sopra la soglia oggi.</p></section>'

    sezioni = ""
    for chiave, nome in SEZIONI.items():
        pezzi = [r for r in resto if r["sezione"] == chiave]
        if pezzi:
            sezioni += (f'<section class="sezione"><h2 class="testatina"><span>{nome}</span></h2>'
                        f'<div class="colonne">{"".join(articolo(r) for r in pezzi)}</div></section>')

    fondo = "".join(f'<li><span class="voto">{voto(r)}</span> <a href="{escape(r["url"])}">{escape(r["titolo"])}</a>'
                    f'{pulsanti(r)}</li>' for r in scartati)
    fondo = (f'<section class="fondo"><h2 class="testatina"><span>Rimasti fuori</span></h2>'
             f'<p class="nota">Toccano il tuo profilo ma sono sotto {regole["soglia"]}/10 o oltre i primi '
             f'{regole["massimo"]}. Se uno ti interessa, segnalalo: serve a tarare le parole chiave.</p><ol>{fondo}</ol></section>') if scartati else ""

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
  <div class="orecchio">Letti {letti}<br>Pubblicati {len(pubblicati)}</div>
  <h1>Il Radar</h1>
  <div class="orecchio destra">Tutte le notizie<br>che ti riguardano</div>
  <p class="riga"><span>Anno {anno} · N. {numero}</span><span>{giorno}</span><span>Edizione del mattino</span></p>
</header>
{prima}
{sezioni}
{fondo}
<footer class="colophon">Scelti dalle parole chiave del profilo · riassunti in locale da MiniCPM4.1 · nessun testo inviato a servizi esterni · fonte: arXiv (cs.AI, cs.LG, cs.CR)</footer>
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
