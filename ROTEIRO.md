# Roteiro de apresentação (vídeo de ~7 min)

Evidência gravada da implementação: o problema, a regra validada, os cenários da fixture e o teste contra o Jira real da CERC.
Os comandos de cada cena estão em `demo.sh` (Enter avança para o próximo passo).

## Preparação (antes de gravar)

- [ ] Estar na rede da CERC (ou VPN) e com o `.env` preenchido. **Nunca abrir o `.env` na tela** (contém o token).
- [ ] Rodar `./demo.sh` uma vez do início ao fim para confirmar que tudo funciona (o Jira real leva ~40 s).
- [ ] Terminal com fonte grande (≥ 18 pt), tema claro ou escuro de alto contraste, janela limpa (`clear`).
- [ ] Navegador logado em `cerc-portal.atlassian.net` com o card **PPD-4775** aberto na aba **Histórico**.
- [ ] Editor com `README.md` aberto (seção Contexto) para a abertura.
- [ ] Gravação: QuickTime (Arquivo → Nova Gravação de Tela) ou `Cmd+Shift+5`, com microfone. Desativar notificações (Foco → Não Perturbe).
- [ ] Cuidado com dados de terceiros na tela: a saída do Jira real pode listar e-mails de colegas (linhas `ignorado`); o `demo.sh` já as oculta.

## Cenas

### 1. Abertura e contexto (0:00 – 0:45)

**Tela:** `README.md`, seção Contexto.

> "Nosso colega propôs o apontamento de horas automático a partir dos commits no Git. Isso resolve para quem programa, mas boa parte do time — análise, QA, produto, gestão — não faz commit. O trabalho dessas pessoas aparece na movimentação dos cards no Jira. Esta proposta complementa a dele: gera o apontamento no PSOffice a partir dos cards e avisa o colaborador e o RH quando há dias sem apontamento."

### 2. Como funciona (0:45 – 1:45)

**Tela:** `README.md` ou um slide com o fluxo:

```
Jira (changelog dos cards) → intervalos em status de trabalho → 1 reporte por pessoa/dia → sugestoes.csv (PENDENTE)
                                                              ↘ alertas → e-mail + Google Chat + consolidado do RH
```

> "Para cada card, lemos o histórico de status. O tempo em que o card fica em um status de trabalho, como 'Em andamento', dentro do expediente, vira horas. Vários cards no mesmo dia viram um único reporte, arredondado em blocos de 2 horas, até 8 horas. A sugestão nasce como PENDENTE: quem aprova é o colaborador, e nunca sobrescrevemos um lançamento existente. Como não conhecemos a integração do PSOffice, a saída é um CSV no mesmo formato dos lançamentos; com uma API, o lançamento seria direto."

### 3. Regra validada: dias sem lançamento (1:45 – 2:30)

**Comando (passo 1 do `demo.sh`):** `lacunas` + comparação com o esperado.

> "Primeiro, o relatório de dias sem lançamento. A regra é: todo dia útil, descontando os feriados da planilha, em que o colaborador não tem nenhum lançamento. O resultado é idêntico, byte a byte, ao arquivo esperado: 61 linhas."

**Destacar:** a mensagem `IDÊNTICO ao esperado`.

### 4. Cenários da fixture (2:30 – 4:00)

**Comando (passo 2):** `executar` com os cards fictícios e exibição de `sugestoes.csv`, `sugestoes_origem.csv` e `alertas.csv`.

> "Agora com cards fictícios que cobrem os casos difíceis:"

| Apontar na tela | Fala |
|---|---|
| C006, 09/10, 8h | "Três cards no mesmo dia viram um único reporte de 8 horas — a sobreposição conta uma vez." |
| C013, alerta `divergencia` | "Dia já lançado com 6 horas: não geramos reporte novo, só um alerta de que o Jira indica 8." |
| C009, 16, 19 e 20/10 + `card_parado` | "Card parado há 3 dias úteis: o apontamento é feito, mas o colaborador recebe alerta no Google Chat." |
| C014, 13/10, 4h + `lacuna` | "Dia parcial: 4 horas, sem completar o dia. A diferença fica como lacuna, com alerta." |

### 5. Notificações (4:00 – 4:45)

**Comando (passo 3):** mensagem do Google Chat e consolidado do RH.

> "Cada colaborador recebe e-mail e mensagem direta no Google Chat com as sugestões a aprovar e as pendências. O RH recebe um consolidado. Como é hackathon, o app do Google Chat não foi publicado: as mensagens ficam numa caixa de saída local, já no formato da API."

### 6. Jira real (4:45 – 6:15)

**Navegador:** card **PPD-4775**, aba Histórico — mostrar a transição para *Em Desenvolvimento* em 21/10 às 17:29.

> "Agora com o Jira real da CERC. Este card meu entrou em desenvolvimento em 21 de outubro, no fim do dia."

**Comando (passo 4):** `executar --jira --dados dados_teste`.

> "Na pasta de teste eu me cadastrei como colaborador. A ferramenta busca só os cards de quem está no cadastro, com o histórico na mesma consulta — roda em cerca de 40 segundos."

**Destacar** as linhas do C061:

> "Saíram reportes de 8 horas em 09, 13, 14 e 22 de outubro, cada um com os cards de origem. O 21 ficou como lacuna: foram só 31 minutos antes do fim do expediente, abaixo do bloco de 2 horas. E veio o alerta de card parado no PPD-4521."

### 7. Qualidade e próximos passos (6:15 – 7:00)

**Comando (passo 5):** testes automatizados.

> "16 testes automatizados passando, só com a biblioteca padrão do Python. Próximos passos: publicar o app do Google Chat, integrar com o PSOffice por API se houver, considerar os worklogs do Jira e agendar a execução diária. Junto com a solução de commits, cobrimos o time inteiro."

## Vídeo do terminal gerado automaticamente

`video/demo.mp4` (~1min30, 1600×1000, sem áudio) traz a abertura em texto e as cenas 3 a 7, com a espera da consulta ao Jira cortada. Serve de base para narrar por cima (QuickTime/iMovie) e intercalar com a cena do navegador. Para gerar de novo, na raiz do projeto e na rede da CERC: `vhs video/demo.tape` (requer `brew install vhs ffmpeg`).

## Vídeo legendado completo

`video/apresentacao.mp4` (~3min12, 1920×1080, sem áudio, legendas numa faixa abaixo do conteúdo): abertura, as cenas do terminal e o print do card PPD-4775 (`print card.png`, inteiro e depois com zoom no histórico) antes do resultado do Jira real. Cada linha de `video/legendas/*.txt` é uma legenda, exibida por tempo proporcional ao tamanho (~15 caracteres/s, mínimo 3 s). Para mudar o texto e gerar de novo: `./video/montar.sh` (na raiz, na rede da CERC). As legendas são desenhadas por `video/legenda.swift` (AppKit), porque o `ffmpeg` do Homebrew não traz os filtros de legenda.

## Dicas

- Se algo falhar ao vivo, corte e regrave só a cena: cada passo do `demo.sh` é independente (`./demo.sh 4` roda só o passo 4).
- Para um vídeo mais curto (~3 min), use as cenas 1, 3, 4 (só C006 e C009) e 6.
- Exporte em 1080p; o QuickTime salva em `.mov` — se precisar de `.mp4`, use Arquivo → Exportar.
