import unittest
from pathlib import Path

from apontamento import psoffice, reports

RAIZ = Path(__file__).resolve().parent.parent


class TestDiasSemLancamento(unittest.TestCase):
    def test_igual_ao_esperado(self):
        colaboradores = psoffice.ler_colaboradores(RAIZ / "colaboradores.csv")
        lancamentos = psoffice.ler_lancamentos(RAIZ / "lancamentos.csv")
        feriados = psoffice.ler_feriados(RAIZ / "feriados.csv")

        obtido = reports.dias_sem_lancamento(colaboradores, lancamentos, feriados)

        with open(RAIZ / "esperado/dias_sem_lancamento.csv", encoding="utf-8") as f:
            esperado = [linha.strip().split(",") for linha in f.readlines()[1:]]
        self.assertEqual(len(obtido), 61)
        self.assertEqual(obtido, esperado)


if __name__ == "__main__":
    unittest.main()
