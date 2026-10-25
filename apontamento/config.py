"""Configuração lida do ambiente (e de um `.env` opcional na raiz)."""

import os
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path


def carregar_dotenv(caminho: Path = Path(".env")) -> None:
    """Carrega um `.env` simples (CHAVE=valor) sem sobrescrever variáveis já definidas."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if "=" not in linha:
            continue
        chave, valor = (p.strip() for p in linha.split("=", 1))
        os.environ.setdefault(chave, valor)


def _hora(valor: str) -> time:
    return datetime.strptime(valor, "%H:%M").time()


@dataclass(frozen=True)
class Config:
    jornada: tuple[tuple[time, time], ...] = ((time(9), time(12)), (time(13), time(18)))
    horas_dia: int = 8
    bloco_horas: int = 2
    status_trabalho: frozenset[str] = frozenset({"In Progress", "Em andamento", "Em Desenvolvimento", "Code Review"})
    dias_card_parado: int = 3
    fuso: str = "America/Sao_Paulo"
    email_rh: str = "rh@empresa.com"

    @classmethod
    def from_env(cls) -> "Config":
        inicio = _hora(os.getenv("JORNADA_INICIO", "09:00"))
        fim = _hora(os.getenv("JORNADA_FIM", "18:00"))
        almoco = _hora(os.getenv("ALMOCO_INICIO", "12:00"))
        almoco_fim = (datetime.combine(datetime.min, almoco)
                      + timedelta(minutes=int(os.getenv("ALMOCO_MIN", "60")))).time()
        status = os.getenv("STATUS_TRABALHO")
        return cls(
            jornada=((inicio, almoco), (almoco_fim, fim)),
            status_trabalho=frozenset(s.strip() for s in status.split(",")) if status else cls.status_trabalho,
            dias_card_parado=int(os.getenv("DIAS_CARD_PARADO", "3")),
            fuso=os.getenv("FUSO", cls.fuso),
            email_rh=os.getenv("EMAIL_RH", cls.email_rh),
        )
