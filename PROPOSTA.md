
# Proposta: Apontamento Automático de Horas a partir do Jira

> Hackathon · rascunho v0.1 · 2026-10-23

## 1. Problema e objetivo

Hoje o colaborador lança as horas manualmente no **PSOffice**. Nos dados de exemplo (período de 09/10 a 22/10/2026, 9 dias úteis) aparecem estes problemas:

| Indicador | Valor |
|---|---|
| Colaboradores | 60 |
| Lançamentos | 572 |
| **Dias úteis sem nenhum lançamento** | **61** (15 colaboradores; 5 deles sem lançar em nenhum dos 9 dias) |
| Dias com menos de 8h lançadas | 81 |
| Lançamentos ainda `PENDENTE` | 61 |

**Objetivo:** usar a movimentação dos cards no Jira (quem estava com qual card, em qual status e por quanto tempo) para **sugerir automaticamente os lançamentos** no formato do PSOffice. A ferramenta também **avisa o colaborador e o RH** quando há dias sem apontamento.

Princípios:
- **Sugerir, não impor.** Todo lançamento gerado nasce como `PENDENTE` e só vira `APROVADO` depois que o colaborador confirma.
- **Nunca sobrescrever** um lançamento que já existe e está `APROVADO`.
- **Um apontamento por colaborador por dia.** No PSOffice o apontamento é único e não é separado por card. Todas as movimentações do dia viram **um único reporte**.
- **Rastreabilidade.** Cada sugestão indica de quais cards e transições ela veio.

---

## 2. Fontes de dados

### 2.1 PSOffice (somente CSV)

A integração com o PSOffice é **feita só por CSV**: a ferramenta lê os arquivos abaixo e gera um `sugestoes.csv` no mesmo formato de `lancamentos.csv`. Não há API.

| Arquivo | Colunas | Observações |
|---|---|---|
| `colaboradores.csv` | `matricula, nome, email, gestor, cliente, projeto, regime, local` | `regime` ∈ {CLT, PJ}; `local` ∈ {São Paulo, Araraquara, Remoto} |
| `lancamentos.csv` | `matricula, data, projeto, horas, status` | `horas` em blocos de 2h (2/4/6/8); `status` ∈ {APROVADO, PENDENTE}; existe o projeto `INTERNO` |
| `feriados.csv` | `data, descricao` | ex.: 2026-10-12 Nossa Senhora Aparecida. É a **única** fonte de feriados, sem feriados municipais por `local` |
| `esperado/dias_sem_lancamento.csv` | `matricula, nome, gestor, data` | saída esperada do relatório de lacunas (teste de aceitação) |

### 2.2 Jira Cloud (REST API v3)

| Uso | Endpoint |
|---|---|
| Cards movimentados no período + histórico (cards **sem assignee são ignorados**) | `GET /rest/api/3/search/jql?jql=updated >= "2026-10-09" AND assignee IS NOT EMPTY&expand=changelog&fields=summary,status,assignee,project,labels,components,parent` |
| Changelog completo (quando ultrapassa 100 itens) | `GET /rest/api/3/issue/{key}/changelog` |
| Worklogs explícitos (se o time registra) | `GET /rest/api/3/issue/{key}/worklog` |
| E-mail do usuário (accountId → e-mail) | `GET /rest/api/3/user?accountId=...` |

Autenticação: Basic Auth (`JIRA_EMAIL` + `JIRA_API_TOKEN`), sempre lida de variáveis de ambiente (ver seção 7).

### 2.3 Mapeamentos (de-para)

- **Pessoa:** e-mail do assignee no Jira → `colaboradores.email` → `matricula`.
- **Projeto PSOffice:** os times usam a **label** do card com o código do projeto (ex.: `ECL-01`). O reporte do dia continua único:
  - todos os cards do dia com a mesma label → esse é o projeto do reporte;
  - labels diferentes no mesmo dia → vale a label com mais horas no dia, e as demais aparecem na descrição;
  - card sem label → fallback para `colaboradores.projeto`.

---

## 3. Regra de cálculo das horas

```
cards + changelog ──► intervalos "em andamento" ──► recorte por expediente ──► consolidação diária (1 reporte) ──► arredondamento 2h ──► sugestões
```

