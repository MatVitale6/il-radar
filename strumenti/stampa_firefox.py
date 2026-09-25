"""Stampa una pagina in PDF con Firefox (senza finestra), come farebbe il suo "Stampa".

    py strumenti/stampa_firefox.py <url> <uscita.pdf>

Serve a controllare la stampa nel browser predefinito dell'utente (Firefox impagina in modo diverso da Edge/Chrome).
Avvia un Firefox a parte con un profilo temporaneo (non tocca quello aperto) e lo guida col protocollo Marionette.
"""
import base64
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

FIREFOX = Path(r"C:\Program Files\Mozilla Firefox\firefox.exe")
PORTA = 2828


class Marionette:
    def __init__(self, porta):
        for _ in range(120):
            try:
                self.s = socket.create_connection(("127.0.0.1", porta), timeout=5)
                self.s.recv(4096)                                # saluto del server
                break
            except OSError:
                time.sleep(0.5)
        else:
            raise RuntimeError("Firefox non risponde")
        self.s.settimeout(120)
        self.n = 0

    def chiama(self, comando, parametri=None):
        self.n += 1
        corpo = json.dumps([0, self.n, comando, parametri or {}])
        self.s.sendall(f"{len(corpo.encode())}:{corpo}".encode())
        buf = b""
        while b":" not in buf:
            buf += self.s.recv(65536)
        lunghezza, resto = buf.split(b":", 1)
        while len(resto) < int(lunghezza):
            resto += self.s.recv(1 << 20)
        _, _, errore, risultato = json.loads(resto.decode())
        if errore:
            raise RuntimeError(f"{comando}: {errore}")
        return risultato


def stampa(url, pdf, larghezza=1400, altezza=900, attesa=6):
    profilo = tempfile.mkdtemp(prefix="ff-stampa-")
    Path(profilo, "user.js").write_text('user_pref("marionette.port", %d);\n' % PORTA)
    proc = subprocess.Popen([FIREFOX, "--headless", "--no-remote", "--marionette", "-profile", profilo],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        m = Marionette(PORTA)
        m.chiama("WebDriver:NewSession", {"capabilities": {}})
        m.chiama("WebDriver:SetWindowRect", {"width": larghezza, "height": altezza})
        m.chiama("WebDriver:Navigate", {"url": url})
        time.sleep(attesa)                                       # caratteri, script di impaginazione
        r = m.chiama("WebDriver:Print", {"page": {"width": 21.0, "height": 29.7}, "margin": {"top": 0, "bottom": 0,
                     "left": 0, "right": 0}, "background": True, "shrinkToFit": False})
        Path(pdf).write_bytes(base64.b64decode(r["value"]))
    finally:
        proc.kill()
        time.sleep(1)
        shutil.rmtree(profilo, ignore_errors=True)


if __name__ == "__main__":
    stampa(sys.argv[1], sys.argv[2])
    print("scritto", sys.argv[2])
