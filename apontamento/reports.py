"""Relatório de dias úteis sem nenhum lançamento."""

from datetime import date

from .psoffice import Colaborador, Lancamento, dias_uteis


def periodo(lancamentos: list[Lancamento]) -> tuple[date, date]:
    datas = [l.data for l in lancamentos]
    return min(datas), max(datas)


def dias_sem_lancamento(
    colaboradores: dict[str, Colaborador],
    lancamentos: list[Lancamento],
    feriados: set[date],
    inicio: date | None = None,
    fim: date | None = None,
) -> list[list[str]]:
    """Linhas `matricula, nome, gestor, data` para cada dia útil sem lançamento (qualquer status)."""
    if inicio is None or fim is None:
        inicio, fim = periodo(lancamentos)
    lancados = {(l.matricula, l.data) for l in lancamentos}
    dias = dias_uteis(inicio, fim, feriados)
    return [
        [c.matricula, c.nome, c.gestor, d.isoformat()]
        for c in sorted(colaboradores.values(), key=lambda c: c.matricula)
        for d in dias
        if (c.matricula, d) not in lancados
    ]