1. **Intervalos de trabalho.** No changelog de cada card, um intervalo começa quando o card entra em um status de trabalho (`In Progress`, `Em Desenvolvimento`, `Code Review` ativo...) e termina quando sai dele (`Done`, `Blocked`, `To Do`) ou quando o assignee muda. A lista de status de trabalho é configurável por board.
2. **Recorte por expediente.** Só conta o tempo dentro da jornada (09h–18h com 1h de almoço, ou seja 8h/dia), sem fins de semana e sem as datas de `feriados.csv`. A jornada é **a mesma para CLT e PJ**.
3. **Prioridade do worklog.** Se o card tem worklog explícito no dia, vale o worklog e o tempo estimado pelo status é ignorado.
4. **Consolidação diária (reporte único).** Todas as movimentações do colaborador no dia, de um ou de vários cards, viram **um único reporte** no PSOffice, sem rateio entre cards. As horas são a **união** dos intervalos no expediente: um período em que dois cards estavam em andamento ao mesmo tempo conta uma vez só. A descrição lista os cards do dia (ex.: `ECL-101, ECL-102`).
5. **Arredondamento.** O total do dia é arredondado para blocos de 2h (padrão do PSOffice) e fica limitado a 8h.
6. **Conciliação com o que já existe:**
   - dia sem lançamento → sugere o reporte único do dia;
   - dia que já tem lançamento → não gera um novo reporte. Se as horas do Jira forem maiores que as lançadas, aparece um alerta de conferência.
7. **Atividades fora do Jira (dia incompleto).** O reporte **não é completado** até 8h com `INTERNO` nem com outro projeto: fica só com as horas vindas do Jira. A diferença fica como **lacuna**, e o colaborador recebe um **alerta** (ex.: "09/10: Jira cobre 4h de 8h"). Dia sem nenhuma movimentação no Jira também fica como lacuna, com alerta.
8. **Card parado há 3 dias.** Se um card fica em status de trabalho por **3 dias úteis seguidos sem nenhuma movimentação** no changelog, o apontamento **continua sendo feito** normalmente (as horas desse card entram nos reportes dos dias). Além disso, o colaborador recebe um **alerta no Google Chat** avisando que o apontamento está se repetindo com base em um card parado, para que ele confira ou movimente o card.

---

## 4. Exemplo com cards fictícios

Colaboradores reais dos CSVs:
- **C006** (Cliente Eclipse, projeto `ECL-01`, Gestor 01), que **não lançou nada em 09/10** (consta no `esperado`). Nesse dia ele movimentou **três cards**.
- **C013** (Cliente Fênix, projeto `FÊN-02`, Gestor 02), que **já lançou 6h em 14/10**.

### 4.1 Cards (changelog resumido)

```json
[
  {
    "key": "ECL-101",
    "summary": "Ajustar cálculo de frete no checkout",
    "assignee": "colaborador006@exemplo.test",
    "labels": ["ECL-01"],
    "changelog": [
      {"at": "2026-10-09T09:00", "from": "To Do",       "to": "In Progress"},
      {"at": "2026-10-09T11:00", "from": "In Progress", "to": "Done"}
    ]
  },
  {
    "key": "ECL-102",
    "summary": "Corrigir timeout na consulta de pedidos",
    "assignee": "colaborador006@exemplo.test",
    "labels": ["ECL-01"],
    "changelog": [
      {"at": "2026-10-09T10:00", "from": "To Do",       "to": "In Progress"},
      {"at": "2026-10-09T15:00", "from": "In Progress", "to": "Done"}
    ]
  },
  {
    "key": "ECL-103",
    "summary": "Revisar logs de integração",
    "assignee": "colaborador006@exemplo.test",
    "labels": ["ECL-01"],
    "changelog": [
      {"at": "2026-10-09T15:00", "from": "To Do",       "to": "In Progress"},
      {"at": "2026-10-09T18:00", "from": "In Progress", "to": "Done"}
    ]
  },
  {
    "key": "FEN-202",
    "summary": "Integração com gateway de pagamentos",
    "assignee": "colaborador013@exemplo.test",
    "labels": ["FÊN-02"],
    "changelog": [
      {"at": "2026-10-13T09:00", "from": "To Do",       "to": "In Progress"},
      {"at": "2026-10-14T18:00", "from": "In Progress", "to": "Done"}
    ]
  }
]
```

