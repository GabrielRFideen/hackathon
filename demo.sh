#!/usr/bin/env bash
# Passos da demonstração (ver ROTEIRO.md). Uso: ./demo.sh [passo]   (sem argumento roda todos)
set -euo pipefail
cd "$(dirname "$0")"

titulo() { clear; printf '\n\033[1;36m== %s ==\033[0m\n\n' "$1"; }
roda()   { printf '\033[1;33m$ %s\033[0m\n' "$*"; eval "$@"; echo; }
pausa()  { [[ -n "${PASSO:-}" ]] || read -rp $'\033[2m[Enter para continuar]\033[0m '; }
tabela() { python3 -c "import csv,sys; [print('  '.join(f'{c:<12}' for c in r).rstrip()) for r in csv.reader(sys.stdin)]" < "$1"; }

passo1() {
  titulo "1. Dias úteis sem lançamento"
  roda python3 -m apontamento lacunas
  roda "cmp saida/dias_sem_lancamento.csv esperado/dias_sem_lancamento.csv && echo 'IDÊNTICO ao esperado'"
  roda "head -6 saida/dias_sem_lancamento.csv"
}

passo2() {
  titulo "2. Cenários da fixture (cards fictícios)"
  roda python3 -m apontamento executar
  roda tabela saida/sugestoes.csv
  roda tabela saida/sugestoes_origem.csv
  roda "grep -E 'divergencia|card_parado|C014,2026-10-13' saida/alertas.csv"
}

passo3() {
  titulo "3. Notificações (caixa de saída local)"
  roda "python3 -c \"import json,sys; print(json.load(open(sys.argv[1]))['text'])\" saida/outbox/gchat/colaborador009@exemplo.test.json"
  roda "python3 -c \"import email,sys; print(email.message_from_binary_file(open(sys.argv[1],'rb')).get_payload(decode=True).decode())\" saida/outbox/email/rh@empresa.com.eml | head -12"
}

passo4() {
  titulo "4. Jira real (cerc-portal.atlassian.net)"
  roda "python3 -m apontamento executar --jira --dados dados_teste --saida saida_teste | grep -v '^ignorado'"
  roda "grep C061 saida_teste/sugestoes.csv"
  roda "grep C061 saida_teste/sugestoes_origem.csv"
  roda "grep C061 saida_teste/alertas.csv | cut -d, -f2-4"
}

passo5() {
  titulo "5. Testes automatizados"
  roda python3 -m unittest discover -s tests -t .
}

if [[ $# -gt 0 ]]; then
  PASSO=1 "passo$1"
else
  for n in 1 2 3 4 5; do "passo$n"; pausa; done
fi
