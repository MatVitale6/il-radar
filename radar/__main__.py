"""Il Radar.

    py -m radar giro      raccoglie, seleziona, fa tradurre/riassumere a MiniCPM e impagina l'edizione di oggi
    py -m radar serve     tiene acceso il giornale su http://127.0.0.1:8765 (all'avvio del PC, senza finestre)
    py -m radar apri      apre il giornale nel browser, accendendo il server se serve (l'icona sul desktop)
"""
import datetime as dt
import json
import math
import re
import sys
import time
import tomllib
from functools import cache
from pathlib import Path

from . import db, fonti, giornale, llm

RADICE = Path(__file__).resolve().parent.parent
PROFILO = tomllib.loads((RADICE / "profilo.toml").read_text("utf-8"))
RUBRICHE_NOTIZIE = ("norme", "sicurezza", "tecnologia")

# Al modello chiediamo solo di tradurre e riassumere: nei test sul giudizio (pertinente sì/no,
# campo di applicazione) sbagliava troppo. La selezione la fanno le parole chiave.
SISTEMA = """Sei un redattore italiano. Ricevi titolo e testo (in inglese) di una notizia o di un articolo
scientifico. Scrivi in italiano corretto, usando SOLO le informazioni ricevute. Rispondi esattamente con due righe:
TITOLO: titolo di giornale in italiano, massimo 12 parole, fedele all'originale
RIASSUNTO: una o due frasi in italiano, massimo 40 parole, su cosa è successo, in concreto"""
SOLO_TITOLO = """Sei un redattore italiano. Traduci in italiano questo titolo di giornale inglese,
fedelmente, in stile giornalistico, massimo 12 parole. Nomi propri e di prodotti restano come sono.
Rispondi solo con il titolo tradotto."""
DESCRIZIONE = """Sei un redattore italiano. Traduci in italiano la descrizione di questo progetto software,
in una frase di massimo 25 parole. Nomi propri e termini tecnici restano come sono. Rispondi solo con la traduzione."""


def _riga(risposta, etichetta):
    m = re.search(rf"^\W*{etichetta}\W*:\s*(.+)$", risposta, re.IGNORECASE | re.MULTILINE)
    return _pulita(m[1]) if m else ""


def _pulita(s):
    return s.strip().strip('"«»“”*').strip()


def _prima_riga(s):
    return _pulita(s.splitlines()[0]) if s else ""


CINESE = re.compile(r"[⺀-鿿가-힯＀-￯]")


def _in_italiano(sistema, testo):
    """MiniCPM è addestrato molto sul cinese e ogni tanto ci ricade ("la trasparenza dei数据中心"):
    si riprova una volta chiedendolo esplicitamente, poi si rinuncia (chi chiama tiene l'originale)."""
    risposta = llm.scrivi(sistema, testo)
    if CINESE.search(risposta):
        risposta = llm.scrivi(sistema + "\nScrivi solo in italiano, con l'alfabeto latino: nessun carattere cinese.", testo)
    return "" if CINESE.search(risposta) else risposta


# ── punteggio ─────────────────────────────────────────────────────────────────

@cache
def _regex(parola):
    radice = re.escape(parola.rstrip("*"))
    coda = r"\w*" if parola.endswith("*") else r"(?:s|es)?"
    # solo le sigle tutte maiuscole (AI, IA, EU) contano solo scritte così: "Weekend a Roma" = "weekend a roma"
    return re.compile(r"\b" + radice + coda + r"\b", 0 if parola.isupper() else re.IGNORECASE)


def trovate(testo, tabella):
    return {p: peso for p, peso in tabella.items() if _regex(p).search(testo)}


def _elenco(*gruppi):
    tutte = {}
    for g in gruppi:
        tutte |= {p: w for p, w in g.items() if w > 0}
    return ", ".join(sorted(tutte, key=lambda p: -tutte[p])[:6])


