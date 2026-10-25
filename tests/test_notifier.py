import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from apontamento import notifier
from apontamento.allocator import CARD_PARADO, LACUNA, Alerta, Resultado, Sugestao
from apontamento.config import Config
from apontamento.psoffice import Colaborador

ANA = Colaborador("C001", "Ana", "ana@x.test", "Gestor 01", "Cliente", "ECL-01", "CLT", "Remoto")


class TestNotifier(unittest.TestCase):
    def setUp(self):
        self.res = Resultado(
            sugestoes=[Sugestao("C001", date(2026, 10, 20), "ECL-01", 8, ["A-1 (09h–12h, 13h–18h)"])],
            alertas=[Alerta("C001", date(2026, 10, 9), LACUNA, "Sem lançamento e sem movimentação no Jira"),
                     Alerta("C001", date(2026, 10, 20), CARD_PARADO, "A-1 parado desde 15/10")],
        )
        self.lacunas = [["C001", "Ana", "Gestor 01", "2026-10-09"], ["C001", "Ana", "Gestor 01", "2026-10-20"]]
        self.msgs = notifier.montar(self.res, {"C001": ANA}, self.lacunas, Config(email_rh="rh@x.test"))

    def test_card_parado_so_no_gchat(self):
        por_canal = {(m.canal, m.destinatario): m for m in self.msgs}
        self.assertIn("parado", por_canal[("gchat", "ana@x.test")].corpo)
        self.assertNotIn("parado", por_canal[("email", "ana@x.test")].corpo)

    def test_consolidado_vai_so_para_o_rh(self):
        rh = [m for m in self.msgs if m.destinatario == "rh@x.test"]
        self.assertEqual([m.canal for m in rh], ["email"])
        self.assertIn("C001 Ana (Gestor 01): 2 dia(s)", rh[0].corpo)

    def test_outbox_grava_email_e_payload_do_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier.enviar(self.msgs, Path(tmp))
            payload = json.loads((Path(tmp) / "gchat/ana@x.test.json").read_text(encoding="utf-8"))
            self.assertIn("8h em ECL-01", payload["text"])
            self.assertTrue((Path(tmp) / "email/rh@x.test.eml").exists())


if __name__ == "__main__":
    unittest.main()
