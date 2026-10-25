import unittest
from datetime import date, datetime

from apontamento import allocator
from apontamento.allocator import CARD_PARADO, DIVERGENCIA, LACUNA
from apontamento.config import Config
from apontamento.psoffice import Colaborador, Lancamento, dias_uteis
from apontamento.timeline import intervalos

CFG = Config()
FERIADOS = {date(2026, 10, 12)}
DIAS = dias_uteis(date(2026, 10, 9), date(2026, 10, 22), FERIADOS)
AGORA = datetime(2026, 10, 22, 18)
ANA = Colaborador("C001", "Ana", "ana@x.test", "Gestor 01", "Cliente", "ECL-01", "CLT", "Remoto")


def card(key, eventos, labels=("ECL-01",), assignee="ana@x.test", status=None):
    return {"key": key, "assignee": assignee, "labels": list(labels), "status": status,
            "changelog": [{"at": at, "field": "status", "from": de, "to": para} for at, de, para in eventos]}


def gerar(cards, lancamentos=()):
    its = [it for c in cards for it in intervalos(c, CFG.status_trabalho, AGORA)]
    return allocator.gerar({ANA.matricula: ANA}, list(lancamentos), its, DIAS, CFG)


def do_dia(res, d):
    return ([s for s in res.sugestoes if s.data == d], [a for a in res.alertas if a.data == d])


class TestAllocator(unittest.TestCase):
    def test_um_card_dia_inteiro_8h(self):
        res = gerar([card("A-1", [("2026-10-09T09:00", "To Do", "In Progress"),
                                  ("2026-10-09T18:00", "In Progress", "Done")])])
        sug, alertas = do_dia(res, date(2026, 10, 9))
        self.assertEqual([(s.projeto, s.horas) for s in sug], [("ECL-01", 8)])
        self.assertEqual(alertas, [])

    def test_varios_cards_viram_reporte_unico_pela_uniao(self):
        res = gerar([
            card("A-1", [("2026-10-09T09:00", "To Do", "In Progress"), ("2026-10-09T11:00", "In Progress", "Done")]),
            card("A-2", [("2026-10-09T10:00", "To Do", "In Progress"), ("2026-10-09T15:00", "In Progress", "Done")]),
            card("A-3", [("2026-10-09T15:00", "To Do", "In Progress"), ("2026-10-09T18:00", "In Progress", "Done")]),
        ])
        sug, _ = do_dia(res, date(2026, 10, 9))
        self.assertEqual(len(sug), 1)
        self.assertEqual(sug[0].horas, 8)
        self.assertEqual([o.split()[0] for o in sug[0].origem], ["A-1", "A-2", "A-3"])

    def test_fim_de_semana_e_feriado_sem_horas(self):
        res = gerar([card("A-1", [("2026-10-09T09:00", "To Do", "In Progress"),
                                  ("2026-10-13T18:00", "In Progress", "Done")])])
        self.assertEqual([s.data for s in res.sugestoes], [date(2026, 10, 9), date(2026, 10, 13)])

    def test_dia_ja_lancado_nao_gera_reporte_so_alerta_de_divergencia(self):
        res = gerar([card("A-1", [("2026-10-14T09:00", "To Do", "In Progress"),
                                  ("2026-10-14T18:00", "In Progress", "Done")])],
                    [Lancamento("C001", date(2026, 10, 14), "ECL-01", 6, "APROVADO")])
        sug, alertas = do_dia(res, date(2026, 10, 14))
        self.assertEqual(sug, [])
        self.assertEqual([a.tipo for a in alertas], [DIVERGENCIA])

    def test_dia_parcial_nao_completa_e_alerta_lacuna(self):
        res = gerar([card("A-1", [("2026-10-13T14:00", "To Do", "In Progress"),
                                  ("2026-10-13T18:00", "In Progress", "Done")])])
        sug, alertas = do_dia(res, date(2026, 10, 13))
        self.assertEqual([s.horas for s in sug], [4])
        self.assertEqual([(a.tipo, a.canais) for a in alertas], [(LACUNA, ("email", "gchat"))])

    def test_dia_sem_jira_e_sem_lancamento_alerta_lacuna(self):
        sug, alertas = do_dia(gerar([]), date(2026, 10, 9))
        self.assertEqual(sug, [])
        self.assertEqual([a.tipo for a in alertas], [LACUNA])

    def test_card_parado_3_dias_apontamento_feito_e_alerta_gchat(self):
        res = gerar([card("A-1", [("2026-10-15T09:00", "To Do", "In Progress")], status="In Progress")])
        self.assertEqual([s.data for s in res.sugestoes],
                         [date(2026, 10, d) for d in (15, 16, 19, 20, 21, 22)])
        parados = [a for a in res.alertas if a.tipo == CARD_PARADO]
        self.assertEqual([a.data for a in parados], [date(2026, 10, d) for d in (20, 21, 22)])
        self.assertTrue(all(a.canais == ("gchat",) for a in parados))

    def test_labels_diferentes_usa_a_de_mais_horas(self):
        cards = [
            card("A-1", [("2026-10-09T09:00", "To Do", "In Progress"), ("2026-10-09T11:00", "In Progress", "Done")],
                 labels=("ECL-02",)),
            card("A-2", [("2026-10-09T11:00", "To Do", "In Progress"), ("2026-10-09T18:00", "In Progress", "Done")],
                 labels=("ECL-03",)),
        ]
        # sem as labels entre os projetos conhecidos → fallback para o projeto do colaborador
        self.assertEqual([(s.projeto, s.horas) for s in gerar(cards).sugestoes], [("ECL-01", 8)])

        conhecidos = [Lancamento("C002", date(2026, 10, 9), p, 4, "APROVADO") for p in ("ECL-02", "ECL-03")]
        self.assertEqual([(s.projeto, s.horas) for s in gerar(cards, conhecidos).sugestoes], [("ECL-03", 8)])

    def test_card_sem_assignee_e_ignorado(self):
        res = gerar([card("A-1", [("2026-10-09T09:00", "To Do", "In Progress"),
                                  ("2026-10-09T18:00", "In Progress", "Done")], assignee=None)])
        self.assertEqual(res.sugestoes, [])

    def test_arredondamento_em_blocos_de_2h(self):
        self.assertEqual([allocator.arredondar(h * 60, CFG) for h in (0.5, 1, 3, 5, 9)], [0, 2, 4, 6, 8])


    def test_email_jira_liga_card_ao_colaborador(self):
        bia = Colaborador("C002", "Bia", "bia@contato.test", "Gestor 01", "Cliente", "ECL-01", "PJ", "Remoto",
                          email_jira="bia@jira.test")
        c = card("B-1", [("2026-10-09T09:00", "To Do", "In Progress"), ("2026-10-09T18:00", "In Progress", "Done")],
                 assignee="bia@jira.test")
        its = intervalos(c, CFG.status_trabalho, AGORA)
        res = allocator.gerar({bia.matricula: bia}, [], its, DIAS, CFG)
        self.assertEqual([(s.matricula, s.horas) for s in res.sugestoes], [("C002", 8)])
        self.assertEqual(res.ignorados, [])


if __name__ == "__main__":
    unittest.main()
