"""Il Radar.

    py -m radar giro      raccoglie, seleziona, fa tradurre/riassumere a MiniCPM e impagina l'edizione di oggi
    py -m radar serve     tiene acceso il giornale su http://127.0.0.1:8765 (all'avvio del PC, senza finestre)
    py -m radar apri      apre il giornale nel browser, accendendo il server se serve (l'icona sul desktop)
"""
import datetime as dt
import json
import re
import subprocess
import sys
import time
import tomllib
from functools import cache
from pathlib import Path

from . import db, fonti, giornale, llm

RADICE = Path(__file__).resolve().parent.parent
PROFILO = tomllib.loads((RADICE / "profilo.toml").read_text("utf-8"))
RUBRICHE_NOTIZIE = ("norme", "sicurezza", "tecnologia")

# MiniCPM riassume in inglese i README dei repository; a tradurre ci pensa TranslateGemma (che traduce molto meglio:
# MiniCPM scriveva "Data centeri sono blind boxes", e ogni tanto in svedese o in cinese). Nei test MiniCPM sul
# giudizio (pertinente sì/no, campo di applicazione) sbagliava troppo: la selezione la fanno le parole chiave.
SPIEGA_EN = """You are a technical editor. You receive the name, description and start of the README of a software
project. In one or two plain sentences (35 words maximum) explain what it is and what it is for, for a software
developer, using ONLY the information given. Reply with the explanation only."""

CINESE = re.compile(r"[⺀-鿿가-힯＀-￯]")
RIPETUTA = re.compile(r"(\b\S+)(?:\s+\1\b){3,}", re.I)      # la stessa parola 4 volte di fila: il modello è in ciclo


def _pulita(s):
    return s.strip().strip('"«»“”*').strip()


def _affidabile(originale, tradotto):
    """Una traduzione sospetta si scarta e resta l'inglese: vuota, con caratteri cinesi, in ciclo, o lunga/corta
    in modo strano (l'italiano è più lungo dell'inglese, ma non di tre volte)."""
    if not tradotto or CINESE.search(tradotto) or RIPETUTA.search(tradotto):
        return False
    return 0.5 <= len(tradotto) / max(1, len(originale)) <= 2.6


def _tradotta(originale, num_predict):
    """TranslateGemma con controlli; un secondo tentativo con un po' di casualità; '' se non è affidabile."""
    for temperatura in (0, 0.4):
        risposta = llm.traduci(originale, num_predict, temperatura)
        if _affidabile(originale, risposta):
            return risposta
    return ""


def _titolo_it(titolo):
    """Traduce un titolo: il traduttore risponde con una frase, quindi via il punto finale e le virgolette."""
    t = _tradotta(titolo, 110)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 1 and t[0] in '"«“' and t[-1] in '"»”':
        t = t[1:-1]
    return t.rstrip(". ") if not t.endswith("...") else t


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


SPORT_DI = {"tennis": ("tennis", "ATP", "WTA"), "pallavolo": ("pallavolo", "volley", "Superlega"),
            "ciclismo": ("ciclismo", "granfondo", "Giro d'Italia", "Tour de France", "Vuelta")}
GARE_ROMA = {"podistic*": 1, "corsa": 1, "maratona": 1, "mezza maratona": 1, "granfondo": 1, "10 km": 1}


def valuta_sport(e):
    cfg, testo = PROFILO["sport"], e["titolo"] + " \n " + e["testo"]
    discipline = trovate(testo, cfg["discipline"])
    if not discipline:
        return 0, "", None                                      # non è uno degli sport che segui
    # importanza e italiani dal solo titolo: un'intervista che nel testo cita "oro, Mondiali, Jacobs" non è un record
    importanza = trovate(e["titolo"], cfg["importanza"])
    italiani = [n for n in cfg["italiani"] if re.search(rf"\b{re.escape(n)}\b", e["titolo"])]
    punti = (sum(discipline.values()) + sum(importanza.values()) + 3 * bool(italiani) + e["peso"]
             + sum(trovate(testo, cfg["giu"]).values()))
    if re.search(r"\bRoma\b", e["titolo"]) and trovate(testo, GARE_ROMA):
        rubrica = "roma"                                        # gare amatoriali a Roma
    else:
        rubrica = next((s for s, chiavi in SPORT_DI.items() if any(k in discipline for k in chiavi)), "atletica")
    return punti, _elenco(importanza, discipline, dict.fromkeys(italiani, 3)), rubrica


