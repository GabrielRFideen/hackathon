import unittest

from apontamento.jira import JiraClient


class TestJiraEventos(unittest.TestCase):
    def test_transicoes_no_mesmo_minuto_seguem_a_ordem_real(self):
        cliente = JiraClient("https://exemplo.atlassian.net", "a@b.c", "x")
        # O Jira devolve os históricos do mais novo ao mais antigo.
        historicos = [
            {"id": "2", "created": "2026-10-21T17:29:40.000-0300",
             "items": [{"field": "status", "fromString": "Liberado", "toString": "Em Desenvolvimento"}]},
            {"id": "1", "created": "2026-10-21T17:29:10.000-0300",
             "items": [{"field": "status", "fromString": "Backlog", "toString": "Liberado"}]},
        ]
        eventos = cliente._eventos(historicos)
        self.assertEqual([e["to"] for e in eventos], ["Liberado", "Em Desenvolvimento"])
        self.assertEqual(eventos[0]["at"], "2026-10-21T17:29")


if __name__ == "__main__":
    unittest.main()
