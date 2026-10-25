"""Leitura e escrita dos CSVs do PSOffice (integração somente por CSV)."""

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


@dataclass(frozen=True)
class Colaborador:
    matricula: str
    nome: str
    email: str
    gestor: str
    cliente: str
    projeto: str
    regime: str
    local: str
    email_jira: str = ""  # opcional: e-mail no Jira, quando difere do e-mail de contato

    @property
    def conta_jira(self) -> str:
        return (self.email_jira or self.email).lower()


@dataclass(frozen=True)
class Lancamento:
    matricula: str
    data: date
    projeto: str
    horas: int
    status: str


def _linhas(caminho: Path) -> list[dict[str, str]]:
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def ler_colaboradores(caminho: Path) -> dict[str, Colaborador]:
    return {r["matricula"]: Colaborador(**r) for r in _linhas(caminho)}


def ler_lancamentos(caminho: Path) -> list[Lancamento]:
    return [
        Lancamento(r["matricula"], date.fromisoformat(r["data"]), r["projeto"], int(r["horas"]), r["status"])
        for r in _linhas(caminho)
    ]


def ler_feriados(caminho: Path) -> set[date]:
    return {date.fromisoformat(r["data"]) for r in _linhas(caminho)}


def dias_uteis(inicio: date, fim: date, feriados: set[date]) -> list[date]:
    """Segunda a sexta entre `inicio` e `fim` (inclusive), excluindo feriados da planilha."""
    dias, d = [], inicio
    while d <= fim:
        if d.weekday() < 5 and d not in feriados:
            dias.append(d)
        d += timedelta(days=1)
    return dias


def escrever_csv(caminho: Path, cabecalho: list[str], linhas: list[list]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)  # CRLF, como os CSVs do PSOffice
        w.writerow(cabecalho)
        w.writerows(linhas)
