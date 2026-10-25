"""CLI: `python -m apontamento {lacunas,executar}`."""

import argparse
import os
import shutil
from datetime import date, datetime
from pathlib import Path

from . import allocator, notifier, psoffice, reports
from .config import Config, carregar_dotenv
from .jira import JiraClient, ler_fixture
from .timeline import intervalos


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="apontamento", description="Apontamento automático de horas a partir do Jira")
    p.add_argument("comando", choices=["lacunas", "executar"])
    p.add_argument("--dados", type=Path, default=Path("."), help="pasta com os CSVs do PSOffice")
    p.add_argument("--saida", type=Path, default=Path("saida"))
    p.add_argument("--cards", type=Path, default=Path("fixtures/jira_cards.json"), help="cards fictícios")
    p.add_argument("--jira", action="store_true", help="buscar cards no Jira real (usa JIRA_* do .env)")
    p.add_argument("--enviar-email", action="store_true", help="enviar e-mails por SMTP em vez da caixa de saída")
    p.add_argument("--inicio", type=date.fromisoformat)
    p.add_argument("--fim", type=date.fromisoformat)
    args = p.parse_args(argv)

    carregar_dotenv()
    cfg = Config.from_env()
    colaboradores = psoffice.ler_colaboradores(args.dados / "colaboradores.csv")
    lancamentos = psoffice.ler_lancamentos(args.dados / "lancamentos.csv")
    feriados = psoffice.ler_feriados(args.dados / "feriados.csv")
    inicio, fim = reports.periodo(lancamentos)
    inicio, fim = args.inicio or inicio, args.fim or fim

    lacunas = reports.dias_sem_lancamento(colaboradores, lancamentos, feriados, inicio, fim)
    psoffice.escrever_csv(args.saida / "dias_sem_lancamento.csv", ["matricula", "nome", "gestor", "data"], lacunas)
    print(f"dias_sem_lancamento.csv: {len(lacunas)} linhas")
    if args.comando == "lacunas":
        return

    if args.jira:
        cards = JiraClient(os.environ["JIRA_BASE_URL"], os.environ["JIRA_EMAIL"],
                           os.environ["JIRA_API_TOKEN"], cfg.fuso).buscar_cards(
            inicio.isoformat(), [c.conta_jira for c in colaboradores.values()], os.getenv("JIRA_JQL_EXTRA", ""))
    else:
        cards = ler_fixture(args.cards)
    agora = min(datetime.now(), datetime.combine(fim, cfg.jornada[-1][1]))
    its = [it for card in cards for it in intervalos(card, cfg.status_trabalho, agora)]
    dias = psoffice.dias_uteis(inicio, fim, feriados)
    res = allocator.gerar(colaboradores, lancamentos, its, dias, cfg)

    psoffice.escrever_csv(args.saida / "sugestoes.csv", ["matricula", "data", "projeto", "horas", "status"],
                          [[s.matricula, s.data, s.projeto, s.horas, s.status] for s in res.sugestoes])
    psoffice.escrever_csv(args.saida / "sugestoes_origem.csv", ["matricula", "data", "cards"],
                          [[s.matricula, s.data, "; ".join(s.origem)] for s in res.sugestoes])
    psoffice.escrever_csv(args.saida / "alertas.csv", ["matricula", "data", "tipo", "mensagem", "canais"],
                          [[a.matricula, a.data, a.tipo, a.mensagem, "+".join(a.canais)] for a in res.alertas])
    print(f"sugestoes.csv: {len(res.sugestoes)} reportes | alertas.csv: {len(res.alertas)} alertas")
    for ign in res.ignorados:
        print(f"ignorado (assignee fora de colaboradores.csv): {ign}")

    outbox = args.saida / "outbox"
    shutil.rmtree(outbox, ignore_errors=True)
    msgs = notifier.montar(res, colaboradores, lacunas, cfg)
    notifier.enviar(msgs, outbox, args.enviar_email)
    print(f"notificações: {len(msgs)} mensagens ({'SMTP' if args.enviar_email else outbox})")


if __name__ == "__main__":
    main()
