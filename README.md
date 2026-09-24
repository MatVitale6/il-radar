# Il Radar

Giornale personale del mattino: raccoglie le novità, un modello locale (MiniCPM5 via Ollama)
decide cosa ti riguarda, e le impagina come la prima pagina di un quotidiano, stampabile.

Solo libreria standard Python. Niente testo esce dal PC.

## Uso

- **Icona "Il Radar" sul desktop** → apre il giornale nel browser (se il server è spento lo riaccende).
- **All'accesso a Windows** il collegamento `Il Radar (server)` nella cartella Esecuzione automatica
  (`shell:startup`) accende il server in background, senza finestre. Per non farlo partire: cancella quel collegamento.
- **Il giro del mattino** lo lancia l'attività pianificata "Il Radar" (lun-ven 07:30) con `radar.cmd giro`;
  log in `data/giri.log`. Il server acceso mostra da solo l'edizione nuova.

A mano:

    py -m radar giro     # raccoglie, seleziona, fa riassumere a MiniCPM, scrive edizioni/AAAA-MM-GG.html
    py -m radar apri     # apre il giornale (http://127.0.0.1:8765), accendendo il server se serve
    py -m radar serve    # solo il server, senza aprire il browser
    py strumenti/icona.py   # rigenera radar.ico

## Come funziona

Tre parti, in quest'ordine sulla pagina: **notizie**, **repository GitHub**, **ricerca**. Il sabato e la
domenica, al posto della ricerca, **il weekend a Roma e dintorni** (guide, musica, sagre, mostre). In testata
il **meteo** del giorno (Open-Meteo). In stampa sta in 3 fogli A4: a schermo si vedono in più "Perché è qui",
i titoli originali, i temi dei repository, i "Rimasti fuori" e i pulsanti.

1. **raccolta** (`radar/fonti.py`)
   - notizie: feed RSS di testate tech, cyber e di politica digitale (EN e IT) + ricerche mirate su Google News;
     solo le ultime `notizie.ore` ore
   - GitHub: API di ricerca, repository creati negli ultimi `github.giorni` giorni, per stelle (generale + temi)
   - ricerca: feed RSS di arXiv (cs.AI, cs.LG, cs.CR), solo lavori nuovi
2. **doppioni** — SQLite in `data/radar.db`. La stessa notizia da più testate (titoli simili, anche tra
   italiano e inglese) diventa una sola, con "su N testate" e punti in più
3. **selezione** — parole chiave pesate in `profilo.toml`. Le notizie hanno tre gruppi che sono anche le
   rubriche (Governi e regole, Cybersicurezza, AI e sviluppo) ed entrano solo se toccano tecnologia o
   sicurezza; nella scelta si salta ciò che è troppo vicino a una notizia già presa
4. **MiniCPM** (`radar/llm.py`) — traduce e riassume solo ciò che è in inglese; le fonti italiane escono come sono.
   Risposte in testo semplice (`TITOLO:` / `RIASSUNTO:`): il JSON lo sbaglia spesso. Se nella traduzione
   compaiono caratteri cinesi (succede: "dei数据中心") riprova una volta, poi tiene l'originale inglese
5. **impaginazione** (`radar/giornale.py`) — apertura, spalle, "In breve", rubriche, repository, ricerca
6. **giudizi** — i pulsanti sulla pagina salvano +1/-1 nel database, per tarare profilo e soglie

## Cartelle non versionate

- `runtime/ollama/` — Ollama portabile (v0.34.4), nessuna installazione di sistema
- `runtime/models/` — i pesi (`openbmb/minicpm5:q8_0`, 1,2 GB)
- `data/`, `edizioni/`

Per rimettere in piedi il runtime su un altro PC: scaricare `ollama-windows-amd64.zip` dalle release
di Ollama in `runtime/ollama/`, poi con `OLLAMA_MODELS=runtime/models` eseguire
`ollama pull openbmb/minicpm5:q8_0`.
