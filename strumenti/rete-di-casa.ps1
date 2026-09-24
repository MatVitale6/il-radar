# Apre il giornale ai dispositivi di casa (es. il telefono), e solo a loro. Va eseguito come amministratore:
#   Start-Process powershell -Verb RunAs -ArgumentList '-ExecutionPolicy Bypass -File strumenti\rete-di-casa.ps1'
#
# 1. La Wi-Fi a cui il PC è collegato ora diventa "Privata" (Windows la considerava "Pubblica": porte chiuse).
# 2. Regola del firewall: porta 8765 aperta solo sui profili "Privata" e solo alla rete locale (LocalSubnet).
#    Su una Wi-Fi pubblica (bar, treno) resta chiusa.
# Per tornare indietro:  Remove-NetFirewallRule -DisplayName 'Il Radar - giornale sulla rete di casa'

$log = Join-Path $PSScriptRoot "..\data\rete-di-casa.log"
Start-Transcript -Path $log -Force | Out-Null
try {
    $wifi = Get-NetConnectionProfile | Where-Object { $_.InterfaceAlias -eq 'Wi-Fi' }
    Set-NetConnectionProfile -InterfaceAlias 'Wi-Fi' -NetworkCategory Private
    "rete '$($wifi.Name)': ora $((Get-NetConnectionProfile -InterfaceAlias 'Wi-Fi').NetworkCategory)"

    Remove-NetFirewallRule -DisplayName 'Il Radar - giornale sulla rete di casa' -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName 'Il Radar - giornale sulla rete di casa' `
        -Description 'Giornale personale (Downloads\Ingegnere\radar) raggiungibile dai dispositivi di casa' `
        -Direction Inbound -Protocol TCP -LocalPort 8765 -RemoteAddress LocalSubnet -Profile Private -Action Allow |
        Select-Object DisplayName, Enabled, Profile, Action | Format-List
    "fatto"
} catch {
    "ERRORE: $_"
} finally {
    Stop-Transcript | Out-Null
}
