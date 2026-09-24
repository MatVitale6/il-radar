"""Server locale: mostra l'edizione (sempre aggiornata coi tuoi giudizi), registra utile / non mi interessa
e, su richiesta (anche dal telefono), stampa l'edizione sulla stampante predefinita."""
import datetime as dt
import json
import re
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from . import giornale

PORTA = 8765
# Tutte le interfacce: così il giornale si apre anche dal telefono sulla rete di casa (http://<ip-del-pc>:8765).
# Dall'esterno lo tiene chiuso il firewall di Windows: la porta è aperta solo sulle reti "private"
# (vedi strumenti/rete-di-casa.ps1).
INDIRIZZO = ("0.0.0.0", PORTA)
LOCALE = f"http://127.0.0.1:{PORTA}/"

EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
# Profilo Edge tutto suo: se Edge è già aperta col profilo normale, --kiosk-printing verrebbe ignorato
PROFILO_EDGE = Path(__file__).resolve().parent.parent / "data" / "edge-stampa"
_stampa = {"proc": None}


class Server(HTTPServer):
    # su Windows il riuso dell'indirizzo lascia due server sulla stessa porta: così il secondo fallisce
    allow_reuse_address = False


def stampa():
    """Apre il giornale in una Edge fuori schermo in modalità chiosco di stampa: la pagina (con ?stampa) si
    impagina sul foglio A4, chiama print() e va dritta alla stampante predefinita, senza finestra di dialogo."""
    p = _stampa["proc"]
    if p and p.poll() is None:
        return False                                   # una stampa è già in corso
    _stampa["proc"] = p = subprocess.Popen([
        EDGE, "--kiosk-printing", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        f"--user-data-dir={PROFILO_EDGE}", "--window-position=-32000,-32000", "--window-size=900,1300",
        f"--app={LOCALE}?stampa"])
    threading.Timer(120, lambda: p.poll() is None and p.kill()).start()   # rete di sicurezza se non si chiude
    return True


def avvia(con, regole, apri=True):
    """Tiene acceso il server; `apri` mostra anche la pagina. Se un server gira già, al massimo apre la pagina."""
    class Gestore(BaseHTTPRequestHandler):
        def rispondi(self, codice, corpo=b"", tipo="text/html; charset=utf-8"):
            self.send_response(codice)
            self.send_header("Content-Type", tipo)
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):
            # "/" = ultima edizione; "/2026-09-24" = quella data
            # "?carta" (anteprima) e "?stampa" li legge la pagina stessa: qui conta solo il percorso
            m = re.fullmatch(r"/(\d{4}-\d{2}-\d{2})?", self.path.split("?", 1)[0])
            if not m:
                return self.rispondi(404, b"non trovato")
            data = m[1] or con.execute("SELECT MAX(visto_il) FROM elementi WHERE ruolo IS NOT NULL").fetchone()[0] \
                or dt.date.today().isoformat()
            self.rispondi(200, giornale.pagina(con, data, regole).encode())

        def do_POST(self):
            if self.path == "/stampa":
                partita = stampa()
                return self.rispondi(202 if partita else 409,
                                     "Stampa inviata alla Canon".encode() if partita else "Stampa già in corso".encode(),
                                     "text/plain; charset=utf-8")
            if self.path != "/giudizio":
                return self.rispondi(404)
            dati = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            con.execute("UPDATE elementi SET giudizio=? WHERE id=?", (int(dati["g"]) or None, dati["id"]))
            con.commit()
            self.rispondi(204)

        def log_message(self, *_):
            pass

    try:
        server = Server(INDIRIZZO, Gestore)
    except OSError:
        # già acceso (all'avvio del PC o da un clic precedente): basta la pagina
        if apri:
            webbrowser.open(LOCALE)
        return
    print(f"Il Radar su {LOCALE} (e sulla rete di casa, porta {PORTA})")
    if apri:
        webbrowser.open(LOCALE)
    server.serve_forever()
