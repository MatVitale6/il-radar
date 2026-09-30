"""Archivio SQLite: ogni elemento visto una volta sola, con punteggio dal profilo e giudizio tuo."""
import os
import sqlite3
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
# Dove vivono i dati dell'utente (database, edizioni, profilo). In Docker è il volume /dati; altrimenti la cartella
# del progetto, come prima.
DATI = Path(os.environ.get("RADAR_DATI") or RADICE)
FILE = DATI / "data" / "radar.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS elementi (
    id TEXT PRIMARY KEY,
    fonte TEXT, sezione TEXT, titolo TEXT, url TEXT, testo TEXT, autori TEXT,
    visto_il TEXT,            -- data dell'edizione (YYYY-MM-DD)
    punti INTEGER,            -- somma dei pesi delle parole chiave (sulla pagina: tagliata a 0-10)
    parole TEXT,              -- le parole chiave trovate, per "perché è qui"
    titolo_it TEXT, riassunto TEXT,   -- da MiniCPM (o dalla fonte, se già italiana)
    giudizio INTEGER          -- +1 / -1 dato da te sulla pagina
);
CREATE TABLE IF NOT EXISTS meteo (data TEXT PRIMARY KEY, dati TEXT);   -- JSON: cielo, min, max, pioggia_mm, fonte
-- stelle dei repository osservati, una riga al giorno: da qui la crescita ("vanno forte")
CREATE TABLE IF NOT EXISTS stelle (repo TEXT, data TEXT, stelle INTEGER, PRIMARY KEY (repo, data));
"""

# colonne arrivate dopo la prima versione: aggiunte al volo ai database esistenti
NUOVE = {
    "rubrica": "TEXT",        # notizie: norme / sicurezza / tecnologia; ricerca: ai / sicurezza
    "ruolo": "TEXT",          # 'articolo' (pubblicato per esteso) / 'breve' (solo titolo) / NULL
    "lingua": "TEXT",
    "uscito": "TEXT",         # data di pubblicazione alla fonte
    "copertura": "INTEGER DEFAULT 1",  # quante testate hanno dato la stessa notizia
    "extra": "TEXT",          # JSON: per GitHub stelle, linguaggio, temi
}


def apri():
    FILE.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(FILE)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    presenti = {r[1] for r in con.execute("PRAGMA table_info(elementi)")}
    for nome, tipo in NUOVE.items():
        if nome not in presenti:
            con.execute(f"ALTER TABLE elementi ADD COLUMN {nome} {tipo}")
    if "ruolo" not in presenti:
        # una volta sola, dalla prima versione: arXiv stava in sezione ai / sicurezza, "pubblicato" = ha un riassunto
        con.execute("UPDATE elementi SET rubrica = sezione, sezione = 'ricerca' WHERE sezione IN ('ai', 'sicurezza')")
        con.execute("UPDATE elementi SET ruolo = 'articolo' WHERE ruolo IS NULL AND riassunto IS NOT NULL")
    con.commit()
    return con
