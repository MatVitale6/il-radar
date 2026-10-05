# Il Radar

Un giornale personale del mattino. Ogni giorno raccoglie notizie, repository GitHub, sport, gaming e attualità, sceglie
ciò che ti riguarda con regole che scrivi tu, traduce l'inglese con un modello che gira sul tuo computer e
impagina tutto come la prima pagina di un quotidiano in bianco e nero: **due fogli A4, pronti da stampare**.

- **Finisce.** Un numero fisso di voci, due fogli. Ciò che resta fuori è elencato in fondo, non nascosto.
- **Dice perché.** Ogni voce porta le parole che l'hanno fatta entrare: una selezione che si spiega si può correggere.
- **Niente esce dal computer.** La traduzione gira in locale (TranslateGemma via Ollama): nessun testo va a un
  servizio di intelligenza artificiale esterno.
- **Su misura.** Città, sezioni, argomenti e fonti sono un file di configurazione, e c'è una TUI per cambiarli.

Come è fatto e perché: <https://matteovitale.dev/progetti/radar>  ·  Licenza: [MIT](LICENSE)

## Installazione (Docker)

```
docker run -d --name radar -p 8765:8765 -v radar-dati:/dati ghcr.io/matvitale6/il-radar:latest
```

Apri <http://localhost:8765>. La prima volta il contenitore scarica il traduttore (TranslateGemma, 3,3 GB) e prepara la
prima edizione: ci vogliono da pochi minuti a mezz'ora, secondo il computer. Poi un giro ogni mattina alle 07:30.

| Cosa | Come |
|---|---|
| L'ora del giro | `-e RADAR_ORA=06:45` |
| Il fuso orario | `-e TZ=Europe/Rome` (è il predefinito) |
| La scheda NVIDIA | `--gpus all` (ci vuole il NVIDIA Container Toolkit) |
| MiniCPM per spiegare i repository | `-e RADAR_MODELLI="translategemma:4b openbmb/minicpm4.1"` (5 GB in più; senza, si traduce la descrizione del repository) |
| Con `docker compose` | `docker compose up -d`, con il `docker-compose.yml` di questa cartella |
| Fare un giro subito | `docker exec radar python3 -m radar giro` |

Tutto ciò che è tuo sta nel volume `radar-dati`: il profilo, il database, le edizioni, i modelli.

**Attenzione alla rete.** Il giornale non ha password: `-p 8765:8765` lo apre a chiunque sia sulla tua rete. Per tenerlo
solo su questo computer usa `-p 127.0.0.1:8765:8765`; per leggerlo dal telefono in casa lascia `-p 8765:8765` e vai su
`http://<indirizzo-del-computer>:8765`. Non esporlo su una rete pubblica.

L'immagine è per processori amd64; su un Mac con Apple Silicon Docker la emula, ed è lento.

## Personalizzalo con la TUI

```
docker exec -it radar python3 -m radar tui
```

Un menu a tastiera (frecce, Invio, Esc; Spazio per accendere e spegnere) per cambiare:

- **dove abiti**, per il tempo del giorno: scrivi la città e la scegli dall'elenco
- **le sezioni**: accese o spente, e quante voci per ciascuna
- **gli argomenti**: le parole che fanno entrare una notizia, con il loro peso (anche negativo, per spingere giù il
  rumore). Per sapere come si scrivono, l'intestazione di `profilo.esempio.toml` ha le regole
- **i repository GitHub**: i temi che segui
- **le liste**: gli atleti italiani da seguire, i luoghi del weekend

Il profilo è il file `profilo.toml` nel volume dei dati. La TUI lo modifica riga per riga, quindi i commenti restano; scrive
solo se scegli *Salva*, e il vecchio resta in `profilo.toml.bak`. Il cambiamento vale dal giro successivo.

Le testate, cioè i feed da cui si legge, non sono nel profilo ma in `radar/fonti.py` (vedi più sotto).

## Senza Docker

