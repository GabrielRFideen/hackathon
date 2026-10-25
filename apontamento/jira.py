"""Cards do Jira no formato interno usado pelo `timeline`.

Formato interno (o mesmo de `fixtures/jira_cards.json`):

    {"key": "ECL-101", "summary": "...", "assignee": "email" | null, "labels": [...],
     "status": "status atual",
     "changelog": [{"at": "2026-10-09T09:00", "field": "status" | "assignee", "from": ..., "to": ...}]}

`at` é hora local sem fuso; `assignee` é o e-mail do usuário.
"""

import base64
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def ler_fixture(caminho: Path) -> list[dict]:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


class JiraClient:
    """Busca cards e changelog na API REST v3 do Jira Cloud e converte para o formato interno."""

    def __init__(self, base_url: str, email: str, token: str, fuso: str = "America/Sao_Paulo"):
        self.base_url = base_url.rstrip("/")
        cred = base64.b64encode(f"{email}:{token}".encode()).decode()
        self.headers = {"Authorization": f"Basic {cred}", "Accept": "application/json"}
        self.fuso = ZoneInfo(fuso)
        self._emails: dict[str, str | None] = {}
        # Proxies corporativos (ex.: Netskope) reassinam o TLS com CAs sem a extensão key usage,
        # recusadas pelo modo estrito do Python 3.13+. A cadeia continua sendo verificada.
        self._ssl = ssl.create_default_context()
        self._ssl.verify_flags &= ~ssl.VERIFY_X509_STRICT

    def _get(self, caminho: str, tentativas: int = 4, **params) -> dict:
        """GET com retry/backoff para timeout, HTTP 429 e 5xx."""
        url = f"{self.base_url}{caminho}?{urllib.parse.urlencode(params)}"
        for n in range(tentativas):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=self.headers), timeout=60,
                                            context=self._ssl) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code != 429 and e.code < 500 or n == tentativas - 1:
                    raise
                espera = int(e.headers.get("Retry-After") or 2 ** n)
            except (TimeoutError, urllib.error.URLError):
                if n == tentativas - 1:
                    raise
                espera = 2 ** n
            time.sleep(espera)

    def _email(self, account_id: str | None) -> str | None:
        if not account_id:
            return None
        if account_id not in self._emails:
            self._emails[account_id] = self._get("/rest/api/3/user", accountId=account_id).get("emailAddress")
        return self._emails[account_id]

    def _account_ids(self, emails: list[str]) -> list[str]:
        """accountId dos usuários com esses e-mails; e-mails sem usuário no Jira são ignorados."""
        ids = []
        for email in emails:
            for u in self._get("/rest/api/3/user/search", query=email):
                if (u.get("emailAddress") or "").lower() == email.lower():
                    self._emails[u["accountId"]] = u["emailAddress"]
                    ids.append(u["accountId"])
                    break
        return ids

    @staticmethod
    def _instante(valor: str) -> datetime:
        return datetime.strptime(valor, "%Y-%m-%dT%H:%M:%S.%f%z")

    def _hora_local(self, valor: str) -> str:
        return self._instante(valor).astimezone(self.fuso).replace(tzinfo=None).isoformat(timespec="minutes")

    def _eventos(self, historicos: list[dict]) -> list[dict]:
        # Ordena pelo instante completo: `at` é truncado no minuto e o Jira devolve do mais novo ao mais antigo.
        eventos = []
        for hist in sorted(historicos, key=lambda h: (self._instante(h["created"]), int(h["id"]))):
            for item in hist["items"]:
                if item["field"] == "status":
                    de, para = item.get("fromString"), item.get("toString")
                elif item["field"] == "assignee":
                    de, para = self._email(item.get("from")), self._email(item.get("to"))
                else:
                    continue
                eventos.append({"at": self._hora_local(hist["created"]), "field": item["field"],
                                "from": de, "to": para})
        return eventos

    def _changelog(self, key: str) -> list[dict]:
        historicos, inicio = [], 0
        while True:
            pagina = self._get(f"/rest/api/3/issue/{key}/changelog", startAt=inicio, maxResults=100)
            historicos += pagina["values"]
            inicio += len(pagina["values"])
            if pagina.get("isLast", True) or not pagina["values"]:
                return self._eventos(historicos)

    def buscar_cards(self, desde: str, assignees: list[str] | None = None, jql_extra: str = "") -> list[dict]:
        """Cards atualizados desde `desde`. Com `assignees` (e-mails), busca só os cards dessas pessoas."""
        jql = f'updated >= "{desde}" AND assignee IS NOT EMPTY'
        if assignees is not None:
            ids = self._account_ids(assignees)
            if not ids:
                return []
            jql += " AND assignee IN (" + ", ".join(f'"{i}"' for i in ids) + ")"
        if jql_extra:
            jql += f" AND ({jql_extra})"
        cards, token = [], None
        while True:
            params = {"jql": jql, "fields": "summary,status,assignee,labels", "expand": "changelog",
                      "maxResults": 100}
            if token:
                params["nextPageToken"] = token
            pagina = self._get("/rest/api/3/search/jql", **params)
            for issue in pagina["issues"]:
                f, log = issue["fields"], issue.get("changelog", {})
                historicos = log.get("histories", [])
                completo = "changelog" in issue and log.get("total", len(historicos)) <= len(historicos)
                cards.append({
                    "key": issue["key"],
                    "summary": f.get("summary", ""),
                    "assignee": (f.get("assignee") or {}).get("emailAddress"),
                    "labels": f.get("labels", []),
                    "status": f["status"]["name"],
                    "changelog": self._eventos(historicos) if completo else self._changelog(issue["key"]),
                })
            token = pagina.get("nextPageToken")
            if not token:
                return cards
