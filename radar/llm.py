"""MiniCPM in locale, tramite l'Ollama portabile in runtime/."""
import json
import os
import subprocess
import time
import urllib.error
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


def chiedi(sistema, testo, schema):
    """Una domanda, risposta JSON secondo lo schema (i valori vanno comunque controllati da chi chiama)."""
    corpo = {
        "model": MODELLO,
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": testo}],
        "format": schema,
        "stream": False,
        "think": False,
        "options": {"temperature": 0},
    }
    try:
        r = _post("/api/chat", corpo)
    except urllib.error.HTTPError as e:
        if e.code != 400:
            raise
        # Alcuni modelli (minicpm4.1 su Ollama 0.34) non reggono l'output vincolato: il JSON lo chiedo a parole.
        del corpo["format"]
        corpo["messages"][0]["content"] += ("\n\nRispondi solo con un oggetto JSON conforme a questo schema:\n"
                                            + json.dumps(schema, ensure_ascii=False))
        r = _post("/api/chat", corpo)
    risposta = r["message"]["content"]
    return json.loads(risposta[risposta.find("{"):risposta.rfind("}") + 1])
