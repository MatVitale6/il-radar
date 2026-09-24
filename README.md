# Il Radar

Giornale personale del mattino: raccoglie le novità, un modello locale (MiniCPM5 via Ollama)
decide cosa ti riguarda, e le impagina come la prima pagina di un quotidiano, stampabile.

Solo libreria standard Python. Niente testo esce dal PC.

## Uso

    py -m radar giro     # raccoglie, prefiltra, fa valutare a MiniCPM, scrive edizioni/AAAA-MM-GG.html
    py -m radar serve    # apre il giornale su http://127.0.0.1:8765 con i pulsanti utile / non mi interessa

## Come funziona

1. **raccolta** (`radar/fonti.py`) — per ora il feed RSS di arXiv (cs.AI, cs.LG, cs.CR), solo lavori nuovi
2. **doppioni** — SQLite in `data/radar.db`: ogni elemento lo vedi una volta
3. **prefiltro** — parole chiave pesate in `profilo.toml`; passano al modello al massimo `prefiltro.massimo` elementi
4. **MiniCPM** (`radar/llm.py`) — voto 0-10, titolo e riassunto in italiano, "perché ti riguarda"
5. **impaginazione** (`radar/giornale.py`) — pubblicati quelli con voto ≥ `pubblica.soglia`
6. **giudizi** — i pulsanti sulla pagina salvano +1/-1 nel database, per tarare profilo e soglie

## Cartelle non versionate

- `runtime/ollama/` — Ollama portabile (v0.34.4), nessuna installazione di sistema
- `runtime/models/` — i pesi (`openbmb/minicpm5:q8_0`, 1,2 GB)
- `data/`, `edizioni/`

Per rimettere in piedi il runtime su un altro PC: scaricare `ollama-windows-amd64.zip` dalle release
di Ollama in `runtime/ollama/`, poi con `OLLAMA_MODELS=runtime/models` eseguire
`ollama pull openbmb/minicpm5:q8_0`.
