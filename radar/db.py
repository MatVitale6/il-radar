"""Archivio SQLite: ogni elemento visto una volta sola, con punteggio dal profilo e giudizio tuo."""
import sqlite3
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "data" / "radar.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS elementi (
    id TEXT PRIMARY KEY,
    fonte TEXT, sezione TEXT, titolo TEXT, url TEXT, testo TEXT, autori TEXT,
    visto_il TEXT,            -- data dell'edizione (YYYY-MM-DD)
    punti INTEGER,            -- somma dei pesi delle parole chiave (sulla pagina: tagliata a 0-10)
    parole TEXT,              -- le parole chiave trovate, per "perché è qui"
    titolo_it TEXT, riassunto TEXT,   -- da MiniCPM, solo per i pubblicati
    giudizio INTEGER          -- +1 / -1 dato da te sulla pagina
);
"""


def apri():
    FILE.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(FILE)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con
