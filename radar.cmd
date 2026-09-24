@echo off
rem  radar          -> giro del mattino (lo lancia anche l'Utilita di pianificazione)
rem  radar leggi    -> apre il giornale nel browser, con i pulsanti utile / non mi interessa
cd /d "%~dp0"
if /i "%1"=="leggi" (py -m radar serve) else (py -u -m radar giro >> "%~dp0data\giri.log" 2>&1)
