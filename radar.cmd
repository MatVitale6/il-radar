@echo off
rem  doppio clic    -> apre il giornale nel browser (tieni aperta questa finestra mentre leggi)
rem  radar giro     -> giro del mattino (lo lancia l'Utilita di pianificazione)
cd /d "%~dp0"
if /i "%1"=="giro" (py -u -m radar giro >> "%~dp0data\giri.log" 2>&1) else (
  echo Il Radar e' aperto nel browser. Chiudi questa finestra quando hai finito di leggere.
  py -m radar serve
)
