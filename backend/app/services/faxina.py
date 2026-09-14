"""A faxina das tabelas de eventos, que sem ela crescem para sempre.

Duas tabelas recebem uma linha por acontecimento e ninguém lê a linha velha:

- `pathr_rate_event` — um uso contado por um limite (services/limites.py). A
  maior janela de limite é de um dia; dois dias de folga cobrem a janela
  inteira de quem está no meio dela.
- `pathr_error_event` — cada 500 (services/erros.py). A varredura diária lê as
  últimas 26 horas; trinta dias guardam o bastante para ver se um erro voltou.

Roda no disparo de hora em hora (routers/jobs.py), e não a cada uso: o
caminho de uma requisição não deve pagar por um DELETE, e uma vez por hora
mantém as tabelas pequenas sem sorteio.

Os DELETEs usam os índices que já existem: `occurred_at` em
`pathr_error_event` (0022) e `(action, key, created_at)` em `pathr_rate_event`
(0020) — esta tabela guarda só dois dias, então o que sobra para varrer é
pouco mesmo sem índice só em `created_at`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger("pathr.faxina")

# (tabela, coluna de tempo, quanto guardar)
RETENCAO: tuple[tuple[str, str, timedelta], ...] = (
    ("pathr_rate_event", "created_at", timedelta(days=2)),
    ("pathr_error_event", "occurred_at", timedelta(days=30)),
    # IP e navegador de cada entrada, troca de senha, chave… é dado pessoal:
    # seis meses bastam para investigar abuso, e depois disso não há motivo
    # (LGPD, necessidade) para guardar.
    ("pathr_security_event", "created_at", timedelta(days=180)),
)


def apagar_eventos_velhos(supabase: Any, agora: Optional[datetime] = None) -> dict[str, Optional[int]]:
    """Apaga o que passou da retenção. Devolve quantas linhas saíram de cada
    tabela, ou None para a que falhou — uma tabela fora do ar não impede a
    faxina da outra, nem o disparo dos avisos que chamou isto."""
    agora = agora or datetime.now(timezone.utc)
    apagadas: dict[str, Optional[int]] = {}
    for tabela, coluna, guardar in RETENCAO:
        corte = (agora - guardar).isoformat()
        try:
            resultado = supabase.table(tabela).delete().lt(coluna, corte).execute()
            apagadas[tabela] = len(resultado.data or [])
        except Exception:  # noqa: BLE001
            logger.warning("faxina de %s falhou", tabela, exc_info=True)
            apagadas[tabela] = None
    return apagadas
