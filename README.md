# Apontamento automático de horas (Jira → PSOffice)

MVP do hackathon descrito em [PROPOSTA.md](PROPOSTA.md). Usa só a biblioteca padrão do Python 3.10+, sem dependências.

## Contexto

Esta proposta complementa a de um colega, que faz o apontamento de horas automático a partir dos **commits no Git**. Esse caminho só cobre quem trabalha com código. Aqui o objetivo é atender os demais colaboradores (análise, QA, produto, gestão, suporte etc.), cujo trabalho não deixa commits mas aparece na **movimentação dos cards no Jira**. Juntas, as duas soluções cobrem o time inteiro. Do lado do Jira, a saída para o PSOffice são sugestões `PENDENTE` no formato de `lancamentos.csv`, que o colaborador confirma.

**Integração com o PSOffice:** como não conhecemos as formas de integração disponíveis no PSOffice, a implementação só gera arquivos CSV de saída (`sugestoes.csv` no formato de `lancamentos.csv`), sem alterar os dados de entrada. Se o PSOffice oferecer uma API, as sugestões passariam a ser lançadas diretamente nele, mantendo as mesmas regras: status `PENDENTE`, aprovação pelo colaborador e nenhum lançamento existente sobrescrito.

## Executar

```bash
python3 -m apontamento executar      # lacunas + sugestões + alertas + notificações
python3 -m apontamento lacunas       # só o relatório de dias sem lançamento
python3 -m unittest discover -s tests -t .
```

Por padrão, a ferramenta lê os CSVs da raiz e os cards fictícios de `fixtures/jira_cards.json`.

| Saída (`saida/`) | Conteúdo |
|---|---|
| `dias_sem_lancamento.csv` | idêntico a `esperado/dias_sem_lancamento.csv` |
| `sugestoes.csv` | um reporte por colaborador por dia, `PENDENTE`, no formato de `lancamentos.csv` |
| `sugestoes_origem.csv` | cards e horários que originaram cada reporte |
| `alertas.csv` | `lacuna`, `divergencia` e `card_parado`, com os canais de cada alerta |
| `outbox/email/*.eml` | e-mails individuais e o consolidado do RH |
| `outbox/gchat/*.json` | mensagens individuais do Google Chat (payload `{"text": ...}`) |

Opções úteis: `--dados`, `--saida`, `--cards`, `--inicio/--fim`, `--enviar-email` (envia por SMTP usando o `.env`) e `--jira` (busca os cards no Jira real).

## Configuração (`.env`)

Copie `.env.example` para `.env`. O `.env` está no `.gitignore` e nunca deve ser versionado.

| Variável | Uso |
|---|---|
| `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` | acesso ao Jira Cloud (só com `--jira`). Token em <https://id.atlassian.com/manage-profile/security/api-tokens> |
| `JIRA_JQL_EXTRA` | filtro JQL opcional somado à busca, ex.: `project = PPD` |
| `STATUS_TRABALHO` | status que contam como trabalho (padrão: `In Progress,Em andamento,Em Desenvolvimento,Code Review`) |
| `JORNADA_*`, `ALMOCO_*`, `DIAS_CARD_PARADO`, `FUSO` | regras de jornada e de card parado |
| `EMAIL_RH`, `EMAIL_REMETENTE`, `SMTP_*` | notificações por e-mail |

## Jira real (`--jira`)

```bash
python3 -m apontamento executar --jira --dados dados_teste --saida saida_teste
```

- Busca só os cards atualizados no período cujo assignee é um colaborador do `colaboradores.csv`. E-mails sem usuário no Jira são ignorados.
- O changelog vem embutido na busca (`expand=changelog`); há retry com backoff para timeout, HTTP 429 e 5xx.
- O card é ligado ao colaborador pelo e-mail. Quando o e-mail no Jira difere do de contato, preencha a coluna opcional `email_jira` em `colaboradores.csv`: ela é usada para achar os cards, e `email` continua recebendo os avisos.
- Na rede da CERC o TLS passa pelo proxy Netskope, cuja CA não tem a extensão *key usage*. O cliente desliga só o modo estrito X.509 do Python 3.13+; a cadeia continua sendo verificada.

Testado contra `cerc-portal.atlassian.net`. A pasta `dados_teste/` é uma cópia dos CSVs de exemplo com um colaborador real (C061, `email_jira` da CERC e avisos no e-mail partner), para ver sugestões saindo de cards reais sem alterar os dados de exemplo.

## Cenários da fixture

| Card | Colaborador | O que demonstra |
|---|---|---|
| ECL-101/102/103 | C006 | 3 cards no mesmo dia viram 1 reporte de 8h (09/10) |
| FEN-202 | C013 | dia já lançado: só alerta de divergência (14/10) |
| COM-301 | C009 | card parado: reportes feitos e alerta no Google Chat a partir de 20/10 |
| BOR-401 | C014 | dia parcial: reporte de 4h sem completar, com alerta de lacuna |
| INT-12 / EXT-7 | — | sem assignee / fora do PSOffice: ignorados |

## Pendências conhecidas

- **Google Chat:** o envio real depende do Chat app liberado pelo admin do Workspace. Até lá as mensagens ficam em `outbox/gchat`.
- **Worklogs explícitos do Jira** ainda não são considerados. As horas vêm só das transições de status.
- **Cards em andamento há semanas** geram dias cheios de 8h; o arredondamento em blocos de 2h zera movimentações curtas no fim do expediente (ex.: 31 min).
- **Alerta de card parado:** o texto mostra o limite configurado ("3 dias úteis"), não o tempo real parado.
- **Fora do MVP:** API web, controle de duplicidade com SQLite e agendamento diário.
