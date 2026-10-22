# -*- coding: utf-8 -*-
"""Resumo breve por artigo (1–2 frases, PT-BR) via chat OpenRouter.

Loop determinístico: uma chamada por artigo com `response_format: json_object`
(modelo `minimax/minimax-m3.1-flash:free` suporta, conforme doc do modelo).
Faz parte do cache idempotente: artigos já resumidos não gastam chamada.
"""
import json
import logging
import re

from . import openrouter_client as ort

log = logging.getLogger("pipeline.sumario")

_CHAT_INSTRUCAO = (
    "Você é editor do briefing 'Visão Global' de relações internacionais. "
    "Resuma o texto em 1 ou 2 frases curtas, factuais e impessoais, em português do Brasil, "
    "priorizando o fato principal e o que há de internacional-alcançável nele. "
    "Não invente informações e não adicione opinião. "
    "Seu raciocínio deve ser mínimo (no máximo 2 linhas). "
    'Responda APENAS com JSON no formato {"resumo": "..."}'
)


def _extrair_resumo(conteudo):
    if not conteudo:
        return None
    texto = conteudo.strip()
    try:
        dado = json.loads(texto)
        return (dado.get("resumo") or "").strip() or None
    except json.JSONDecodeError:
        passa = re.search(r"\{[^{}]*\"resumo\"[^{}]*\}", texto, re.DOTALL)
        if passa:
            try:
                dado = json.loads(passa.group(0))
                return (dado.get("resumo") or "").strip() or None
            except json.JSONDecodeError:
                return None
    return None


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
        "model": conf.get("modelo", "minimax/minimax-m3.1-flash:free"),
        "temperature": 0.3,
        # alto: modelos com raciocínio (MiniMax M3.1) gastam tokens de
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
    resumo = _extrair_resumo(conteudo)
    if not resumo:
        escolha = (resp.get("choices") or [{}])[0]
        log.warning(
            "resumo inválido (%s): finish_reason=%s, content=%r",
            artigo.get("url", "")[:80],
            escolha.get("finish_reason"),
            (conteudo or "")[:80],
        )
    artigo["resumo_curto"] = resumo
    artigo["metodo_resumo"] = "chat" if resumo else "erro_resumo"
    return artigo
