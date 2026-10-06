@echo off
rem  doppio clic    -> apre il giornale (stesso effetto dell'icona sul desktop; nessuna finestra resta aperta)
rem  radar giro     -> giro del mattino (lo lancia l'Utilita di pianificazione)
cd /d "%~dp0"
if /i "%1"=="giro" (py -u -m radar giro %2 >> "%~dp0data\giri.log" 2>&1) else (start "" pyw -m radar apri)