def valuta_notizia(e):
    cfg, testo = PROFILO["notizie"], e["titolo"] + " \n " + e["testo"]
    gruppi = {r: trovate(testo, cfg[r]) for r in RUBRICHE_NOTIZIE}
    somme = {r: sum(g.values()) for r, g in gruppi.items()}
    if somme["tecnologia"] + somme["sicurezza"] <= 0:
        return 0, "", None                     # niente digitale: fuori, anche se parla di leggi
    punti = sum(somme.values()) + sum(trovate(testo, cfg["giu"]).values()) + e["peso"]
    return punti, _elenco(*gruppi.values()), max(somme, key=somme.get)


def valuta_repo(e):
    extra = json.loads(e["extra"])
    testo = " ".join([e["titolo"].replace("/", " "), e["testo"], " ".join(extra["temi"])])
    parole = trovate(testo.replace("-", " "), PROFILO["ricerca"]["parole"])
    punti = int(math.log2(extra["stelle"] + 1)) + sum(parole.values())
    return punti, _elenco(parole) or ", ".join(extra["temi"][:4]), None


def valuta_articolo(e):
    parole = trovate(e["titolo"] + " " + e["testo"], PROFILO["ricerca"]["parole"])
    return sum(parole.values()), _elenco(parole), e["rubrica"]


# ── raccolta ──────────────────────────────────────────────────────────────────

VUOTE = set("della delle degli dello nella nelle negli sulla sulle dopo anche come hanno sono essere pure sotto "
            "ecco perché questo questa with from that this into over after about their what have will more than "
            "they your says said just".split())


def _impronta(titolo):
    # prime 5 lettere: "governo"/"government", "attacco"/"attack" diventano uguali tra italiano e inglese
    return {w[:5] for w in re.findall(r"\w{4,}", titolo.lower()) if w not in VUOTE}


def _stessa_storia(a, b):
    comuni = len(a & b)
    return comuni >= 3 and comuni / max(1, min(len(a), len(b))) >= 0.6


def _inserisci(con, e, oggi, punti, parole, rubrica):
    cur = con.execute(
        "INSERT OR IGNORE INTO elementi (id, fonte, sezione, rubrica, titolo, url, testo, autori, lingua, uscito,"
        " extra, visto_il, punti, parole) VALUES (:id, :fonte, :sezione, :rubrica, :titolo, :url, :testo, :autori,"
        " :lingua, :uscito, :extra, :oggi, :punti, :parole)",
        e | {"oggi": oggi, "punti": punti, "parole": parole, "rubrica": rubrica})
    return cur.rowcount


def raccogli_notizie(con, oggi):
    cfg = PROFILO["notizie"]
    limite = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=cfg["ore"])
    tre_giorni = (dt.date.fromisoformat(oggi) - dt.timedelta(days=3)).isoformat()
    # storie già viste (anche nei giorni scorsi): la stessa notizia da un'altra testata non rientra
    storie = [(r["id"], r["visto_il"], _impronta(r["titolo"])) for r in con.execute(
        "SELECT id, visto_il, titolo FROM elementi WHERE sezione='notizie' AND visto_il >= ?", (tre_giorni,))]
    nuove = doppie = 0
    for nome, url, lingua, peso in fonti.NOTIZIE:
        try:
            voci = list(fonti.feed(nome, url, lingua, peso))
        except Exception as err:                      # una fonte giù non ferma il giornale
            print(f"  fonte saltata: {nome} ({err})", flush=True)
            continue
        for e in voci:
            if e["uscito"] and dt.datetime.fromisoformat(e["uscito"]) < limite:
                continue
            if con.execute("SELECT 1 FROM elementi WHERE id=?", (e["id"],)).fetchone():
                continue
            impronta = _impronta(e["titolo"])
            gemella = next((s for s in storie if _stessa_storia(s[2], impronta)), None)
            if gemella:
                doppie += 1
                storie.append((gemella[0], gemella[1], impronta))   # le varianti allargano la storia
                # la copia resta in archivio (nascosta), così un secondo giro non la riconta
                _inserisci(con, e | {"sezione": "doppione", "extra": json.dumps({"di": gemella[0]})}, oggi, 0, "", None)
                if gemella[1] == oggi:
                    # bonus per le prime tre testate in più, poi solo il conteggio
                    con.execute("UPDATE elementi SET copertura = copertura + 1,"
                                " punti = punti + CASE WHEN copertura < 4 THEN ? ELSE 0 END WHERE id = ?",
                                (cfg["copertura"], gemella[0]))
                continue
            punti, parole, rubrica = valuta_notizia(e)
            nuove += _inserisci(con, e, oggi, punti, parole, rubrica)
            storie.append((e["id"], oggi, impronta))
    con.commit()
    print(f"notizie: {nuove} nuove, {doppie} doppioni riuniti", flush=True)