### 4.2 Passo a passo

**C006 em 09/10:** três cards, um reporte.

| Card | Intervalo em andamento |
|---|---|
| ECL-101 | 09h–11h |
| ECL-102 | 10h–15h (sobrepõe ECL-101 das 10h às 11h) |
| ECL-103 | 15h–18h |
| **União no expediente** | 09h–18h, menos 1h de almoço = **8h** (a sobreposição conta uma vez só) |

→ **Um único reporte:** 8h no projeto da label (`ECL-01`), descrição `ECL-101, ECL-102, ECL-103`.

**C013 em 14/10:** FEN-202 em andamento o dia inteiro dá 8h pelo Jira, mas já existe um lançamento de 6h (`FÊN-02`, APROVADO). Como o apontamento do dia é único, **não se cria um segundo reporte**. A ferramenta só envia um **alerta de conferência** ("Jira indica 8h, PSOffice tem 6h").

### 4.3 Saída (mesmo formato de `lancamentos.csv`, uma linha por colaborador por dia)

```csv
matricula,data,projeto,horas,status
C006,2026-10-09,ECL-01,8,PENDENTE
```

A origem de cada reporte fica num registro auxiliar e aparece na tela de aprovação e na notificação, por exemplo `ECL-101 (09h–11h), ECL-102 (10h–15h), ECL-103 (15h–18h)`.

---

## 5. Relatório "dias sem lançamento"

**Regra (validada contra `esperado/dias_sem_lancamento.csv`, 61/61 linhas idênticas):**

> Para cada colaborador e cada dia útil do período (de segunda a sexta, menos os feriados de `feriados.csv`), gerar uma linha `matricula, nome, gestor, data` se o colaborador **não tiver nenhum lançamento**, seja qual for o status.

- O período vai da menor à maior data em `lancamentos.csv` (09/10 a 22/10/2026).
- Um lançamento `PENDENTE` **conta** como lançado. Se só os `APROVADO` contassem, o resultado teria 108 linhas e não bateria com o esperado.
- Saída ordenada por `matricula, data`.

O relatório vira a lista de notificações do dia: o colaborador recebe as próprias lacunas já com as sugestões do Jira para aprovar em um clique, e o RH recebe o consolidado geral.

### 5.1 Notificações (e-mail + Google Chat)

O relatório de lacunas e as sugestões viram notificações, enviadas pelos **dois canais**:

| Destinatário | Quando | Conteúdo | Canal |
|---|---|---|---|
| Colaborador | diariamente, no fim do expediente (ex.: 18h30) | dias sem apontamento + reporte sugerido de cada dia (horas e cards de origem) + link para aprovar | e-mail + Google Chat |
| Colaborador | quando o Jira diverge de um lançamento existente | alerta de conferência (ex.: "Jira indica 8h, PSOffice tem 6h") | e-mail + Google Chat |
| Colaborador | dia incompleto ou sem movimentação no Jira (lacuna) | alerta de lacuna (ex.: "09/10: Jira cobre 4h de 8h") | e-mail + Google Chat |
| Colaborador | card em status de trabalho há 3 dias úteis sem movimentação | alerta de **apontamento repetido** (o apontamento é feito mesmo assim) | Google Chat |
| RH | diariamente, ou semanalmente se configurado | consolidado: quem tem lacunas (com o gestor de cada um), quantos dias e quantas sugestões pendentes | e-mail para o endereço do RH (`EMAIL_RH`) |

- **E-mail:** SMTP corporativo ou Gmail API, com template HTML (Jinja2). O endereço do colaborador vem de `colaboradores.email`. O consolidado vai para **um e-mail de alguém do RH**, configurado em `EMAIL_RH`, porque o CSV não traz o e-mail dos gestores.
- **Google Chat:**
  - **Mensagem individual (direta) para cada colaborador**, nunca em espaço compartilhado.
  - Implementação: um Chat app com conta de serviço na Google Chat API. A DM é localizada ou criada com `spaces.findDirectMessage` / `spaces.setup` usando `users/{email}`, e a mensagem é enviada com `spaces.messages.create`.
  - Pré-requisito: o admin do Google Workspace precisa publicar e liberar o app para os colaboradores.
