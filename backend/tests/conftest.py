"""Configuração da suíte.

Toda a suíte é OFFLINE: nenhum teste toca o Supabase real nem chama provedor
de IA. Isso é uma escolha, não uma limitação — os testes rodam em segundos,
sem chave e sem rede, o que é o que faz alguém realmente executá-los antes de
commitar.

A persistência do cooldown é desligada aqui porque o `.env.local` de
desenvolvimento aponta para o Supabase REAL: sem esta linha, um teste de
rotação gravaria cooldown de provedores fictícios no banco de produção.
"""

import pytest

from app import ai_providers
from app.config import settings
from app.services import traducao


@pytest.fixture(autouse=True)
def offline_rotation():
    ai_providers._persistence_enabled = False
    ai_providers._cooldowns.clear()
    ai_providers._last_cooldown_refresh = None
    yield
    ai_providers._cooldowns.clear()


@pytest.fixture(autouse=True)
def offline_deepl(monkeypatch):
    """Sem DeepL na suíte. O `.env.local` tem a chave real, e sem isto os
    testes do treino traduziam de verdade: gastavam cota, dependiam de rede e
    levaram a suíte de 15 para 25 segundos. Quem testa a tradução liga a chave
    e troca o cliente HTTP por um falso."""
    monkeypatch.setattr(settings, "deepl_api_key", "")
    traducao._cache.clear()
    traducao._glossario = None
    yield
    traducao._cache.clear()
    traducao._glossario = None
