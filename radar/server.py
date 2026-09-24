"""Server locale: mostra l'edizione (sempre aggiornata coi tuoi giudizi) e registra utile / non mi interessa."""
import datetime as dt
import json
import re
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import giornale

INDIRIZZO = ("127.0.0.1", 8765)


class Server(HTTPServer):
    # su Windows il riuso dell'indirizzo lascia due server sulla stessa porta: così il secondo fallisce
    allow_reuse_address = False


def avvia(con, regole):
    class Gestore(BaseHTTPRequestHandler):
        def rispondi(self, codice, corpo=b"", tipo="text/html; charset=utf-8"):
            self.send_response(codice)
            self.send_header("Content-Type", tipo)
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):
            # "/" = ultima edizione; "/2026-09-24" = quella data
            m = re.fullmatch(r"/(\d{4}-\d{2}-\d{2})?", self.path)
            if not m:
                return self.rispondi(404, b"non trovato")
            data = m[1] or con.execute("SELECT MAX(visto_il) FROM elementi WHERE riassunto IS NOT NULL").fetchone()[0] \
                or dt.date.today().isoformat()
            self.rispondi(200, giornale.pagina(con, data, regole).encode())

        def do_POST(self):
            if self.path != "/giudizio":
                return self.rispondi(404)
            dati = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            con.execute("UPDATE elementi SET giudizio=? WHERE id=?", (int(dati["g"]) or None, dati["id"]))
            con.commit()
            self.rispondi(204)

        def log_message(self, *_):
            pass

    url = f"http://{INDIRIZZO[0]}:{INDIRIZZO[1]}/"
    try:
        server = Server(INDIRIZZO, Gestore)
    except OSError:
        # già aperto da un doppio clic precedente: basta riaprire la pagina
        webbrowser.open(url)
        return
    print(f"Il Radar su {url}  (Ctrl+C per chiudere)")
    webbrowser.open(url)
    server.serve_forever()
