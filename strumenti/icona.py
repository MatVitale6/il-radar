"""Rigenera radar.ico: la R gotica della testata su un foglio con doppio filetto.

    py strumenti/icona.py

Disegna in un canvas (Edge headless, per avere il font della testata) a più dimensioni esatte
e impacchetta i PNG in un .ico, che Windows usa per il collegamento sul desktop.
"""
import base64
import re
import struct
import subprocess
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
MISURE = [256, 64, 48, 32, 24, 16]

PAGINA = """<!doctype html><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=UnifrakturMaguntia&display=block" rel="stylesheet">
<pre id="out"></pre>
<script>
(async () => {
  await document.fonts.load('400 100px "UnifrakturMaguntia"');
  const out = [];
  for (const s of MISURE) {
    const c = document.createElement("canvas"); c.width = c.height = s;
    const x = c.getContext("2d");
    const bordo = Math.max(1, Math.round(s * 0.05)), m = bordo / 2, r = s * 0.16;
    x.beginPath(); x.roundRect(m, m, s - bordo, s - bordo, r);
    x.fillStyle = "#fff"; x.fill(); x.lineWidth = bordo; x.strokeStyle = "#111"; x.stroke();
    if (s >= 48) {                       // secondo filetto, come sotto la testata
      const i = s * 0.12;
      x.beginPath(); x.roundRect(i, i, s - 2 * i, s - 2 * i, r * 0.5);
      x.lineWidth = Math.max(1, s * 0.012); x.stroke();
    }
    x.fillStyle = "#111"; x.textAlign = "center"; x.textBaseline = "alphabetic";
    x.font = `400 ${s * (s >= 48 ? 0.66 : 0.8)}px "UnifrakturMaguntia"`;
    const mis = x.measureText("R");
    const alto = mis.actualBoundingBoxAscent + mis.actualBoundingBoxDescent;
    x.fillText("R", s / 2, s / 2 + alto / 2 - mis.actualBoundingBoxDescent);
    out.push(s + ":" + c.toDataURL("image/png").split(",")[1]);
  }
  document.getElementById("out").textContent = out.join("\\n");
})();
</script>"""


def main():
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / "icona.html"
        html.write_text(PAGINA.replace("MISURE", str(MISURE)), "utf-8")
        dom = subprocess.run([EDGE, "--headless=new", "--disable-gpu", f"--user-data-dir={tmp}\\profilo",
                              "--virtual-time-budget=8000", "--dump-dom", html.as_uri()],
                             capture_output=True, text=True, timeout=120).stdout
    png = {int(s): base64.b64decode(b) for s, b in re.findall(r"(\d+):([A-Za-z0-9+/=]+)", dom)}
    assert sorted(png) == sorted(MISURE), f"misure mancanti: {set(MISURE) - set(png)}"

    # formato ICO: intestazione, una voce di 16 byte per immagine, poi i PNG uno dopo l'altro
    intestazione = struct.pack("<HHH", 0, 1, len(MISURE))
    voci, dati, scarto = b"", b"", 6 + 16 * len(MISURE)
    for s in MISURE:
        voci += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(png[s]), scarto + len(dati))
        dati += png[s]
    (RADICE / "radar.ico").write_bytes(intestazione + voci + dati)
    for s in (256, 32, 16):                 # anteprime da guardare
        (RADICE / "data" / f"icona-{s}.png").write_bytes(png[s])
    print("scritto", RADICE / "radar.ico")


main()
