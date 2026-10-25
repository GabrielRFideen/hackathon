"""Changelog dos cards → intervalos em que o card estava em status de trabalho com um assignee."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Intervalo:
    card: str
    email: str
    labels: tuple[str, ...]
    inicio: datetime  # também é a última movimentação do card
    fim: datetime


def intervalos(card: dict, status_trabalho: frozenset[str], agora: datetime) -> list[Intervalo]:
    """Cada evento do changelog encerra o intervalo corrente e pode abrir outro.

    Assim, o início de todo intervalo coincide com a última movimentação do card,
    o que permite detectar cards parados.
    """
    eventos = sorted(card.get("changelog", []), key=lambda e: e["at"])
    status_ev = [e for e in eventos if e.get("field", "status") == "status"]
    assignee_ev = [e for e in eventos if e.get("field") == "assignee"]
    status = status_ev[0]["from"] if status_ev else card.get("status")
    assignee = assignee_ev[0]["from"] if assignee_ev else card.get("assignee")
    labels = tuple(card.get("labels", []))

    resultado: list[Intervalo] = []
    inicio: datetime | None = None
    for ev in eventos:
        t = datetime.fromisoformat(ev["at"])
        if t > agora:
            break
        if inicio is not None and t > inicio:
            resultado.append(Intervalo(card["key"], assignee.lower(), labels, inicio, t))
        if ev.get("field", "status") == "status":
            status = ev["to"]
        else:
            assignee = ev["to"]
        inicio = t if status in status_trabalho and assignee else None
    if inicio is not None and agora > inicio:
        resultado.append(Intervalo(card["key"], assignee.lower(), labels, inicio, agora))
    return resultado