def valuta_gaming(e):
    cfg, testo = PROFILO["gaming"], e["titolo"] + " \n " + e["testo"]
    parole = trovate(testo, cfg["parole"])
    # tutte le fonti sono di gaming: ogni voce parte da 1; le parole la spingono su (uscite, annunci, recensioni,
    # industria, sviluppo) o giù (offerte, guide, trucchi, cinema e serie tv)
    return 1 + sum(parole.values()) + e["peso"], _elenco(parole), None


PARTICIPIO = re.compile(r"\b\w{3,}(?:at|it|ut)[oaie]\b", re.I)          # "approvato", "perquisiti", "intitolato"
DICHIARAZIONE = re.compile(r"^[^,:'\"«“]{2,40}[,:]\s*['\"«“‘]")        # "Meloni, 'studenti...'": un'opinione


def valuta_attualita(e, zona):
    """Solo fatti avvenuti: nel titolo un verbo di fatto compiuto (o un participio passato), nessuna parola di
    ipotesi, niente domande, niente titoli che sono solo una dichiarazione tra virgolette."""
    cfg, titolo = PROFILO["attualita"], e["titolo"]
    uno = lambda parole: dict.fromkeys(parole, 1)
    if zona == "auto":
        zona = "estero" if any(re.search(r"mondo|ester", c, re.I) for c in e["categorie"]) else "italia"
    if trovate(titolo + " " + e["testo"], uno(cfg["escludi"])) or any(
            re.search(r"sport|calcio", c, re.I) for c in e["categorie"]):
        return 0, "", zona
    certe = list(trovate(titolo, uno(cfg["certo"]))) + PARTICIPIO.findall(titolo)
    if e["fonte"] != "ISTAT" and ("?" in titolo or trovate(titolo, uno(cfg["incerto"]))
                                  or DICHIARAZIONE.search(titolo) or not certe):
        return 0, "", zona                                      # ipotesi, discussioni, domande, opinioni: fuori
    return min(len(certe), 3) + e["peso"], ", ".join(certe[:4]) or "report", zona


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


def _crescita(con, r, oggi):
    """Stelle guadagnate in 7 giorni: misurate sullo storico, se c'è almeno un giorno prima di oggi;
    altrimenti stimate dalla media di stelle al giorno dalla nascita del repository."""
    giorno = dt.date.fromisoformat(oggi)
    prima = con.execute("SELECT data, stelle FROM stelle WHERE repo=? AND data>=? AND data<? ORDER BY data LIMIT 1",
                        (r["nome"], (giorno - dt.timedelta(days=7)).isoformat(), oggi)).fetchone()
    if prima:
        giorni = (giorno - dt.date.fromisoformat(prima[0])).days
        return round((r["stelle"] - prima[1]) * 7 / giorni), True
    return round(r["stelle"] * 7 / max(1, (giorno - dt.date.fromisoformat(r["creato"])).days)), False


def raccogli_repo(con, oggi):
    g, visti = PROFILO["github"], 0
    try:
        for r in fonti.github_forti(g["temi"], g["stelle_min"], g["attivi_giorni"]):
            con.execute("INSERT OR REPLACE INTO stelle VALUES (?, ?, ?)", (r["nome"], oggi, r["stelle"]))
            settimana, misurata = _crescita(con, r, oggi)
            e = {"id": f"github:{r['nome'].lower()}:{oggi}", "fonte": "GitHub", "sezione": "github",
                 "titolo": r["nome"], "url": r["url"], "testo": r["descrizione"], "autori": r["nome"].split("/")[0],
                 "lingua": "en", "uscito": r["creato"],
                 "extra": json.dumps({"stelle": r["stelle"], "linguaggio": r["linguaggio"], "temi": r["temi"],
                                      "settimana": settimana, "misurata": misurata})}
            visti += _inserisci(con, e, oggi, settimana, r["tema"], r["tema"])   # un repo, un giorno, un tema
    except Exception as err:
        print(f"  GitHub saltato ({err})", flush=True)
    con.commit()
    print(f"repository osservati oggi: {visti}", flush=True)


