# Il Radar

Giornale personale del mattino: raccoglie notizie, repository, sport, gaming e attualità, li seleziona con le
parole chiave del profilo, fa tradurre l'inglese a un traduttore locale (TranslateGemma 4B via Ollama) e li impagina
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
- **Stampa**: il pulsante *Stampa* della pagina (anche dal telefono) apre la stampa del browser. *Anteprima di
  stampa* (`?carta`) mostra i fogli A4 come usciranno.

A mano:

    py -m radar giro     # raccoglie, seleziona, traduce, scrive edizioni/AAAA-MM-GG.html e .pdf
    py -m radar apri     # apre il giornale (http://127.0.0.1:8765), accendendo il server se serve
    py -m radar serve    # solo il server, senza aprire il browser
    py strumenti/icona.py   # rigenera radar.ico

## La pagina

Testata con il meteo di San Paolo (Aeronautica Militare; Open-Meteo con il modello ICON-2I di riserva). Sotto,
due colonne per tutta l'altezza, come un quotidiano:

- **a sinistra (3/4)**: l'apertura; le notizie su AI e sviluppo con riassunto, in rubriche (Governi e regole,
  Cybersicurezza, AI e sviluppo); 5 repository GitHub con spiegazione; lo sport importante; il gaming. Sabato e
  domenica anche *Il weekend a Roma e dintorni* (guide, musica, sagre, mostre).
- **a destra (1/4)**: i titoli — In breve, Sport, Gaming, Italia, Estero, Dalla ricerca.

**Stampa: al massimo 2 fogli A4.** I fogli li costruisce lo script della pagina, non il browser. Appena la pagina
è aperta (e caricati i caratteri) lo script misura ogni articolo e lo dispone a mano nelle colonne di due fogli da
210×296 mm (2 colonne + barra dei titoli per foglio), in ordine e senza spezzare un articolo. I fogli restano
nascosti a schermo e si mostrano in stampa e nell'anteprima `?carta`, quindi anche il Ctrl+P del browser li trova
pronti. Perché non lasciar fare al browser: Firefox (il browser predefinito) non spezza una griglia o un blocco a
colonne tra due pagine e lo sposta intero sulla successiva, lasciando la prima con la sola testata; Edge e Chrome
lo spezzano. Con fogli a misura fissa non c'è niente da spezzare e il risultato è identico ovunque.

- se il flusso non sta in due fogli, l'articolo meno importante (prima lo sport e il gaming, poi le notizie)
  diventa un titolo nella barra e si riprova; i riassunti non si accorciano mai. L'articolo più forte di sport e di
  gaming è protetto: una sezione con un articolo vero non resta solo titoli
- la barra dei titoli si riempie foglio dopo foglio, con gli articoli declassati in cima a "In breve"; ogni sezione
  (sport, gaming, Italia, estero, ricerca) mantiene almeno 3 titoli: se non ci stanno, si tolgono voci da "In breve"; i titoli che non ci stanno vanno in coda alle colonne
  dell'ultimo foglio, negli spazi bianchi lasciati dagli articoli interi; quelli che non entrano nemmeno lì
  non si stampano (prima la ricerca, poi l'estero, l'Italia, lo sport)
- se le notizie stanno in un foglio solo e restano fuori al massimo 2 titoli, si stampa un foglio solo
- il margine del foglio (`@page`) è zero, così il browser non stampa titolo, data e indirizzo; i 10 mm li dà `.pagina`
- per provare la stampa nel browser dell'utente: `py strumenti/stampa_firefox.py <url> <file.pdf>` (Firefox senza
  finestra, profilo temporaneo, protocollo Marionette); `data-fogli` sulla radice della pagina dice quanti fogli,
  quanti articoli declassati e quanti titoli persi

## Come funziona

1. **raccolta** (`radar/fonti.py`)
   - notizie: feed RSS di testate tech, cyber e di politica digitale (EN e IT) + Google News mirato
   - GitHub: i 3 più seguiti dei temi del profilo, aggiornati nell'ultimo mese. Le stelle si registrano ogni
     giorno (tabella `stelle`): "vanno forte" = stelle guadagnate in 7 giorni (finché manca lo storico, la media
     dalla nascita — per i grandi repository storici è sempre lo stesso numero). Al massimo `per_tema` per tema;
     un repository già uscito non ritorna prima di `raffreddamento` giorni, altrimenti sarebbero sempre gli stessi
   - sport: OA Sport, FIDAL, Runner's World, ANSA + Google News per le gare a Roma. Importanza dal titolo (record,
     titoli, grandi eventi, atleti italiani); niente calcio. Per esteso solo se importante
   - gaming: Everyeye, IGN Italia, GameSpot, PC Gamer, Rock Paper Shotgun, Polygon, The Verge, GamesIndustry.biz,
     Push Square, Nintendo Life + Google News. Uscite, annunci, recensioni, industria e sviluppo; fuori offerte,
     guide, trucchi, anime. Per esteso solo le voci forti con un testo; le altre sono titoli in barra
   - attualità: ANSA, Il Fatto Quotidiano, ISTAT. Solo fatti avvenuti: verbo di fatto compiuto o participio
     passato, niente ipotesi, domande, sole dichiarazioni, calcio
   - ricerca: arXiv (cs.AI, cs.LG, cs.CR), solo titoli