def raccogli_repo(con, oggi):
    nuovi = 0
    try:
        for e in fonti.github(PROFILO["github"]["temi"], PROFILO["github"]["giorni"]):
            punti, parole, _ = valuta_repo(e)
            nuovi += _inserisci(con, e, oggi, punti, parole, None)
    except Exception as err:
        print(f"  GitHub saltato ({err})", flush=True)
    con.commit()
    print(f"repository: {nuovi} nuovi", flush=True)


def raccogli_ricerca(con, oggi):
    nuovi = 0
    try:
        for e in fonti.arxiv():
            punti, parole, rubrica = valuta_articolo(e)
            nuovi += _inserisci(con, e, oggi, punti, parole, rubrica)
    except Exception as err:
        print(f"  arXiv saltato ({err})", flush=True)
    con.commit()
    print(f"ricerca: {nuovi} nuovi", flush=True)


def raccogli_meteo(con, oggi):
    m = PROFILO["meteo"]
    try:
        dati = fonti.meteo(m["lat"], m["lon"]) | {"citta": m["citta"]}
    except Exception as err:
        print(f"  meteo saltato ({err})", flush=True)
        return
    con.execute("INSERT OR REPLACE INTO meteo VALUES (?, ?)", (oggi, json.dumps(dati, ensure_ascii=False)))
    con.commit()
    print(f"meteo: {dati}", flush=True)


# ── weekend a Roma ────────────────────────────────────────────────────────────

RUBRICHE_WEEKEND = ("guide", "musica", "sagre", "mostre")
MESI_RE = "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
GIORNI_RE = "lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica"


def sabato_del(giorno):
    return giorno - dt.timedelta(days=giorno.weekday() - 5)       # sabato: se stesso; domenica: il giorno prima


def _giorni_citati(titolo):
    """(giorno, mese) scritti nel titolo: '25-26-27 settembre', 'dal 18 al 20 settembre'; 'sabato 19' ha mese None."""
    citati = set()
    for serie, mese in re.findall(rf"((?:\d{{1,2}}\s*(?:-|–|/|,|e|al)\s*)*\d{{1,2}})\s+({MESI_RE})", titolo, re.I):
        numero_mese = MESI_RE.split("|").index(mese.lower()) + 1
        citati |= {(int(n), numero_mese) for n in re.findall(r"\d{1,2}", serie)}
    citati |= {(int(n), None) for n in re.findall(rf"(?:{GIORNI_RE})\s+(\d{{1,2}})\b", titolo, re.I)}
    return citati


def valuta_evento(e, sabato):
    cfg, testo = PROFILO["weekend"], e["titolo"] + " \n " + e["testo"]
    locale = e["fonte"] in cfg["fonti_locali"]
    if not locale and not any(re.search(rf"\b{re.escape(l)}\b", testo) for l in cfg["luoghi"]):
        return 0, "", None                                         # non è a Roma o dintorni
    citati = _giorni_citati(e["titolo"])
    fine_settimana = (sabato, sabato + dt.timedelta(days=1))
    if citati and not any(g == w.day and m in (None, w.month) for g, m in citati for w in fine_settimana):
        return 0, "", None                                         # parla di un altro giorno (o mese)
    gruppi = {r: trovate(testo, cfg[r]) for r in RUBRICHE_WEEKEND}
    somme = {r: sum(g.values()) for r, g in gruppi.items()}
    punti = sum(somme.values()) + e["peso"] + (3 if citati else 0)
    # una guida che nomina anche concerti resta una guida; altrimenti vince il gruppo con più punti
    rubrica = "guide" if somme["guide"] >= 4 else max(somme, key=somme.get)
    return punti, _elenco(*gruppi.values()), rubrica


