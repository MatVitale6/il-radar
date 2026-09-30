"""La TUI del Radar: menu a tastiera per personalizzare `profilo.toml` senza toccare il file.

Solo libreria standard (niente curses: su Windows non c'è). Le modifiche si fanno sul TESTO del file, riga per riga,
così commenti e ordine restano com'erano; il file si scrive solo con "Salva", dopo aver controllato che sia ancora
TOML valido, e il vecchio resta in `profilo.toml.bak`.

    py -m radar tui                                   (Windows, Linux, macOS)
    docker exec -it radar python3 -m radar tui        (Docker)
"""
import json
import os
import re
import shutil
import sys
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

# ── modifica del testo del profilo ────────────────────────────────────────────


def _toml(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ", ".join(_toml(x) for x in v) + "]"
    raise TypeError(v)


def _intervallo(righe, tabella):
    """(inizio, fine) delle righe di una tabella: dopo la sua intestazione `[tabella]`, fino alla prossima."""
    testa = re.compile(r"^\[" + re.escape(tabella) + r"\]\s*(#.*)?$")
    for i, r in enumerate(righe):
        if testa.match(r):
            j = i + 1
            while j < len(righe) and not righe[j].startswith("["):
                j += 1
            return i + 1, j
    raise KeyError(tabella)


def imposta(testo, tabella, chiave, valore):
    """`chiave = valore` dentro `[tabella]`, tenendo il commento a fine riga; se la chiave non c'è, la aggiunge."""
    righe = testo.split("\n")
    a, b = _intervallo(righe, tabella)
    rx = re.compile(r"^(\s*" + re.escape(chiave) + r"\s*=\s*)(.*?)(\s+#.*)?$")
    for i in range(a, b):
        if m := rx.match(righe[i]):
            righe[i] = m[1] + _toml(valore) + (m[3] or "")
            return "\n".join(righe)
    righe.insert(a, f"{chiave} = {_toml(valore)}")
    return "\n".join(righe)


_VOCE = re.compile(r'^\s*"((?:[^"\\]|\\.)+)"\s*=\s*(.*?)(\s+#.*)?$')


def voci(testo, tabella):
    """Le righe `"parola" = valore` di una tabella: [(parola, valore in TOML)]."""
    righe = testo.split("\n")
    a, b = _intervallo(righe, tabella)
    return [(json.loads(f'"{m[1]}"'), m[2]) for r in righe[a:b] if (m := _VOCE.match(r))]


def imposta_voce(testo, tabella, parola, valore):
    """Cambia il valore di `"parola" = ...` o, se non c'è, la aggiunge dopo l'ultima voce della tabella."""
    righe = testo.split("\n")
    a, b = _intervallo(righe, tabella)
    nuova = f"{json.dumps(parola, ensure_ascii=False)} = {valore}"
    ultima = None
    for i in range(a, b):
        if m := _VOCE.match(righe[i]):
            ultima = i
            if json.loads(f'"{m[1]}"') == parola:
                righe[i] = nuova + (m[3] or "")
                return "\n".join(righe)
    righe.insert((ultima + 1) if ultima is not None else a, nuova)
    return "\n".join(righe)


def togli_voce(testo, tabella, parola):
    righe = testo.split("\n")
    a, b = _intervallo(righe, tabella)
    for i in range(a, b):
        if (m := _VOCE.match(righe[i])) and json.loads(f'"{m[1]}"') == parola:
            del righe[i]
            break
    return "\n".join(righe)


def imposta_lista(testo, tabella, chiave, valori):
    """Riscrive un elenco `chiave = [...]` (anche su più righe), andando a capo tra un elemento e l'altro."""
    righe = testo.split("\n")
    a, b = _intervallo(righe, tabella)
    blocco = "\n".join(righe[a:b])
    rx = re.compile(r"^(\s*" + re.escape(chiave) + r"\s*=\s*)\[.*?\]", re.S | re.M)
    m = rx.search(blocco)
    if not m:
        raise KeyError(chiave)
    rientro, corrente, linee = " " * (len(m[1].lstrip("\n")) + 1), "", []
    for v in map(_toml, valori):
        if corrente and len(corrente) + len(v) > 96:
            linee.append(corrente.rstrip())
            corrente = ""
        corrente += v + ", "
    linee.append(corrente.rstrip().rstrip(","))
    nuovo = m[1] + "[" + ("\n" + rientro).join(linee) + "]"
    righe[a:b] = (blocco[:m.start()] + nuovo + blocco[m.end():]).split("\n")
    return "\n".join(righe)


# ── terminale ─────────────────────────────────────────────────────────────────


def _out(s):
    sys.stdout.write(s)
    sys.stdout.flush()


def _tasto():
    """Un tasto: 'su', 'giu', 'invio', 'esc' oppure il carattere premuto."""
    if os.name == "nt":
        import msvcrt
        c = msvcrt.getwch()
        if c in ("\x00", "\xe0"):
            return {"H": "su", "P": "giu"}.get(msvcrt.getwch(), "")
        return {"\r": "invio", "\x1b": "esc", "\x03": "esc"}.get(c, c)
    import select
    fd = sys.stdin.fileno()
    c = os.read(fd, 1)                                       # os.read, non sys.stdin: quest'ultimo legge in anticipo
    if c == b"\x1b":                                         # e select non vedrebbe più il resto della freccia
        if select.select([fd], [], [], 0.05)[0]:
            return {b"[A": "su", b"[B": "giu", b"OA": "su", b"OB": "giu"}.get(os.read(fd, 2), "")
        return "esc"
    return {b"\r": "invio", b"\n": "invio", b"\x03": "esc"}.get(c, c.decode("latin-1"))


_vecchio = None


def _raw(acceso):
    """Su Linux/macOS il terminale sta in modalità raw per tutta la sessione dei menu (un tasto alla volta, senza
    Invio) e torna normale solo per `input()`. Se lo si cambiasse a ogni tasto, quelli che arrivano in fretta (un tasto
    tenuto premuto) resterebbero nel buffer di riga e andrebbero persi."""
    global _vecchio
    if os.name == "nt" or not sys.stdin.isatty():
        return
    import termios
    import tty
    fd = sys.stdin.fileno()
    if acceso and _vecchio is None:
        _vecchio = termios.tcgetattr(fd)
        tty.setcbreak(fd)                                    # non setraw: senza, "\n" non torna a capo e il menu va a scalini
    elif not acceso and _vecchio is not None:
        termios.tcsetattr(fd, termios.TCSADRAIN, _vecchio)
        _vecchio = None


def _riga(domanda, predefinito=""):
    _raw(False)
    _out("\x1b[?25h")
    try:
        risposta = input(f"{domanda}" + (f" [{predefinito}]" if predefinito != "" else "") + ": ").strip()
    finally:
        _raw(True)
    return risposta or str(predefinito)


def menu(titolo, righe, piede="↑↓ scegli · Invio apri · Esc indietro", tasti="", corrente=0, vuoto="(niente)"):
    """Un menu a schermo intero. Ritorna (indice, tasto): tasto è 'invio' o una delle lettere in `tasti`;
    con Esc ritorna (None, 'esc')."""
    i = min(corrente, max(0, len(righe) - 1))
    while True:
        altezza = max(5, shutil.get_terminal_size((80, 24)).lines - 6)
        inizio = max(0, min(i - altezza // 2, len(righe) - altezza))
        corpo = [f"\x1b[7m ▸ {r} \x1b[0m" if k == i else f"   {r}" for k, r in enumerate(righe)][inizio:inizio + altezza]
        _out("\x1b[2J\x1b[H\x1b[?25l"                         # pulisce, cursore in alto, cursore nascosto
             f"\x1b[1m {titolo}\x1b[0m\n\n" + ("\n".join(corpo) if righe else f"   {vuoto}")
             + f"\n\n\x1b[2m {piede}\x1b[0m\n")
        t = _tasto()
        if t == "su" and righe:
            i = (i - 1) % len(righe)
        elif t == "giu" and righe:
            i = (i + 1) % len(righe)
        elif t == "invio":
            return i, "invio"
        elif t == "esc":
            return None, "esc"
        elif t in tasti:
            return i, t


def avviso(testo):
    _out(f"\x1b[2J\x1b[H\n {testo}\n\n\x1b[2m Premi un tasto per continuare\x1b[0m\n")
    _tasto()


def _intero(testo, predefinito, minimo=-99, massimo=999):
    try:
        return min(massimo, max(minimo, int(_riga(testo, predefinito))))
    except ValueError:
        return None


# ── schermate ─────────────────────────────────────────────────────────────────

SEZIONI = {
    "notizie": ("Notizie su AI e sviluppo", ("massimo", "brevi")),
    "github": ("Repository GitHub", ("massimo", "per_tema")),
    "sport": ("Sport", ("articoli", "brevi")),
    "attualita": ("Attualità, solo titoli", ("per_zona",)),
    "gaming": ("Gaming", ("articoli", "brevi")),
    "weekend": ("Weekend: agenda della città", ("massimo",)),
    "ricerca": ("Ricerca (arXiv), solo titoli", ("massimo",)),
}
QUANTE = {"massimo": "quante voci", "brevi": "quante in breve (solo titolo)", "per_tema": "al massimo per tema",
          "articoli": "quanti articoli per esteso", "per_zona": "titoli per l'Italia e per l'estero"}
ARGOMENTI = [
    ("notizie.tecnologia", "Notizie · AI e sviluppo"),
    ("notizie.sicurezza", "Notizie · cybersicurezza"),
    ("notizie.norme", "Notizie · governi e regole"),
    ("notizie.giu", "Notizie · da spingere giù (pesi negativi)"),
    ("sport.discipline", "Sport · discipline che segui"),
    ("gaming.parole", "Gaming · parole che contano"),
    ("ricerca.parole", "Ricerca · parole che contano"),
]
LISTE = [("sport", "italiani", "Sport · atleti italiani da seguire"),
         ("weekend", "luoghi", "Weekend · luoghi che contano")]


class Profilo:
    def __init__(self, file):
        self.file = Path(file)
        self.testo = self.originale = self.file.read_text("utf-8")

    @property
    def dati(self):
        return tomllib.loads(self.testo)

    @property
    def modificato(self):
        return self.testo != self.originale

    def salva(self):
        tomllib.loads(self.testo)                               # mai scrivere un file rotto
        shutil.copy(self.file, self.file.with_name(self.file.name + ".bak"))
        self.file.write_text(self.testo, "utf-8")
        self.originale = self.testo


def geocodifica(nome):
    """Cerca una città su Open-Meteo (gratuito, senza chiave): [(etichetta, nome, lat, lon)]."""
    url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": nome, "count": 6, "language": "it", "format": "json"})
    with urllib.request.urlopen(url, timeout=15) as r:
        trovate = json.load(r).get("results", [])
    return [(f"{c['name']}, {c.get('admin1', '')} ({c.get('country', '')})".replace(", (", " ("),
             c["name"], round(c["latitude"], 3), round(c["longitude"], 3)) for c in trovate]


def schermata_citta(p):
    attuale = p.dati.get("meteo", {})
    nome = _riga(f"Città per il tempo (ora: {attuale.get('citta', '?')}). Vuoto = lascia com'è", "")
    if not nome:
        return
    try:
        trovate = geocodifica(nome)
    except OSError:
        trovate = []
        avviso("Non riesco a cercare la città (sei offline?). Inserisci le coordinate a mano.")
        lat, lon = _riga("Latitudine (es. 41.89)"), _riga("Longitudine (es. 12.49)")
        try:
            trovate = [(nome, nome, round(float(lat), 3), round(float(lon), 3))]
        except ValueError:
            return
    if not trovate:
        return avviso(f"Nessuna città trovata per «{nome}».")
    i, _ = menu("Quale?", [t[0] for t in trovate]) if len(trovate) > 1 else (0, "invio")
    if i is None:
        return
    _, citta, lat, lon = trovate[i]
    for chiave, valore in (("citta", citta), ("lat", lat), ("lon", lon)):
        p.testo = imposta(p.testo, "meteo", chiave, valore)


def schermata_sezioni(p):
    i = 0
    while True:
        dati = p.dati
        righe = [f"[{'x' if dati.get(s, {}).get('attiva', True) else ' '}] {nome}  "
                 f"({' + '.join(str(dati.get(s, {}).get(k, '?')) for k in chiavi)})"
                 for s, (nome, chiavi) in SEZIONI.items()]
        i, tasto = menu("Sezioni del giornale", righe, "↑↓ scegli · Spazio accende/spegne · Invio quante voci · Esc indietro",
                        " ", i or 0)
        if i is None:
            return
        sezione = list(SEZIONI)[i]
        if tasto == " ":
            p.testo = imposta(p.testo, sezione, "attiva", not dati.get(sezione, {}).get("attiva", True))
        else:
            for chiave in SEZIONI[sezione][1]:
                n = _intero(f"{SEZIONI[sezione][0]} · {QUANTE[chiave]}", dati.get(sezione, {}).get(chiave, 5), 0, 99)
                if n is not None:
                    p.testo = imposta(p.testo, sezione, chiave, n)


def schermata_voci(p, tabella, titolo, tema=False):
    """Le parole di una tabella con il loro peso (o, per i repository, nome → filtro di ricerca GitHub)."""
    i = 0
    while True:
        elenco = voci(p.testo, tabella)
        righe = [f"{k:<34} → {json.loads(v)}" if tema else f"{k:<34} {int(v):+d}" for k, v in elenco]
        i, tasto = menu(titolo, righe, "↑↓ scegli · Invio cambia · a aggiungi · d toglie · Esc indietro", "ad", i or 0,
                        "(vuota: premi a per aggiungere)")
        if i is None:
            return
        if tasto == "a":
            if tema:
                arg = _riga("Argomento GitHub (es. rust, home-automation)").lower().replace(" ", "-")
                if arg:
                    p.testo = imposta_voce(p.testo, tabella, arg.replace("-", " ").title(), json.dumps(f"topic:{arg}"))
            else:
                parola = _riga("Parola (es. cyber*, AI, data center: * = qualunque finale)")
                n = _intero("Peso (-10 … 10: più alto conta di più, negativo spinge giù)", 3, -20, 20) if parola else None
                if n is not None:
                    p.testo = imposta_voce(p.testo, tabella, parola, str(n))
        elif elenco and tasto == "d":
            p.testo = togli_voce(p.testo, tabella, elenco[i][0])
            i = max(0, i - 1)
        elif elenco and tasto == "invio":
            parola, valore = elenco[i]
            if tema:
                nuovo = _riga(f"Filtro di ricerca per «{parola}» (es. topic:mcp language:python)", json.loads(valore))
                p.testo = imposta_voce(p.testo, tabella, parola, json.dumps(nuovo))
            else:
                n = _intero(f"Peso di «{parola}»", int(valore), -20, 20)
                if n is not None:
                    p.testo = imposta_voce(p.testo, tabella, parola, str(n))


def schermata_lista(p, sezione, chiave, titolo):
    i = 0
    while True:
        elenco = p.dati.get(sezione, {}).get(chiave, [])
        i, tasto = menu(titolo, list(elenco), "↑↓ scegli · a aggiungi · d toglie · Esc indietro", "ad", i or 0,
                        "(vuota: premi a per aggiungere)")
        if i is None:
            return
        if tasto == "a":
            nuovo = _riga("Aggiungi")
            if nuovo:
                p.testo = imposta_lista(p.testo, sezione, chiave, elenco + [nuovo])
        elif elenco and tasto == "d":
            p.testo = imposta_lista(p.testo, sezione, chiave, [x for k, x in enumerate(elenco) if k != i])
            i = max(0, i - 1)


def _scegli_argomento(p):
    i = 0
    while True:
        i, _ = menu("Argomenti e parole chiave: cosa fa entrare una notizia", [t for _, t in ARGOMENTI], corrente=i or 0)
        if i is None:
            return
        schermata_voci(p, *ARGOMENTI[i])


def _scegli_lista(p):
    i, _ = menu("Liste", [t for _, _, t in LISTE])
    if i is not None:
        schermata_lista(p, *LISTE[i])


def avvia(file):
    if not sys.stdin.isatty():
        sys.exit("La TUI vuole un terminale interattivo. In Docker: docker exec -it <contenitore> python3 -m radar tui")
    if os.name == "nt":
        # Comando costante e vuoto, senza alcun input: è il trucco noto per far attivare a cmd/PowerShell di Windows 10+
        # le sequenze ANSI (colori, cancellazione dello schermo) che il menu usa.
        os.system("")
    p = Profilo(file)
    i = 0
    _raw(True)
    try:
        while True:
            d = p.dati
            accese = sum(d.get(s, {}).get("attiva", True) for s in SEZIONI)
            righe = [f"Dove abiti (il tempo)            {d.get('meteo', {}).get('citta', '?')}",
                     f"Sezioni del giornale            {accese} accese su {len(SEZIONI)}",
                     "Argomenti e parole chiave",
                     "Repository GitHub: i temi che segui",
                     "Liste: atleti, luoghi del weekend",
                     "Salva ed esci" + ("  (ci sono modifiche)" if p.modificato else ""),
                     "Esci senza salvare"]
            i, _ = menu("Il Radar · il tuo profilo", righe, "↑↓ scegli · Invio apri · Esc esci", corrente=i or 0)
            if i is None or i == 6:
                if p.modificato and _riga("Ci sono modifiche non salvate. Esci comunque? (s/n)", "n").lower() != "s":
                    continue
                break
            if i == 5:
                if p.modificato:
                    p.salva()
                    avviso(f"Salvato in {p.file}\n (il vecchio è in {p.file.name}.bak).\n Vale dal prossimo giro; "
                           "per vederlo subito: python -m radar giro")
                break
            [schermata_citta, schermata_sezioni, _scegli_argomento,
             lambda q: schermata_voci(q, "github.temi", "Repository GitHub: temi e filtri di ricerca", tema=True),
             _scegli_lista][i](p)
    finally:
        _raw(False)
        _out("\x1b[?25h\x1b[2J\x1b[H")                         # cursore di nuovo visibile, schermo pulito