2. **doppioni** — SQLite in `data/radar.db`. La stessa notizia da più testate (titoli simili, anche tra italiano e
   inglese) diventa una sola, con "su N testate" e punti in più
3. **selezione** — parole chiave pesate in `profilo.toml`. Per esteso solo ciò che ha un testo da riassumere:
   Google News dà solo titoli, e quelli vanno in barra
4. **modelli locali** (`radar/llm.py`) — **TranslateGemma 4B** traduce dall'inglese all'italiano i titoli e le prime
   due frasi dei testi. È fatto apposta e traduce bene; MiniCPM4.1, provato per primo, scriveva "Data centeri sono
   blind boxes" (e a volte in svedese o in cinese). Una traduzione sospetta (vuota, in ciclo, con caratteri cinesi,
   troppo lunga o troppo corta) si riprova una volta e poi resta in inglese. **MiniCPM4.1** riassume in inglese i
   README dei repository, poi li traduce TranslateGemma. Sulla scheda da 4 GB i due modelli non stanno insieme: si
   usano a blocchi (prima tutto MiniCPM, poi tutte le traduzioni). Un errore lascia in originale solo quella voce
5. **impaginazione** (`radar/giornale.py`) — a fine giro anche il PDF identico alla stampa, in `edizioni/`
6. **giudizi** — i pulsanti sulla pagina salvano +1/-1 nel database, per tarare profilo e soglie

## Personalizzare per un'altra persona

Il motore (raccolta, doppioni, selezione, impaginazione, stampa) non dipende da chi legge: cambia il profilo. Il
`profilo.toml` di questa cartella è quello di chi l'ha scritto (tecnologia e sicurezza, repository per tema, sport,
attualità, weekend a Roma), non una scelta obbligata. Cosa si tocca, dal più semplice:

1. **`profilo.toml`** — chi legge e cosa gli interessa
   - `descrizione` e `[meteo]` (città e coordinate)
   - le parole chiave con i pesi: `[notizie.norme]`, `[notizie.sicurezza]`, `[notizie.tecnologia]` (le tre rubriche
     delle notizie), `[notizie.giu]` (il rumore da spingere giù), `[ricerca.parole]`; le regole di scrittura sono
     nell'intestazione del file
   - quante voci e con quali soglie: `massimo`, `brevi`, `soglia`, `ore` in ogni sezione
   - `[github.temi]` (un tema = un filtro di ricerca GitHub), `[sport]` (discipline, importanza, atleti da seguire),
     `[gaming]` (parole che spingono su o giù, nomi grossi), `[attualita]` (verbi di fatto compiuto, ipotesi da
     scartare, argomenti da escludere), `[weekend]` (luoghi, testate locali, rubriche)
2. **`radar/fonti.py`** — le testate: gli elenchi `NOTIZIE`, `ATTUALITA`, `SPORT`, `GAMING`, `EVENTI` (nome, indirizzo del
   feed, lingua, peso) e le ricerche su Google News (`_gnews`)
3. **il codice, solo per cambiare la struttura** — i nomi delle tre rubriche delle notizie stanno in
   `radar/giornale.py` (`RUBRICHE`) e le loro chiavi in `radar/__main__.py` (`RUBRICHE_NOTIZIE`): per cambiare le
   parole chiave basta il file, per cambiare le rubriche servono due righe di codice

Una sezione senza voci quel giorno non compare. Dopo ogni modifica: `py -m radar giro` e `?carta` per controllare i fogli.

## Cartelle non versionate

- `runtime/ollama/` — Ollama portabile (v0.34.4), nessuna installazione di sistema
- `runtime/models/` — i pesi: `translategemma:4b` (3,3 GB) e `openbmb/minicpm4.1` (5 GB)
- `data/` (database, log, profili Edge), `edizioni/` (HTML e PDF di ogni giorno)

Per rimettere in piedi il runtime su un altro PC: scaricare `ollama-windows-amd64.zip` dalle release di Ollama in
`runtime/ollama/`, poi con `OLLAMA_MODELS=runtime/models` eseguire `ollama pull translategemma:4b` e
`ollama pull openbmb/minicpm4.1`.