def raccogli_weekend(con, oggi):
    cfg, sabato = PROFILO["weekend"], sabato_del(dt.date.fromisoformat(oggi))
    limite = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=cfg["ore"])
    storie = [(r["id"], _impronta(r["titolo"])) for r in con.execute(
        "SELECT id, titolo FROM elementi WHERE sezione='weekend' AND visto_il >= ?", (sabato.isoformat(),))]
    nuovi = 0
    for nome, url, lingua, peso in fonti.EVENTI:
        try:
            voci = list(fonti.feed(nome, url, lingua, peso))
        except Exception as err:
            print(f"  fonte eventi saltata: {nome} ({err})", flush=True)
            continue
        for e in voci:
            e["sezione"] = "weekend"
            if e["uscito"] and dt.datetime.fromisoformat(e["uscito"]) < limite:
                continue
            impronta = _impronta(e["titolo"])
            if any(_stessa_storia(s[1], impronta) for s in storie):
                continue
            punti, parole, rubrica = valuta_evento(e, sabato)
            nuovi += _inserisci(con, e, oggi, punti, parole, rubrica)
            storie.append((e["id"], impronta))
    con.commit()
    print(f"weekend: {nuovi} eventi nuovi", flush=True)


def _scegli_weekend(con, oggi):
    """Come per le notizie; la domenica conta anche ciò che è già uscito il sabato."""
    cfg, sabato = PROFILO["weekend"], sabato_del(dt.date.fromisoformat(oggi)).isoformat()
    fatte = con.execute("SELECT titolo FROM elementi WHERE sezione='weekend' AND ruolo IS NOT NULL AND visto_il>=?",
                        (sabato,)).fetchall()
    scelte, posti = [_impronta(r["titolo"]) for r in fatte], cfg["massimo"] - len(fatte)
    for r in con.execute("SELECT id, titolo FROM elementi WHERE visto_il=? AND sezione='weekend' AND ruolo IS NULL"
                         " AND punti>=? ORDER BY punti DESC", (oggi, cfg["soglia"])).fetchall():
        if posti <= 0:
            break
        impronta = _impronta(r["titolo"])
        if any(_vicina(impronta, s) for s in scelte):
            continue
        posti -= 1
        scelte.append(impronta)
        con.execute("UPDATE elementi SET ruolo='articolo' WHERE id=?", (r["id"],))


# ── scelta e traduzione ──────────────────────────────────────────────────────

def _assegna(con, oggi, sezione, ruolo, quanti, soglia):
    gia = con.execute("SELECT COUNT(*) FROM elementi WHERE visto_il=? AND sezione=? AND ruolo=?",
                      (oggi, sezione, ruolo)).fetchone()[0]
    con.execute(
        "UPDATE elementi SET ruolo=? WHERE id IN (SELECT id FROM elementi WHERE visto_il=? AND sezione=?"
        " AND ruolo IS NULL AND punti>=? ORDER BY punti DESC, copertura DESC LIMIT ?)",
        (ruolo, oggi, sezione, soglia, max(0, quanti - gia)))


def _vicina(a, b):
    """Più larga di _stessa_storia: non la stessa notizia, ma lo stesso filone (sette moratorie di contee USA)."""
    comuni = len(a & b)
    return comuni >= 2 and comuni / max(1, min(len(a), len(b))) >= 0.34


def _scegli_notizie(con, oggi):
    """Dalla più forte in giù, saltando quelle troppo vicine a una già scelta: prima gli articoli, poi le brevi."""
    n = PROFILO["notizie"]
    fatte = con.execute("SELECT titolo, ruolo FROM elementi WHERE visto_il=? AND sezione='notizie' AND ruolo IS NOT NULL",
                        (oggi,)).fetchall()
    scelte = [_impronta(r["titolo"]) for r in fatte]
    posti = {"articolo": n["massimo"] - sum(r["ruolo"] == "articolo" for r in fatte),
             "breve": n["brevi"] - sum(r["ruolo"] == "breve" for r in fatte)}
    for r in con.execute("SELECT id, titolo FROM elementi WHERE visto_il=? AND sezione='notizie' AND ruolo IS NULL"
                         " AND punti>=? ORDER BY punti DESC, copertura DESC", (oggi, n["soglia"])).fetchall():
        ruolo = next((k for k, v in posti.items() if v > 0), None)
        if not ruolo:
            break
        impronta = _impronta(r["titolo"])
        if any(_vicina(impronta, s) for s in scelte):
            continue
        posti[ruolo] -= 1
        scelte.append(impronta)
        con.execute("UPDATE elementi SET ruolo=? WHERE id=?", (ruolo, r["id"]))