Servono Python 3.11 o più recente e [Ollama](https://ollama.com). Nessun pacchetto da installare: solo la libreria standard.

```
ollama pull translategemma:4b
python -m radar tui       # configurare il proprio radar
python -m radar giro      # raccoglie, sceglie, traduce e impagina l'edizione di oggi (in edizioni/)
python -m radar apri      # apre il giornale nel browser
```

Su Windows il comando è `py -m radar ...`. I dati (database, edizioni, profilo) stanno nella cartella del progetto, o dove
indica la variabile `RADAR_DATI`. Per un giro ogni mattina usa l'Utilità di pianificazione di Windows o `cron`; per tenere il
giornale sempre acceso e fare il giro da solo, `python -m radar demone`.

La stampa dal browser è già pronta: il pulsante *Stampa* della pagina, o *Anteprima di stampa* (`?carta`) per vedere i
due fogli come usciranno.

## Com'è la pagina

Testata con il tempo del giorno (Aeronautica Militare in Italia, Open-Meteo altrove). Sotto, due colonne per tutta
l'altezza, come un quotidiano:

- **a sinistra (3/4)**: l'apertura; le notizie su AI e sviluppo con riassunto, in rubriche (Governi e regole,
  Cybersicurezza, AI e sviluppo); i repository GitHub con una spiegazione; lo sport importante; il gaming; nel weekend,
  se la accendi, l'agenda della tua città
- **a destra (1/4)**: i titoli, cioè In breve, Sport, Gaming, Bandi e concorsi, Italia, Estero, Dalla ricerca

**Stampa: al massimo 2 fogli A4.** I fogli li costruisce lo script della pagina, non il browser. Appena la pagina è
aperta (e caricati i caratteri) lo script misura ogni articolo e lo dispone a mano nelle colonne di due fogli da
210×296 mm (2 colonne + barra dei titoli per foglio), in ordine e senza spezzare un articolo. I fogli restano nascosti a
schermo e si mostrano in stampa e nell'anteprima `?carta`, quindi anche il Ctrl+P del browser li trova pronti. Perché non
lasciar fare al browser: Firefox non spezza una griglia o un blocco a colonne tra due pagine e lo sposta intero sulla
successiva, lasciando la prima con la sola testata; Edge e Chrome lo spezzano. Con fogli a misura fissa non c'è niente da
spezzare e il risultato è identico ovunque.

- se il flusso non sta in due fogli, l'articolo meno importante (prima lo sport e il gaming, poi le notizie) diventa un
  titolo nella barra e si riprova; i riassunti non si accorciano mai. L'articolo più forte di sport e di gaming è protetto
- la barra dei titoli si riempie foglio dopo foglio, con gli articoli declassati in cima a "In breve"; ogni sezione (sport,
  gaming, Italia, estero, ricerca) mantiene almeno 3 titoli; quelli che non ci stanno vanno in coda alle colonne
  dell'ultimo foglio, negli spazi bianchi lasciati dagli articoli interi, e quelli che non entrano nemmeno lì non si stampano
- se le notizie stanno in un foglio solo e restano fuori al massimo 2 titoli, si stampa un foglio solo
- il margine del foglio (`@page`) è zero, così il browser non stampa titolo, data e indirizzo; i 10 mm li dà `.pagina`

## Come funziona

1. **raccolta** (`radar/fonti.py`)
   - notizie: feed RSS di testate tech, cyber e di politica digitale (inglese e italiano) + Google News mirato
   - GitHub: i più seguiti dei temi del profilo, aggiornati nell'ultimo mese. Le stelle si registrano ogni giorno (tabella
     `stelle`): "vanno forte" = stelle guadagnate in 7 giorni (finché manca lo storico, la media dalla nascita). Al
     massimo `per_tema` per tema; un repository già uscito non ritorna prima di `raffreddamento` giorni
   - sport: OA Sport, FIDAL, Runner's World, ANSA + Google News per le gare a Roma. Importanza dal titolo (record, titoli,
     grandi eventi, atleti italiani); niente calcio. Per esteso solo se importante
   - gaming: Everyeye, IGN Italia, GameSpot, PC Gamer, Rock Paper Shotgun, Polygon, The Verge, GamesIndustry.biz, Push
     Square, Nintendo Life + Google News. Fuori offerte, guide, trucchi, anime
   - attualità: ANSA, Il Fatto Quotidiano, ISTAT. Solo fatti avvenuti: verbo di fatto compiuto o participio passato,
     niente ipotesi, domande, sole dichiarazioni, calcio
   - bandi e concorsi: Concorsando e ricerche mirate su Google News (concorsi per funzionari informatici, avvisi e incarichi
     per ingegneri informatici, anche a Roma e nel Lazio). Entra solo ciò che nel titolo parla di informatica/ICT/ingegneria
     ed è un'offerta aperta: quiz, graduatorie ed esiti restano fuori. Un bando esce una volta sola. Solo titoli
   - ricerca: arXiv (cs.AI, cs.LG, cs.CR), solo titoli
