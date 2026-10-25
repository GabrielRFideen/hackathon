"""Notificações: e-mail e Google Chat individual para o colaborador, consolidado por e-mail para o RH.

O Google Chat individual depende de um Chat app liberado pelo admin do Workspace. Até lá as
mensagens são gravadas na caixa de saída (`saida/outbox/gchat`), no mesmo payload que a
Chat API receberia. O e-mail também vai para a caixa de saída, a não ser que o envio por
SMTP seja pedido explicitamente.
"""

import json
import os
import smtplib
from collections import defaultdict
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

from .allocator import Resultado
from .config import Config
from .psoffice import Colaborador


@dataclass
class Mensagem:
    canal: str  # "email" | "gchat"
    destinatario: str
    assunto: str
    corpo: str


def _linhas_colaborador(sugestoes, alertas, canal: str) -> list[str]:
    linhas = []
    if sugestoes:
        linhas.append("Reportes sugeridos (aguardando sua aprovação):")
        linhas += [f"  • {s.data:%d/%m/%Y}: {s.horas}h em {s.projeto} (cards: {', '.join(s.origem)})"
                   for s in sugestoes]
    meus = [a for a in alertas if canal in a.canais]
    if meus:
        linhas.append("Alertas:")
        linhas += [f"  • {a.data:%d/%m/%Y}: {a.mensagem}" for a in meus]
    return linhas


def montar(res: Resultado, colaboradores: dict[str, Colaborador], lacunas: list[list[str]],
           cfg: Config) -> list[Mensagem]:
    sug = defaultdict(list)
    for s in res.sugestoes:
        sug[s.matricula].append(s)
    alt = defaultdict(list)
    for a in res.alertas:
        alt[a.matricula].append(a)

    msgs = []
    for m in sorted(set(sug) | set(alt)):
        c = colaboradores[m]
        for canal in ("email", "gchat"):
            linhas = _linhas_colaborador(sug[m], alt[m], canal)
            if linhas:
                msgs.append(Mensagem(canal, c.email, "Apontamento de horas: pendências",
                                     f"Olá, {c.nome}!\n\n" + "\n".join(linhas)))

    por_colab = defaultdict(list)
    for matricula, nome, gestor, data in lacunas:
        por_colab[(matricula, nome, gestor)].append(data)
    linhas = [f"Dias úteis sem lançamento: {len(lacunas)} ({len(por_colab)} colaboradores)",
              f"Reportes sugeridos aguardando aprovação: {len(res.sugestoes)}", ""]
    linhas += [f"  • {m} {nome} ({gestor}): {len(datas)} dia(s): {', '.join(datas)}"
               for (m, nome, gestor), datas in sorted(por_colab.items())]
    msgs.append(Mensagem("email", cfg.email_rh, "Consolidado de apontamento de horas", "\n".join(linhas)))
    return msgs


def _email(msg: Mensagem, remetente: str) -> EmailMessage:
    e = EmailMessage()
    e["From"], e["To"], e["Subject"] = remetente, msg.destinatario, msg.assunto
    e.set_content(msg.corpo)
    return e


def enviar(msgs: list[Mensagem], outbox: Path, enviar_email: bool = False) -> None:
    remetente = os.getenv("EMAIL_REMETENTE", "apontamento@empresa.com")
    smtp = None
    if enviar_email:
        smtp = smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")))
        smtp.starttls()
        if os.getenv("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
    try:
        for msg in msgs:
            pasta = outbox / msg.canal
            pasta.mkdir(parents=True, exist_ok=True)
            if msg.canal == "gchat":
                payload = {"text": f"*{msg.assunto}*\n{msg.corpo}"}
                (pasta / f"{msg.destinatario}.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            elif smtp:
                smtp.send_message(_email(msg, remetente))
            else:
                (pasta / f"{msg.destinatario}.eml").write_bytes(_email(msg, remetente).as_bytes())
    finally:
        if smtp:
            smtp.quit()