def _raccogli_feed(con, oggi, sezione, elenco, ore, valuta):
    """Per sport e attualità: come le notizie, con i doppioni riuniti per titolo (e un punto per testata in più)."""
    limite = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=ore)
    tre_giorni = (dt.date.fromisoformat(oggi) - dt.timedelta(days=3)).isoformat()
    storie = [(r["id"], r["visto_il"], _impronta(r["titolo"])) for r in con.execute(
        "SELECT id, visto_il, titolo FROM elementi WHERE sezione=? AND visto_il >= ?", (sezione, tre_giorni))]
    nuove = 0
    for nome, url, lingua, peso, *zona in elenco:
        try:
            voci = list(fonti.feed(nome, url, lingua, peso))
        except Exception as err:
            print(f"  fonte saltata: {nome} ({err})", flush=True)
            continue
        for e in voci:
            e["sezione"] = sezione
            if (e["uscito"] and dt.datetime.fromisoformat(e["uscito"]) < limite) or \
                    con.execute("SELECT 1 FROM elementi WHERE id=?", (e["id"],)).fetchone():
                continue
            impronta = _impronta(e["titolo"])
            gemella = next((s for s in storie if _stessa_storia(s[2], impronta)), None)
            if gemella:
                _inserisci(con, e | {"sezione": "doppione", "extra": json.dumps({"di": gemella[0]})}, oggi, 0, "", None)
                if gemella[1] == oggi:
                    con.execute("UPDATE elementi SET copertura = copertura + 1, punti = punti + 1 WHERE id = ?",
                                (gemella[0],))
                continue
            punti, parole, rubrica = valuta(e, *zona)
            nuove += _inserisci(con, e, oggi, punti, parole, rubrica)
            storie.append((e["id"], oggi, impronta))
    con.commit()
    print(f"{sezione}: {nuove} nuove", flush=True)


def raccogli_sport(con, oggi):
    _raccogli_feed(con, oggi, "sport", fonti.SPORT, PROFILO["sport"]["ore"], valuta_sport)


def raccogli_gaming(con, oggi):
    _raccogli_feed(con, oggi, "gaming", fonti.GAMING, PROFILO["gaming"]["ore"], valuta_gaming)


def raccogli_attualita(con, oggi):
    _raccogli_feed(con, oggi, "attualita", fonti.ATTUALITA, PROFILO["attualita"]["ore"], valuta_attualita)


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


CON_TESTO = 80      # caratteri minimi di testo per uscire per esteso: senza testo non c'è niente da riassumere


def _scegli(con, oggi, sezione, piani, rubrica=None):
    """Dalla più forte in giù, saltando quelle troppo vicine a una già scelta. `piani`: [(ruolo, quanti, soglia,
    serve_testo)] in ordine: una voce va nel primo piano con posto, punti sufficienti e (se serve) un testo.
    Così le notizie di Google News, che hanno solo il titolo, finiscono tra le brevi."""
    filtro, argomenti = ("AND rubrica=?", (rubrica,)) if rubrica else ("", ())
    fatte = con.execute(f"SELECT titolo, ruolo FROM elementi WHERE visto_il=? AND sezione=? {filtro}"
                        " AND ruolo IS NOT NULL", (oggi, sezione, *argomenti)).fetchall()
    scelte = [_impronta(r["titolo"]) for r in fatte]
    posti = {ruolo: quanti - sum(r["ruolo"] == ruolo for r in fatte) for ruolo, quanti, _, _ in piani}
    for r in con.execute(f"SELECT id, titolo, testo, punti FROM elementi WHERE visto_il=? AND sezione=? {filtro}"
                         " AND ruolo IS NULL AND punti>0 ORDER BY punti DESC, copertura DESC, uscito DESC",
                         (oggi, sezione, *argomenti)).fetchall():
        ruolo = next((ruolo for ruolo, _, soglia, serve_testo in piani if posti[ruolo] > 0 and r["punti"] >= soglia
                      and (not serve_testo or len(r["testo"] or "") >= CON_TESTO)), None)
        if not ruolo:
            continue
        impronta = _impronta(r["titolo"])
        if any(_vicina(impronta, s) for s in scelte):
            continue
        posti[ruolo] -= 1
        scelte.append(impronta)
        con.execute("UPDATE elementi SET ruolo=? WHERE id=?", (ruolo, r["id"]))