def scegli(con, oggi):
    g, r = PROFILO["github"], PROFILO["ricerca"]
    _scegli_notizie(con, oggi)
    _scegli_weekend(con, oggi)
    _assegna(con, oggi, "github", "articolo", g["massimo"], 1)
    _assegna(con, oggi, "ricerca", "articolo", r["massimo"], r["soglia"])
    con.commit()


def traduci(con, oggi):
    righe = con.execute(
        "SELECT * FROM elementi WHERE visto_il=? AND ruolo IS NOT NULL AND riassunto IS NULL ORDER BY"
        " CASE sezione WHEN 'notizie' THEN 0 WHEN 'github' THEN 1 ELSE 2 END, ruolo, punti DESC", (oggi,)).fetchall()
    italiane = [r for r in righe if r["lingua"] == "it"]
    for r in italiane:                                   # già in italiano: niente modello
        con.execute("UPDATE elementi SET titolo_it=?, riassunto=? WHERE id=?",
                    (r["titolo"], giornale.breve(r["testo"]), r["id"]))
    con.commit()
    righe = [r for r in righe if r["lingua"] != "it"]
    print(f"da tradurre: {len(righe)} (italiane pronte: {len(italiane)})", flush=True)
    if not righe:
        return
    with llm.ollama():
        for i, r in enumerate(righe, 1):
            t0 = time.time()
            if r["sezione"] == "github":
                titolo = r["titolo"]
                riassunto = (_prima_riga(_in_italiano(DESCRIZIONE, r["testo"])) or r["testo"]) if r["testo"] else ""
            elif r["ruolo"] == "breve" or not r["testo"]:
                titolo, riassunto = _prima_riga(_in_italiano(SOLO_TITOLO, r["titolo"])), ""
            else:
                risposta = _in_italiano(SISTEMA, f"Titolo: {r['titolo']}\n\nTesto: {r['testo']}")
                titolo, riassunto = _riga(risposta, "titolo"), _riga(risposta, "riassunto")
                if not riassunto:
                    # risposta fuori formato: esce comunque, col testo originale
                    print(f"     risposta fuori formato, resta in inglese: {risposta[:80]!r}", flush=True)
                    riassunto = giornale.breve(r["testo"])
            con.execute("UPDATE elementi SET titolo_it=?, riassunto=? WHERE id=?",
                        (titolo or None, riassunto, r["id"]))
            con.commit()
            print(f"  {i:>2}/{len(righe)} {r['sezione']:<8} {time.time() - t0:4.1f}s  {r['titolo'][:60]}", flush=True)


def impagina(con, oggi):
    uscita = RADICE / "edizioni" / f"{oggi}.html"
    uscita.parent.mkdir(exist_ok=True)
    uscita.write_text(giornale.pagina(con, oggi, PROFILO), "utf-8")
    print(f"edizione: {uscita}", flush=True)


def main():
    if sys.stdout:                  # il log passa dalla console cp1252: senza questo un titolo con "ə" ferma il giro
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    comando = sys.argv[1] if len(sys.argv) > 1 else "giro"
    con = db.apri()
    oggi = dt.date.today().isoformat()
    if comando == "giro":
        print(f"── giro del {dt.datetime.now():%Y-%m-%d %H:%M}", flush=True)
        raccogli_meteo(con, oggi)
        raccogli_notizie(con, oggi)
        raccogli_repo(con, oggi)
        if dt.date.today().weekday() >= 5:     # sabato e domenica: il weekend a Roma al posto della ricerca
            raccogli_weekend(con, oggi)
        else:
            raccogli_ricerca(con, oggi)
        scegli(con, oggi)
        traduci(con, oggi)
        impagina(con, oggi)
    elif comando in ("serve", "apri"):
        from . import server
        server.avvia(con, PROFILO, apri=comando == "apri")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