- **Idempotência:** a tabela `notificacoes(matricula, data, canal, enviado_em)` evita mandar a mesma notificação duas vezes. Se um canal falhar, o outro é enviado mesmo assim e a falha é registrada para nova tentativa.

Exemplo de mensagem no Google Chat (C006):

```json
{
  "text": "⏰ *Apontamento pendente: 09/10/2026*\nSugestão: *8h* em ECL-01 (reporte único)\nCards: ECL-101 (09h–11h), ECL-102 (10h–15h), ECL-103 (15h–18h)\n<https://apontamento.local/sugestoes/123|Aprovar sugestão>"
}
```

Exemplo de alerta de card parado (Google Chat):

```json
{
  "text": "⚠️ *Card parado há 3 dias: FEN-202*\nO card está em *In Progress* desde 13/10 sem movimentação. O apontamento de hoje foi feito com base nele e está se *repetindo*.\nSe o trabalho mudou, movimente o card no Jira."
}
```

---

## 6. Arquitetura proposta (Python)

```
                ┌─────────────┐   webhook / polling   ┌──────────────┐
                │  Jira Cloud │ ────────────────────► │ jira_client  │
                └─────────────┘                       └──────┬───────┘
                                                             ▼
┌──────────────┐      CSV      ┌──────────┐   ┌──────────┐   ┌───────────┐
│   PSOffice   │ ◄───────────► │ psoffice │◄──│allocator │◄──│ timeline  │
└──────────────┘               └────┬─────┘   └──────────┘   └───────────┘
                                    ▼
                              ┌──────────┐     ┌──────────────────────┐
                              │ reports  │ ──► │ notifier (e-mail +   │
                              └──────────┘     │ Google Chat)         │
                                               └──────────────────────┘
          FastAPI (/sync, /sugestoes, /lacunas)  ·  SQLite  ·  APScheduler
```

| Módulo | Responsabilidade |
|---|---|
| `jira_client` | `httpx` com paginação, retry/backoff (HTTP 429) e cache de usuários |
| `timeline` | changelog → intervalos `(matricula, card, projeto, início, fim)` |
| `allocator` | expediente, feriados, consolidação em 1 reporte por dia (união dos intervalos), projeto pela label, arredondamento em 2h, conciliação, detecção de lacuna e de card parado |
| `notifier` | envia e-mail (SMTP / Gmail API) ao colaborador e ao RH, e mensagem direta no Google Chat (Chat API com conta de serviço) ao colaborador |
| `psoffice` | leitura dos CSVs do PSOffice e geração do `sugestoes.csv` (integração só por CSV) |
| `reports` | relatório de lacunas e divergências |
| `api` | FastAPI: `POST /sync`, `GET /sugestoes?matricula=`, `POST /sugestoes/{id}/aprovar`, `GET /lacunas` |
| `scheduler` | job diário (ex.: 18h30) que roda sync, sugestões e notificações |

Estrutura de pastas sugerida:

```
apontamento-jira/
├── app/
│   ├── jira_client.py
│   ├── timeline.py
│   ├── allocator.py
│   ├── psoffice.py
│   ├── reports.py
│   ├── api.py
│   └── config.py          # pydantic-settings, lê o .env
├── data/                  # CSVs do PSOffice (exemplos)
├── fixtures/jira_cards.json   # cards fictícios da seção 4
├── tests/
│   ├── test_lacunas.py        # compara com esperado/dias_sem_lancamento.csv
│   └── test_allocator.py
├── .env.example
└── pyproject.toml         # fastapi, httpx, pandas, pydantic-settings, apscheduler, pytest
```

`.env.example`:

```dotenv
JIRA_BASE_URL=https://SUA-EMPRESA.atlassian.net
JIRA_EMAIL=usuario@empresa.com
JIRA_API_TOKEN=            # nunca versionar
JORNADA_INICIO=09:00
JORNADA_FIM=18:00
ALMOCO_MIN=60
STATUS_TRABALHO=In Progress,Em Desenvolvimento,Code Review
DIAS_CARD_PARADO=3
# Notificações
SMTP_HOST=smtp.empresa.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=             # nunca versionar
EMAIL_REMETENTE=apontamento@empresa.com
EMAIL_RH=rh@empresa.com    # destinatário do consolidado
GCHAT_SERVICE_ACCOUNT_FILE=/caminho/seguro/chat-sa.json   # credencial do Chat app (nunca versionar)
NOTIFICAR_HORARIO=18:30
```