def _scegli_repo(con, oggi):
    """I più forti, al massimo `per_tema` per tema, saltando quelli già usciti negli ultimi `raffreddamento`
    giorni: senza uno storico di stelle abbastanza lungo, i grandi repository storici hanno sempre lo stesso
    punteggio (media dalla nascita) e altrimenti uscirebbero ogni giorno."""
    g = PROFILO["github"]
    if con.execute("SELECT 1 FROM elementi WHERE visto_il=? AND sezione='github' AND ruolo IS NOT NULL",
                   (oggi,)).fetchone():
        return
    recenti = {r[0] for r in con.execute(
        "SELECT titolo FROM elementi WHERE sezione='github' AND ruolo='articolo' AND visto_il>=? AND visto_il<?",
        ((dt.date.fromisoformat(oggi) - dt.timedelta(days=g["raffreddamento"])).isoformat(), oggi))}
    per_tema, presi = {}, 0
    for r in con.execute("SELECT id, titolo, rubrica FROM elementi WHERE visto_il=? AND sezione='github'"
                         " ORDER BY punti DESC", (oggi,)).fetchall():
        if presi >= g["massimo"]:
            break
        if r["titolo"] in recenti or per_tema.get(r["rubrica"], 0) >= g["per_tema"]:
            continue
        per_tema[r["rubrica"]] = per_tema.get(r["rubrica"], 0) + 1
        presi += 1
        con.execute("UPDATE elementi SET ruolo='articolo' WHERE id=?", (r["id"],))


def scegli(con, oggi):
    n, s, a, r = PROFILO["notizie"], PROFILO["sport"], PROFILO["attualita"], PROFILO["ricerca"]
    _scegli(con, oggi, "notizie", [("articolo", n["massimo"], n["soglia"], True), ("breve", n["brevi"], n["soglia"], False)])
    _scegli_repo(con, oggi)
    _scegli(con, oggi, "sport", [("articolo", s["articoli"], s["soglia_articolo"], True), ("breve", s["brevi"], s["soglia"], False)])
    gm = PROFILO["gaming"]
    _scegli(con, oggi, "gaming", [("articolo", gm["articoli"], gm["soglia_articolo"], True), ("breve", gm["brevi"], gm["soglia"], False)])
    for zona in ("italia", "estero"):
        _scegli(con, oggi, "attualita", [("breve", a["per_zona"], 1, False)], rubrica=zona)
    _scegli_weekend(con, oggi)
    _assegna(con, oggi, "ricerca", "breve", r["massimo"], r["soglia"])
    con.commit()


def _spiegazione_en(r):
    """MiniCPM: due o tre frasi in inglese su cos'è il repository, dal README (poi si traducono)."""
    try:
        inizio = fonti.readme(r["titolo"])
    except Exception:                                   # niente README: basta la descrizione
        inizio = ""
    if not (inizio or r["testo"]):
        return ""
    risposta = llm.scrivi(SPIEGA_EN, f"Project: {r['titolo']}\nDescription: {r['testo']}\n\nREADME: {inizio}")
    return "" if CINESE.search(risposta) or RIPETUTA.search(risposta) else " ".join(_pulita(risposta).split())