2. **doppioni** — SQLite in `data/radar.db`. La stessa notizia da più testate (titoli simili, anche tra italiano e
   inglese) diventa una sola, con "su N testate" e punti in più
3. **selezione** — parole chiave pesate in `profilo.toml`. Per esteso solo ciò che ha un testo da riassumere: Google News
   dà solo titoli, e quelli vanno in barra
4. **modelli locali** (`radar/llm.py`) — **TranslateGemma 4B** traduce dall'inglese all'italiano i titoli e le prime due
   frasi dei testi. Una traduzione sospetta (vuota, in ciclo, con caratteri cinesi, troppo lunga o troppo corta) si
   riprova una volta e poi resta in inglese. **MiniCPM4.1**, facoltativo, riassume in inglese i README dei repository, poi
   li traduce TranslateGemma. Sulla scheda da 4 GB i due modelli non stanno insieme: si usano a blocchi
5. **impaginazione** (`radar/giornale.py`) — a fine giro, se c'è un Chromium/Chrome/Edge, anche il PDF identico alla stampa
6. **giudizi** — i pulsanti ▲ e ▼ sulla pagina salvano un giudizio nel database, per tarare profilo e soglie

## Personalizzare a fondo

La TUI copre quello che serve quasi sempre. Per il resto, dal più semplice:

1. **`profilo.toml`** — tutto ciò che la TUI cambia, e di più: `[giornale]`, le soglie (`soglia`, `ore`), i gruppi di
   parole di ogni sezione, `[sport]` (discipline, importanza), `[gaming]`, `[attualita]` (verbi di fatto compiuto, ipotesi da
   scartare, argomenti da escludere), `[weekend]` (luoghi, testate locali). Ogni sezione ha `attiva = true/false`
2. **`radar/fonti.py`** — le testate: gli elenchi `NOTIZIE`, `ATTUALITA`, `SPORT`, `GAMING`, `EVENTI` (nome, indirizzo del
   feed, lingua, peso) e le ricerche su Google News (`_gnews`). Sono in Python perché sono poche righe; in Docker
   significa ricostruire l'immagine (`docker build -t il-radar .`)
3. **il codice, solo per cambiare la struttura** — i nomi delle tre rubriche delle notizie stanno in `radar/giornale.py`
   (`RUBRICHE`) e le loro chiavi in `radar/__main__.py` (`RUBRICHE_NOTIZIE`)

Una sezione senza voci quel giorno non compare. Dopo ogni modifica: un giro e `?carta` per controllare i fogli.
I test: `python -m unittest discover -s tests`.

## Come lo uso io su Windows

Non serve per usarlo: sono gli strumenti che ho messo intorno a una installazione senza Docker.

- **Icona sul desktop** (`radar.ico`, `strumenti/icona.py`): apre il giornale e, se il server è spento, lo riaccende
- **All'accesso a Windows**: un collegamento nella cartella Esecuzione automatica (`shell:startup`) fa partire
  `pyw -m radar serve`, senza finestre
- **Il giro del mattino**: l'Utilità di pianificazione lancia `radar.cmd giro` ogni giorno; il log è in `data/giri.log`
- **Dal telefono**, sulla stessa Wi-Fi: `strumenti/rete-di-casa.ps1` (da amministratore) imposta la rete di casa come
  "Privata" e apre la porta 8765 solo alle reti private e alla rete locale
- **Provare la stampa in Firefox**: `strumenti/stampa_firefox.py <url> <file.pdf>`, senza finestra

## Da sapere

- Il Radar legge feed RSS, Google News e le API pubbliche di GitHub e di Open-Meteo, pensati per la lettura personale: è
  uno strumento per **leggere** le notizie, non per ripubblicarle. Il giornale che produce contiene riassunti e titoli di
  testate altrui, che restano dei loro autori: non metterlo online.
- Il tempo in Italia viene dall'indirizzo che usa il sito dell'Aeronautica Militare, che non è un'API pubblica
  documentata e può cambiare; se non risponde, si passa a Open-Meteo.
- Il modello locale traduce, non giudica: nei primi test sbagliava troppo nel dire se una notizia fosse pertinente, e
  per questo la selezione è fatta da regole.
