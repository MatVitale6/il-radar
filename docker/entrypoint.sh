#!/bin/sh
# avvia (default): Ollama + modelli + il demone del Radar (server sulla 8765 e un giro al giorno)
# giro: Ollama + modelli + un giro adesso, poi esce
# qualsiasi altra cosa (tui, aiuto...): si passa a `python3 -m radar <comando>`, senza Ollama
set -e
cd /app

case "${1:-avvia}" in
  avvia | giro) ;;
  *) exec python3 -m radar "$@" ;;
esac

mkdir -p "$OLLAMA_MODELS" "$RADAR_DATI"
ollama serve >"$RADAR_DATI/ollama.log" 2>&1 &
until ollama list >/dev/null 2>&1; do sleep 1; done

# translategemma traduce tutto l'inglese; minicpm4.1 (5 GB) spiega i repository GitHub dal README: facoltativo
# (senza, si traduce la descrizione del repository). Per averlo: -e RADAR_MODELLI="translategemma:4b openbmb/minicpm4.1"
for modello in ${RADAR_MODELLI:-translategemma:4b}; do
  ollama list | grep -q "^$modello" || { echo "scarico $modello (la prima volta ci vuole un po')"; ollama pull "$modello"; }
done

if [ "${1:-avvia}" = "giro" ]; then exec python3 -m radar giro; fi
exec python3 -m radar demone
