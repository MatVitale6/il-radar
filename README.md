# Il Radar

Giornale personale del mattino: raccoglie notizie, repository, sport e attualità, li seleziona con le parole
chiave del profilo, fa tradurre e riassumere l'inglese a un modello locale (MiniCPM4.1 via Ollama) e li impagina
come un quotidiano in bianco e nero, stampabile in 2 fogli A4.

Solo libreria standard Python. Niente testo esce dal PC.

## Uso

- **Icona "Il Radar" sul desktop** → apre il giornale nel browser (se il server è spento lo riaccende).
- **All'accesso a Windows** il collegamento `Il Radar (server)` nella cartella Esecuzione automatica
  (`shell:startup`) accende il server in background, senza finestre. Per non farlo partire: cancella quel collegamento.
- **Il giro del mattino** lo lancia ogni giorno alle 07:30 l'attività pianificata "Il Radar" con `radar.cmd giro`;
  log in `data/giri.log`. Il server acceso mostra da solo l'edizione nuova.
- **Dal telefono** (stessa Wi-Fi): `http://192.168.1.6:8765` — l'indirizzo del PC in casa (se cambia: `ipconfig`,
  voce Wi-Fi). Perché il telefono arrivi al PC: server su `0.0.0.0` + `strumenti/rete-di-casa.ps1` (da
  amministratore: Wi-Fi di casa "Privata" e porta 8765 aperta solo sulle reti private e alla rete locale). Con
  NordVPN attiva serve l'opzione che lascia visibili i dispositivi della rete locale.
- **Stampa**: il pulsante *Stampa* della pagina (anche dal telefono) passa dall'anteprima di stampa e poi apre la
  stampa del browser. *Anteprima di stampa* (`?carta`) mostra i due fogli come usciranno.

A mano:

    py -m radar giro     # raccoglie, seleziona, traduce, scrive edizioni/AAAA-MM-GG.html e .pdf
    py -m radar apri     # apre il giornale (http://127.0.0.1:8765), accendendo il server se serve
    py -m radar serve    # solo il server, senza aprire il browser
    py strumenti/icona.py   # rigenera radar.ico

## La pagina

Testata con il meteo di San Paolo (Aeronautica Militare; Open-Meteo con il modello ICON-2I di riserva). Sotto,
due colonne per tutta l'altezza, come un quotidiano:

- **a sinistra (3/4)**: l'apertura; le notizie su AI e sviluppo con riassunto, in rubriche (Governi e regole,
  Cybersicurezza, AI e sviluppo); i repository GitHub con spiegazione; lo sport importante. Sabato e domenica
  anche *Il weekend a Roma e dintorni* (guide, musica, sagre, mostre).
- **a destra (1/4)**: i titoli — In breve, Italia, Estero, Sport, Dalla ricerca.

**Sempre 2 fogli.** Sulla carta (stampa e anteprima) uno script misura il giornale nel formato del foglio e,
finché supera i due fogli: se è più lunga la colonna principale, l'articolo più debole (prima lo sport, poi le
notizie) diventa un titolo in barra; se è più lunga la barra, si tolgono i titoli dal fondo (ricerca, attualità,
sport, brevi). I riassunti non si accorciano mai. In stampa non compaiono le intestazioni del browser: il margine
del foglio è zero e i 10 mm li dà il giornale stesso, ripetuti su ogni pagina (`box-decoration-break: clone`).
In `giornale.py` le regole della carta (`CARTA`) sono scritte una volta e valgono sia in `@media print` sia sotto
`html.carta`.

## Come funziona

1. **raccolta** (`radar/fonti.py`)
   - notizie: feed RSS di testate tech, cyber e di politica digitale (EN e IT) + Google News mirato
   - GitHub: i più seguiti di ogni tema del profilo, aggiornati nell'ultimo mese. Le stelle si registrano ogni
     giorno (tabella `stelle`): "vanno forte" = stelle guadagnate in 7 giorni (finché manca lo storico, la media
     dalla nascita). Al massimo `per_tema` per tema; ripetizioni ammesse
   - sport: OA Sport, FIDAL, Runner's World, ANSA + Google News per le gare a Roma. Importanza dal titolo (record,
     titoli, grandi eventi, atleti italiani); niente calcio. Per esteso solo se importante
   - attualità: ANSA, Il Fatto Quotidiano, ISTAT. Solo fatti avvenuti: verbo di fatto compiuto o participio
     passato, niente ipotesi, domande, sole dichiarazioni, calcio
   - ricerca: arXiv (cs.AI, cs.LG, cs.CR), solo titoli
2. **doppioni** — SQLite in `data/radar.db`. La stessa notizia da più testate (titoli simili, anche tra italiano e
   inglese) diventa una sola, con "su N testate" e punti in più
3. **selezione** — parole chiave pesate in `profilo.toml`. Per esteso solo ciò che ha un testo da riassumere:
   Google News dà solo titoli, e quelli vanno in barra
4. **MiniCPM** (`radar/llm.py`) — traduce e riassume solo l'inglese; spiega i repository dal README. Testo semplice
   (il JSON lo sbaglia spesso), tetto di lunghezza, penalità per le ripetizioni. Se scrive caratteri cinesi o va
   in ciclo riprova una volta, poi resta l'originale. Un errore lascia in originale solo quella voce
5. **impaginazione** (`radar/giornale.py`) — a fine giro anche il PDF identico alla stampa, in `edizioni/`
6. **giudizi** — i pulsanti sulla pagina salvano +1/-1 nel database, per tarare profilo e soglie

## Cartelle non versionate

- `runtime/ollama/` — Ollama portabile (v0.34.4), nessuna installazione di sistema
- `runtime/models/` — i pesi (`openbmb/minicpm4.1`, 5 GB)
- `data/` (database, log, profili Edge), `edizioni/` (HTML e PDF di ogni giorno)

Per rimettere in piedi il runtime su un altro PC: scaricare `ollama-windows-amd64.zip` dalle release di Ollama in
`runtime/ollama/`, poi con `OLLAMA_MODELS=runtime/models` eseguire `ollama pull openbmb/minicpm4.1`.
