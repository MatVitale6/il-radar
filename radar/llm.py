"""MiniCPM in locale, tramite l'Ollama portabile in runtime/."""
import json
import os
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
OLLAMA = RADICE / "runtime" / "ollama" / "ollama.exe"
URL = "http://127.0.0.1:11434"
MODELLO = "openbmb/minicpm4.1"  # 8B; il 5-1B era veloce ma scriveva un italiano povero


def _post(percorso, dati, timeout=600):
    req = urllib.request.Request(URL + percorso, json.dumps(dati).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def attivo():
    try:
        urllib.request.urlopen(URL + "/api/version", timeout=2)
        return True
    except OSError:
        return False


@contextmanager
def ollama():
    """Usa Ollama se gira già, altrimenti lo avvia per la durata del blocco e poi lo spegne."""
    if attivo():
        yield
        return
    env = dict(os.environ, OLLAMA_MODELS=str(RADICE / "runtime" / "models"))
    proc = subprocess.Popen([OLLAMA, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        for _ in range(60):
            if attivo():
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Ollama non parte")
        yield
    finally:
        proc.terminate()


def scrivi(sistema, testo):
    """Una domanda, risposta in testo semplice.

    Niente JSON: su Ollama 0.34 minicpm4.1 non regge l'output vincolato (400 "Failed to initialize samplers")
    e, se il JSON glielo chiedi a parole, circa metà delle volte lo sbaglia. Il testo a righe lo scrive sempre.
    """
    r = _post("/api/chat", {
        "model": MODELLO,
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": testo}],
        "stream": False,
        "think": False,
        # num_predict: senza un tetto il modello ogni tanto entra in un ciclo e scrive per sempre
        # (il 25/9 una chiamata ha superato i 10 minuti e ha fermato il giro)
        # repeat_penalty: il 25/9 ha scritto "l'immediato l'immediato l'immediato..." per mezza colonna
        "options": {"temperature": 0, "num_predict": 250, "repeat_penalty": 1.15},
    }, timeout=180)
    return r["message"]["content"].strip()
