"""Intervalos do Jira → um reporte único por colaborador por dia, mais os alertas."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from .config import Config
from .psoffice import Colaborador, Lancamento
from .timeline import Intervalo

LACUNA = "lacuna"
DIVERGENCIA = "divergencia"
CARD_PARADO = "card_parado"

CANAIS = {
    LACUNA: ("email", "gchat"),
    DIVERGENCIA: ("email", "gchat"),
    CARD_PARADO: ("gchat",),
}


@dataclass
class Sugestao:
    matricula: str
    data: date
    projeto: str
    horas: int
    origem: list[str]  # ex.: ["ECL-101 (09h–11h)", ...]
    status: str = "PENDENTE"


@dataclass
class Alerta:
    matricula: str
    data: date
    tipo: str
    mensagem: str

    @property
    def canais(self) -> tuple[str, ...]:
        return CANAIS[self.tipo]


@dataclass
class Resultado:
    sugestoes: list[Sugestao] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)
    ignorados: list[str] = field(default_factory=list)


@dataclass
class _Dia:
    """Trechos de trabalho de um colaborador num dia útil, já recortados pelo expediente."""
    trechos: list[tuple[datetime, datetime, Intervalo]] = field(default_factory=list)

    def minutos(self) -> int:
        total, fim_atual = 0, None
        for ini, fim, _ in sorted(self.trechos, key=lambda t: t[0]):
            if fim_atual is not None and ini < fim_atual:
                ini = fim_atual
            if fim > ini:
                total += int((fim - ini).total_seconds() // 60)
                fim_atual = fim
        return total


def arredondar(minutos: int, cfg: Config) -> int:
    """Arredonda para blocos de `bloco_horas` (meio bloco para cima), limitado a `horas_dia`."""
    bloco = cfg.bloco_horas * 60
    return min((minutos + bloco // 2) // bloco * cfg.bloco_horas, cfg.horas_dia)


def _hh(dt: datetime) -> str:
    return f"{dt.hour:02d}h" if dt.minute == 0 else f"{dt.hour:02d}h{dt.minute:02d}"


def _recortar(intervalos: list[Intervalo], dias: list[date], cfg: Config) -> dict[tuple[str, date], _Dia]:
    por_dia: dict[tuple[str, date], _Dia] = defaultdict(_Dia)
    for it in intervalos:
        for d in (d for d in dias if it.inicio.date() <= d <= it.fim.date()):
            for j_ini, j_fim in cfg.jornada:
                ini = max(it.inicio, datetime.combine(d, j_ini))
                fim = min(it.fim, datetime.combine(d, j_fim))
                if fim > ini:
                    por_dia[(it.email, d)].trechos.append((ini, fim, it))
    return por_dia


def _projeto(dia: _Dia, colaborador: Colaborador, projetos: set[str]) -> str:
    """Label (código de projeto) com mais minutos no dia; sem label conhecida, o projeto do colaborador."""
    minutos: dict[str, float] = defaultdict(float)
    for ini, fim, it in dia.trechos:
        for label in it.labels:
            if label in projetos:
                minutos[label] += (fim - ini).total_seconds()
    if not minutos:
        return colaborador.projeto
    return min(minutos, key=lambda l: (-minutos[l], l))


def _origem(dia: _Dia) -> list[str]:
    por_card: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    for ini, fim, it in sorted(dia.trechos, key=lambda t: t[0]):
        por_card[it.card].append((ini, fim))
    return [f"{card} ({', '.join(f'{_hh(i)}–{_hh(f)}' for i, f in trechos)})"
            for card, trechos in por_card.items()]


def _dias_parado(it: Intervalo, d: date, dias: list[date]) -> int:
    """Dias úteis decorridos desde a última movimentação do card até `d` (inclusive)."""
    return sum(1 for x in dias if it.inicio.date() < x <= d)


def gerar(
    colaboradores: dict[str, Colaborador],
    lancamentos: list[Lancamento],
    intervalos: list[Intervalo],
    dias: list[date],
    cfg: Config,
) -> Resultado:
    res = Resultado()
    por_email = {c.conta_jira: c for c in colaboradores.values()}
    projetos = {c.projeto for c in colaboradores.values()} | {l.projeto for l in lancamentos}

    validos = []
    for it in intervalos:
        if it.email in por_email:
            validos.append(it)
        elif f"{it.card}: {it.email}" not in res.ignorados:
            res.ignorados.append(f"{it.card}: {it.email}")
    por_dia = _recortar(validos, dias, cfg)

    lancado: dict[tuple[str, date], int] = defaultdict(int)
    for l in lancamentos:
        lancado[(l.matricula, l.data)] += l.horas

    for c in sorted(colaboradores.values(), key=lambda c: c.matricula):
        for d in dias:
            dia = por_dia.get((c.conta_jira, d))
            horas = arredondar(dia.minutos(), cfg) if dia else 0
            ja_lancado = lancado.get((c.matricula, d))

            if ja_lancado is not None:
                if horas > ja_lancado:
                    res.alertas.append(Alerta(c.matricula, d, DIVERGENCIA,
                                              f"Jira indica {horas}h, PSOffice tem {ja_lancado}h"))
                continue

            if horas == 0:
                res.alertas.append(Alerta(c.matricula, d, LACUNA, "Sem lançamento e sem movimentação no Jira"))
                continue

            res.sugestoes.append(Sugestao(c.matricula, d, _projeto(dia, c, projetos), horas, _origem(dia)))
            if horas < cfg.horas_dia:
                res.alertas.append(Alerta(c.matricula, d, LACUNA, f"Jira cobre {horas}h de {cfg.horas_dia}h"))

            parados = sorted({it.card: it for _, _, it in dia.trechos
                              if _dias_parado(it, d, dias) >= cfg.dias_card_parado}.values(),
                             key=lambda it: it.card)
            for it in parados:
                res.alertas.append(Alerta(
                    c.matricula, d, CARD_PARADO,
                    f"{it.card} parado desde {it.inicio:%d/%m} ({_dias_parado(it, d, dias)} dias úteis); "
                    "o apontamento foi feito com base nele e está se repetindo"))
    return res
