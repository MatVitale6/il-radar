"""Controllo della TUI: le modifiche al profilo e un giro di menu guidato a tasti finti.

    py -m unittest discover -s tests
"""
import shutil
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
from radar import tui  # noqa: E402

ESEMPIO = (RADICE / "profilo.esempio.toml").read_text("utf-8")


def commenti(testo):
    return [r for r in testo.split("\n") if r.lstrip().startswith("#")]


class Modifiche(unittest.TestCase):
    def test_il_testo_resta_toml_e_i_commenti_restano(self):
        t = tui.imposta(ESEMPIO, "sport", "attiva", False)
        t = tui.imposta(t, "notizie", "massimo", 7)
        t = tui.imposta(t, "meteo", "citta", "Milano")
        t = tui.imposta_voce(t, "notizie.norme", "cyber*", "5")
        t = tui.imposta_voce(t, "notizie.norme", "legge", "9")
        t = tui.togli_voce(t, "notizie.norme", "leggi")
        t = tui.imposta_lista(t, "sport", "italiani", ["Sinner", "Paolini", "Castelli Romani"])
        d = tomllib.loads(t)
        self.assertIs(d["sport"]["attiva"], False)
        self.assertEqual(d["notizie"]["massimo"], 7)
        self.assertEqual(d["meteo"]["citta"], "Milano")
        self.assertEqual(d["notizie"]["norme"]["cyber*"], 5)
        self.assertEqual(d["notizie"]["norme"]["legge"], 9)
        self.assertNotIn("leggi", d["notizie"]["norme"])
        self.assertEqual(d["sport"]["italiani"], ["Sinner", "Paolini", "Castelli Romani"])
        self.assertEqual(commenti(t), commenti(ESEMPIO))                 # nessun commento perso
        self.assertIn("# pubblicate per esteso", t)                     # e quello a fine riga di massimo resta

    def test_chiave_mancante_viene_aggiunta(self):
        senza = ESEMPIO.replace("attiva = true\n", "", 1)
        self.assertIs(tomllib.loads(tui.imposta(senza, "notizie", "attiva", False))["notizie"]["attiva"], False)


class Menu(unittest.TestCase):
    """Si finge la tastiera: i tasti e le risposte a `input()` sono una lista."""

    def esegui(self, tasti, risposte=()):
        cartella = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, cartella, True)
        file = cartella / "profilo.toml"
        file.write_text(ESEMPIO, "utf-8")
        t, r = iter(tasti), iter(risposte)
        vecchi = tui._tasto, tui._riga, tui._out, tui._raw, sys.stdin
        tui._tasto, tui._riga, tui._out = lambda: next(t), lambda *a: next(r), lambda s: None
        tui._raw = lambda acceso: None                    # niente terminale vero: lo si prova a parte, con un pty
        sys.stdin = type("Tty", (), {"isatty": lambda self: True})()
        try:
            tui.avvia(file)
        finally:
            tui._tasto, tui._riga, tui._out, tui._raw, sys.stdin = vecchi
        return file

    def test_spegni_una_sezione_e_salva(self):
        # menu: Sezioni (1 giù) · Invio · 2 giù fino a "Sport" · Spazio · Esc · 4 giù fino a "Salva" · Invio · avviso
        file = self.esegui(["giu", "invio", "giu", "giu", " ", "esc", "giu", "giu", "giu", "giu", "invio", "x"])
        d = tomllib.loads(file.read_text("utf-8"))
        self.assertIs(d["sport"]["attiva"], False)
        self.assertIs(d["notizie"]["attiva"], True)
        self.assertTrue(file.with_name("profilo.toml.bak").exists())

    def test_aggiungi_una_parola_chiave(self):
        # Argomenti (2 giù) · Invio · "Governi e regole" (2 giù) · Invio · a · Esc · Esc · Salva (3 giù) · Invio · avviso
        file = self.esegui(["giu", "giu", "invio", "giu", "giu", "invio", "a", "esc", "esc",
                            "giu", "giu", "giu", "invio", "x"], ["cyber*", "5"])
        self.assertEqual(tomllib.loads(file.read_text("utf-8"))["notizie"]["norme"]["cyber*"], 5)

    def test_esci_senza_modifiche_non_scrive(self):
        file = self.esegui(["esc"])
        self.assertEqual(file.read_text("utf-8"), ESEMPIO)
        self.assertFalse(file.with_name("profilo.toml.bak").exists())


if __name__ == "__main__":
    unittest.main()
