"""Il Radar.

    py -m radar giro      raccoglie, seleziona, fa riassumere a MiniCPM e impagina l'edizione di oggi
    py -m radar serve     tiene acceso il giornale su http://127.0.0.1:8765 (all'avvio del PC, senza finestre)
    py -m radar apri      apre il giornale nel browser, accendendo il server se serve (l'icona sul desktop)
"""
import datetime as dt
import re
import sys
import time
import tomllib
from pathlib import Path

from . import db, fonti, giornale, llm

RADICE = Path(__file__).resolve().parent.parent
PROFILO = tomllib.loads((RADICE / "profilo.toml").read_text("utf-8"))

# Al modello chiediamo solo di riassumere e tradurre: nei test sul giudizio (pertinente sì/no,
# campo di applicazione) sbagliava troppo. La selezione la fanno le parole chiave.
SISTEMA = """Sei un redattore scientifico italiano. Ricevi titolo e abstract di un articolo in inglese.
Rispondi in italiano corretto:
- titolo_it: titolo di giornale in italiano, massimo 10 parole, fedele all'articolo
- riassunto: una o due frasi in italiano, massimo 40 parole: cosa fa o scopre l'articolo, in concreto"""

SCHEMA = {
    "type": "object",
    "properties": {"titolo_it": {"type": "string"}, "riassunto": {"type": "string"}},
    "required": ["titolo_it", "riassunto"],
}


def punteggio(e):
    testo = (e["titolo"] + " " + e["testo"]).lower()
    trovate = {parola: peso for parola, peso in PROFILO["parole"].items()
               if re.search(r"\b" + re.escape(parola) + r"(?:s|es)?\b", testo)}
    positive = sorted((p for p in trovate if trovate[p] > 0), key=lambda p: -trovate[p])
    return sum(trovate.values()), ", ".join(positive)


def raccogli(con, oggi):
    nuovi = 0
    for e in fonti.arxiv():
        punti, parole = punteggio(e)
        cur = con.execute(
            "INSERT OR IGNORE INTO elementi (id, fonte, sezione, titolo, url, testo, autori, visto_il, punti, parole)"
            " VALUES (:id, :fonte, :sezione, :titolo, :url, :testo, :autori, :oggi, :punti, :parole)",
            e | {"oggi": oggi, "punti": punti, "parole": parole})
        nuovi += cur.rowcount
    con.commit()
    print(f"raccolti: {nuovi} nuovi", flush=True)


def riassumi(con, oggi):
    p = PROFILO["pubblica"]
    righe = con.execute(
        "SELECT * FROM elementi WHERE visto_il = ? AND punti >= ? ORDER BY punti DESC LIMIT ?",
        (oggi, p["soglia"], p["massimo"])).fetchall()
    righe = [r for r in righe if r["riassunto"] is None]
    print(f"da riassumere: {len(righe)}", flush=True)
    with llm.ollama():
        for i, r in enumerate(righe, 1):
            t0 = time.time()
            try:
                v = llm.chiedi(SISTEMA, f"Titolo: {r['titolo']}\n\nAbstract: {r['testo']}", SCHEMA)
                titolo, riassunto = v["titolo_it"].strip() or None, v["riassunto"].strip()
            except (ValueError, KeyError, AttributeError) as err:
                # risposta illeggibile: esce comunque, col titolo e la prima frase originali
                print(f"     riassunto non riuscito ({err!r}), uso l'abstract", flush=True)
                titolo, riassunto = None, r["testo"].split(". ")[0] + "."
            con.execute("UPDATE elementi SET titolo_it=?, riassunto=? WHERE id=?", (titolo, riassunto, r["id"]))
            con.commit()
            print(f"  {i:>2}/{len(righe)}  {time.time() - t0:4.1f}s  {r['titolo'][:70]}", flush=True)


def impagina(con, oggi):
    uscita = RADICE / "edizioni" / f"{oggi}.html"
    uscita.parent.mkdir(exist_ok=True)
    uscita.write_text(giornale.pagina(con, oggi, PROFILO["pubblica"]), "utf-8")
    print(f"edizione: {uscita}", flush=True)


def main():
    comando = sys.argv[1] if len(sys.argv) > 1 else "giro"
    con = db.apri()
    oggi = dt.date.today().isoformat()
    if comando == "giro":
        raccogli(con, oggi)
        riassumi(con, oggi)
        impagina(con, oggi)
    elif comando in ("serve", "apri"):
        from . import server
        server.avvia(con, PROFILO["pubblica"], apri=comando == "apri")
    else:
        sys.exit(__doc__)


main()
