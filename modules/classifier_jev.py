# -*- coding: utf-8 -*-
"""Classificação temática via JEV (System One) na Decisions API da OpenRouter.

Um pedido Choice por artigo:
    POST {endpoint_base}/alpha/decisions
    state = {"titulo": ..., "texto": texto truncado}
    questions.tema = {"type": "choice", "instructions": ..., "criteria": {chave: descrição}}

A resposta chega com `answers.tema = {type, choice, confidence?, probabilities?}`.
A chave vencedora deve bater com uma categoria do config; caso contrário o
artigo fica sem tema (erro logado). O texto é truncado em `limites.truncar_chars`
contexto: jev-1.13 tem 32k tokens; o truncamento mantém custo e payload sob controle.
"""
import logging

from . import openrouter_client as ort

log = logging.getLogger("pipeline.jev")


def construir_criteria(config):
    """{chave_config: texto_criterio} na ordem do config.yaml."""
    return {
        chave: info["criterio_jev"]
        for chave, info in (config.get("categorias") or {}).items()
    }


def classificar(artigo, config, api_key):
    """Preenche tema/tema_confianca/tema_probabilidades/custo in-place. Levanta ErroTerminal p/ cima."""
    base = (config.get("openrouter") or {}).get("endpoint_base", "https://openrouter.ai/api")
    jestev = config.get("jev") or {}
    limites = config.get("limites") or {}
    truncar = int(limites.get("truncar_chars", 6000))

    texto = (artigo.get("texto_extraido") or "")
    if not texto.strip():
        texto = artigo.get("titulo", "")

    payload = {
        "model": jestev.get("modelo", "typesafe/jev-1.13"),
        "state": {"titulo": artigo.get("titulo", ""), "texto": texto[:truncar]},
        "questions": {
            "tema": {
                "type": "choice",
                "instructions": (
                    "Which single theme best describes this international news item? "
                    "Pick the most specific applicable theme."
                ),
                "criteria": construir_criteria(config),
            },
        },
        "session_id": "visao-global-pipeline",
    }

    resp = ort.post_json(
        f"{base}/alpha/decisions",
        payload,
        api_key,
        tentativas=int(jestev.get("tentativas", 5)),
        backoff_base=float(jestev.get("backoff_base_seg", 1.0)),
        backoff_max=float(jestev.get("backoff_max_seg", 30.0)),
    )

    resposta_tema = (resp.get("answers") or {}).get("tema") or {}
    tipos_ok = resposta_tema.get("type") == "choice"
    vencedor = resposta_tema.get("choice") if tipos_ok else None
    criterias = construir_criteria(config)
    if vencedor and vencedor not in criterias:
        log.warning("JEV devolveu opção inesperada '%s' (artigo %s)", vencedor, artigo.get("url"))
        vencedor = None

    uso = resp.get("usage") or {}
    artigo["tema"] = vencedor
    artigo["tema_confianca"] = resposta_tema.get("confidence") if tipos_ok else None
    artigo["tema_probabilidades"] = resposta_tema.get("probabilities") if tipos_ok else None
    artigo["tema_modelo"] = resp.get("model") or payload["model"]
    artigo["custo_classificacao"] = float(uso.get("cost") or 0.0)
    artigo["classificacao_erro"] = None if vencedor else "resposta_invalida"
    return artigo
