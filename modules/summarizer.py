# -*- coding: utf-8 -*-
"""Resumo breve e título traduzido por artigo (PT-BR) via chat OpenRouter.

Loop determinístico: uma chamada por artigo com `response_format: json_object`.
O modelo padrão em produção vem do config (`sumario.modelo`; em 22/10/2026 é
`nvidia/nemotron-3-ultra-550b-a55b:free`). Faz parte do cache idempotente:
artigos já resumidos não gastam chamada — e o título traduzido vai junto.
"""
import json
import logging
import re

from . import openrouter_client as ort

log = logging.getLogger("pipeline.sumario")

_CHAT_INSTRUCAO = (
    "Você é editor do briefing 'Visão Global' de relações internacionais. "
    "Traduza o título original para o Português do Brasil; se o título já "
    "estiver em português, mantenha-o sem alterar o sentido. "
    "O resumo também deve ser em Português: 1 ou 2 frases curtas, factuais e "
    "impessoais, priorizando o fato principal e o gancho internacional dele. "
    "Não invente informações e não adicione opinião. "
    "Seu raciocínio deve ser mínimo (no máximo 2 linhas). "
    "Responda APENAS com JSON no formato "
    '{"titulo_traduzido": "...", "resumo": "..."}'
)


def _extrair_par(conteudo):
    """Extrai (titulo_traduzido, resumo) do JSON do modelo; tolera texto ao redor."""
    if not conteudo:
        return None, None
    texto = conteudo.strip()

    def _campo(dado, nome):
        valor = (dado.get(nome) or "").strip()
        return valor or None

    try:
        dado = json.loads(texto)
        if isinstance(dado, dict):
            return (_campo(dado, "titulo_traduzido"), _campo(dado, "resumo"))
    except json.JSONDecodeError:
        busca = re.search(r"\{[^{}]*\"(?:resumo|titulo_traduzido)\"[^{}]*\}",
                          texto, re.DOTALL)
        if busca:
            try:
                dado = json.loads(busca.group(0))
                return (_campo(dado, "titulo_traduzido"), _campo(dado, "resumo"))
            except json.JSONDecodeError:
                return None, None
    return None, None


def resumir(artigo, config, api_key):
    """Preenche resumo_curto / metodo_resumo in-place. Levanta ErroTerminal p/ cima."""
    conf = config.get("sumario") or {}
    limites = config.get("limites") or {}
    base = (config.get("openrouter") or {}).get("endpoint_base", "https://openrouter.ai/api")

    texto = artigo.get("texto_extraido") or ""
    minimo = int(conf.get("max_caracteres_texto_base", 80))
    if len(texto.strip()) < minimo:
        artigo["resumo_curto"] = None
        artigo["metodo_resumo"] = "sem_conteudo"
        return artigo

    truncar = int(limites.get("truncar_chars", 6000))
    payload = {
        "model": conf.get("modelo", "nvidia/nemotron-3-ultra-550b-a55b:free"),
        "temperature": 0.3,
        # alto: modelos com raciocínio (Nemotron) gastam tokens de
        # pensamento ANTES do JSON; teto baixo => content None (finish=length)
        "max_tokens": int(conf.get("max_tokens", 3000)),
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _CHAT_INSTRUCAO},
            {
                "role": "user",
                "content": (
                    f"TÍTULO: {artigo.get('titulo', '')}\n\nTEXTO:\n{texto[:truncar]}"
                ),
            },
        ],
    }

    resp = ort.post_json(
        f"{base}/v1/chat/completions",
        payload,
        api_key,
        tentativas=int(conf.get("tentativas", 5)),
        backoff_base=float(conf.get("backoff_base_seg", 1.0)),
        backoff_max=float(conf.get("backoff_max_seg", 30.0)),
    )

    conteudo = ((resp.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    uso = resp.get("usage") or {}
    artigo["custo_resumo"] = float(uso.get("cost") or 0.0)
    titulo_traduzido, resumo = _extrair_par(conteudo)
    if not resumo:
        escolha = (resp.get("choices") or [{}])[0]
        log.warning(
            "resumo inválido (%s): finish_reason=%s, content=%r",
            artigo.get("url", "")[:80],
            escolha.get("finish_reason"),
            (conteudo or "")[:80],
        )
    artigo["resumo_curto"] = resumo
    artigo["titulo_traduzido"] = titulo_traduzido
    artigo["metodo_resumo"] = "chat" if resumo else "erro_resumo"
    return artigo