def traduci(con, oggi):
    righe = con.execute(
        "SELECT * FROM elementi WHERE visto_il=? AND ruolo IS NOT NULL AND riassunto IS NULL ORDER BY"
        " CASE sezione WHEN 'notizie' THEN 0 WHEN 'github' THEN 1 ELSE 2 END, ruolo, punti DESC", (oggi,)).fetchall()
    italiane = [r for r in righe if r["lingua"] == "it"]
    for r in italiane:                                   # già in italiano: niente modello
        con.execute("UPDATE elementi SET titolo_it=?, riassunto=? WHERE id=?",
                    (r["titolo"], giornale.breve(r["testo"]), r["id"]))
    con.commit()
    inglesi = [r for r in righe if r["lingua"] != "it"]
    print(f"da tradurre: {len(inglesi)} (italiane pronte: {len(italiane)})", flush=True)
    if not inglesi:
        return
    with llm.ollama():
        # 1. MiniCPM: i repository nuovi. Uno già spiegato un altro giorno riusa la spiegazione (già in italiano),
        # ma solo se scritta con questa pipeline: fino al 26/9 le spiegazioni le scriveva MiniCPM in italiano
        # ("un piattaforma", "composazione"). Sulla scheda da 4 GB i due modelli non stanno insieme: prima tutto
        # MiniCPM, poi tutte le traduzioni.
        inglese = {}
        for r in inglesi:
            if r["sezione"] != "github":
                continue
            gia = con.execute("SELECT riassunto FROM elementi WHERE sezione='github' AND titolo=? AND visto_il<?"
                              " AND visto_il>'2026-09-26' AND length(riassunto)>60 ORDER BY visto_il DESC LIMIT 1",
                              (r["titolo"], oggi)).fetchone()
            try:
                inglese[r["id"]] = ("it", gia[0]) if gia else ("en", _spiegazione_en(r))
            except OSError as err:
                print(f"     MiniCPM non disponibile ({err}): {r['titolo']}", flush=True)
                inglese[r["id"]] = ("en", r["testo"])
        # 2. TranslateGemma: titoli e prime frasi dei testi
        usati = set()                                # certi feed (The Verge) mandano lo stesso testo per più articoli
        for i, r in enumerate(inglesi, 1):
            t0 = time.time()
            try:
                if r["sezione"] == "github":
                    lingua, spiegazione = inglese[r["id"]]
                    titolo = r["titolo"]
                    if lingua == "it":
                        riassunto = spiegazione
                    else:                            # se MiniCPM non ha risposto, si traduce la descrizione del repository
                        originale = spiegazione or r["testo"]
                        riassunto = (_tradotta(originale, 220) or originale) if originale else ""
                    riassunto = giornale.breve(riassunto)     # una piccola descrizione: due frasi al massimo
                else:
                    titolo = _titolo_it(r["titolo"]) or None
                    originale = "" if r["ruolo"] == "breve" else giornale.breve(r["testo"])
                    if originale in usati:
                        originale = ""
                    usati.add(originale)
                    riassunto = (_tradotta(originale, 240) or originale) if originale else ""
            except OSError as err:                  # timeout o Ollama giù: questo resta in inglese, il giro va avanti
                print(f"     modello non disponibile ({err}), resta in inglese", flush=True)
                titolo, riassunto = None, "" if r["ruolo"] == "breve" else giornale.breve(r["testo"])
            con.execute("UPDATE elementi SET titolo_it=?, riassunto=? WHERE id=?", (titolo, riassunto, r["id"]))
            con.commit()
            if r["sezione"] != "github" and not titolo:
                print(f"     titolo lasciato in inglese: {r['titolo'][:70]}", flush=True)
            print(f"  {i:>2}/{len(inglesi)} {r['sezione']:<8} {time.time() - t0:4.1f}s  {r['titolo'][:60]}", flush=True)


def impagina(con, oggi):
    uscita = RADICE / "edizioni" / f"{oggi}.html"
    uscita.parent.mkdir(exist_ok=True)
    uscita.write_text(giornale.pagina(con, oggi, PROFILO), "utf-8")
    print(f"edizione: {uscita}", flush=True)
    archivia_pdf(uscita)


EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def archivia_pdf(html):
    """L'edizione come esce dalla stampante (?carta: due fogli, niente intestazioni), accanto all'HTML.
    ~0,5 MB al giorno. Edge senza finestra, con un profilo suo per non toccare quello di tutti i giorni."""
    pdf = html.with_suffix(".pdf")
    try:
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", f"--user-data-dir={RADICE / 'data' / 'edge-pdf'}",
                        "--virtual-time-budget=10000", "--no-pdf-header-footer", f"--print-to-pdf={pdf}",
                        html.as_uri() + "?carta"], timeout=120, capture_output=True)
        print(f"archivio: {pdf}", flush=True)
    except (OSError, subprocess.SubprocessError) as err:
        print(f"  pdf saltato ({err})", flush=True)


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
        raccogli_sport(con, oggi)
        raccogli_attualita(con, oggi)
        raccogli_gaming(con, oggi)
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
