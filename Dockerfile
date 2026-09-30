# Il Radar in un solo contenitore: Ollama (per la traduzione) + il giornale. I modelli non sono nell'immagine:
# si scaricano la prima volta nel volume /dati e ci restano.
FROM ollama/ollama:0.34.4

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 tzdata \
 && rm -rf /var/lib/apt/lists/*

ENV TZ=Europe/Rome \
    RADAR_DATI=/dati \
    OLLAMA_MODELS=/dati/modelli \
    OLLAMA_HOST=127.0.0.1:11434 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app
COPY radar/ radar/
COPY profilo.esempio.toml .
COPY docker/entrypoint.sh /usr/local/bin/radar-entrypoint
RUN chmod +x /usr/local/bin/radar-entrypoint

VOLUME /dati
EXPOSE 8765
LABEL org.opencontainers.image.source="https://github.com/MatVitale6/il-radar" \
      org.opencontainers.image.description="Il Radar: giornale personale del mattino, scelto con le tue regole e pronto da stampare" \
      org.opencontainers.image.licenses="NOASSERTION"

ENTRYPOINT ["radar-entrypoint"]
CMD ["avvia"]