A idempotência fica numa tabela SQLite `sugestoes(matricula, data, projeto, horas, origem, hash)`. Rodar o sync de novo não duplica sugestões.

---

## 7. Segurança

- O token do Jira fica **só** em `.env` (incluído no `.gitignore`) ou num secret manager. Nunca em código, README ou log.
- ⚠️ **O token de exemplo foi compartilhado em texto aberto no chat. Recomenda-se revogá-lo** em <https://id.atlassian.com/manage-profile/security/api-tokens> e gerar outro, de preferência com escopo só de leitura (`read:jira-work`, `read:jira-user`).
- Usar uma conta de serviço técnica em vez de uma conta pessoal.
- A credencial da conta de serviço do Google Chat e a senha SMTP são segredos: ficam fora do repositório e nunca vão para logs.
- As notificações individuais (e-mail e Google Chat) mostram só os dados do próprio colaborador. O consolidado vai apenas para o e-mail do RH.
- Os dados de horas são pessoais (LGPD).

---

## 8. Escopo: MVP do hackathon × evolução

**MVP (hackathon)**
1. Ler os CSVs do PSOffice.
2. Gerar o relatório de lacunas **idêntico** a `esperado/dias_sem_lancamento.csv`.
3. Simular o Jira com `fixtures/jira_cards.json` (seção 4) e gerar as sugestões `PENDENTE`.
4. CLI ou endpoint que exporta `sugestoes.csv` no formato de `lancamentos.csv`.
5. Notificação individual do colaborador por e-mail e mensagem direta no Google Chat, e consolidado por e-mail para o RH.
6. (Bônus) Página simples para aprovar as sugestões.

**Evolução**
- Integração real com o Jira (polling, depois webhook `jira:issue_updated`).
- Botões "Aprovar" e "Ajustar" dentro da mensagem do Google Chat (Chat app interativo).
- Dashboard para o RH (aderência ao apontamento por time e por cliente).

---

## 9. Critérios de aceite e testes

- `test_lacunas.py`: a saída é exatamente igual a `esperado/dias_sem_lancamento.csv` (61 linhas).
- `test_allocator.py`:
  - um card no dia inteiro → 8h;
  - vários cards no mesmo dia → **um único reporte**, com as horas pela união dos intervalos (cenário C006 em 09/10);
  - card que atravessa fim de semana ou feriado → sem horas em 10/10, 11/10 e 12/10;
  - dia já `APROVADO` → nenhuma sugestão;
  - dia que já tem lançamento → nenhum reporte novo, só o alerta (cenário C013 em 14/10);
  - dia com menos de 8h pelo Jira → reporte só com as horas do Jira, sem completar, e alerta de lacuna;
  - card parado há 3 dias úteis → apontamento feito normalmente e alerta no Google Chat;
  - cards com labels diferentes no mesmo dia → um reporte, no projeto da label com mais horas;
  - notifier: monta o e-mail e o payload do Google Chat certos (com mock de SMTP e da Chat API);
  - card sem assignee → ignorado, não gera reporte.
- O exemplo da seção 4 é reproduzido de ponta a ponta a partir da fixture.

---

## 10. Decisões tomadas e questões em aberto

**Decisões**

| Tema | Decisão |
|---|---|
| Integração PSOffice | Só CSV: leitura dos arquivos e geração de `sugestoes.csv` |
| De-para card → projeto | Label do card com o código do projeto (seção 2.3) |
| Card parado | Parado há 3 dias úteis em status de trabalho: o apontamento é feito mesmo assim, com alerta no Google Chat de que está se repetindo |
| Atividades fora do Jira | Não completar o dia: fica a lacuna, com alerta |
| Regime | PJ e CLT seguem a mesma jornada de 8h/dia |
| Feriados | Só os de `feriados.csv` |
| Aceitação | Risco de o colaborador aprovar sem conferir: aceito, sem mitigação específica |
| Google Chat | Mensagem individual (direta) para cada colaborador |
| Consolidado | Enviado para o e-mail de alguém do RH (`EMAIL_RH`) |
| Cards sem assignee | Ignorados |

Não há questões em aberto no momento.
