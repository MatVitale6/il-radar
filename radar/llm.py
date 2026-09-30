"""Modelli in locale, tramite l'Ollama portabile in runtime/.

- TRADUTTORE (TranslateGemma 4B): traduce dall'inglese all'italiano. È fatto apposta e traduce molto meglio di un
  modello generico: MiniCPM4.1 scriveva "Data centeri sono blind boxes".
- MODELLO (MiniCPM4.1 8B): riassume e spiega in inglese (i repository GitHub dal README).

Sulla scheda da 4 GB i due non stanno insieme: Ollama scarica l'uno per caricare l'altro (mezzo minuto). Chi chiama
li usa quindi a blocchi: prima tutto ciò che serve a MiniCPM, poi tutte le traduzioni.
"""
import json
import os
import shutil
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
OLLAMA = RADICE / "runtime" / "ollama" / "ollama.exe"      # l'Ollama portabile di Windows, se c'è
if not OLLAMA.exists():
    OLLAMA = shutil.which("ollama") or OLLAMA               # altrimenti quello installato nel sistema
URL = "http://127.0.0.1:11434"
MODELLO = "openbmb/minicpm4.1"  # 8B; il 5-1B era veloce ma scriveva un italiano povero
TRADUTTORE = "translategemma:4b"

# il formato che Google indica per TranslateGemma: istruzione, poi due righe vuote, poi il testo
_ISTRUZIONE = ("You are a professional English (en) to Italian (it) translator. Your goal is to accurately convey the "
               "meaning and nuances of the original English text while adhering to Italian grammar, vocabulary, and "
               "cultural sensitivities.\nProduce only the Italian translation, without any additional explanations or "
               "commentary. Please translate the following English text into Italian:\n\n\n")


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


def _chat(modello, messaggi, num_predict, temperatura=0):
    # num_predict: senza un tetto il modello ogni tanto entra in un ciclo e scrive per sempre (il 25/9 una
    # chiamata ha superato i 10 minuti e ha fermato il giro). repeat_penalty: il 25/9 ha scritto
    # "l'immediato l'immediato l'immediato..." per mezza colonna.
    r = _post("/api/chat", {
        "model": modello,
        "messages": messaggi,
        "stream": False,
        "think": False,
        "options": {"temperature": temperatura, "num_predict": num_predict, "repeat_penalty": 1.1},
    }, timeout=180)
    return r["message"]["content"].strip()


def scrivi(sistema, testo):
    """MiniCPM: una domanda, risposta in testo semplice.

    Niente JSON: su Ollama 0.34 minicpm4.1 non regge l'output vincolato (400 "Failed to initialize samplers")
    e, se il JSON glielo chiedi a parole, circa metà delle volte lo sbaglia.
    """
    return _chat(MODELLO, [{"role": "system", "content": sistema}, {"role": "user", "content": testo}], 250)


def traduci(testo, num_predict=200, temperatura=0):
    """TranslateGemma: inglese -> italiano."""
    return _chat(TRADUTTORE, [{"role": "user", "content": _ISTRUZIONE + testo}], num_predict, temperatura)
