# -*- coding: utf-8 -*-
"""Classificação via JEV (System One) na Decisions API da OpenRouter.

Um POST com ATÉ DUAS perguntas choice no MESMO payload:
    POST {endpoint_base}/alpha/decisions
    state     = {"titulo": ..., "texto": texto truncado}
    questions.tema = {"type": "choice", ..., criteria das categorias}
    questions.tom  = {"type": "choice", ..., criteria dos tons} — SOMENTE
                     para artigos com tipo_fonte == 'youtube' (Goal 1.5);
                     notícias de texto ficam sem tom (tom = None).

Regra de segurança (Goal 1.5): confidence da resposta vencedora < 0.60 =>
tema forçado p/ 'outros' e tom p/ 'outros_nao_classificado', com log. Se a
confidence NÃO chegar na resposta, o resultado é mantido (sem reprovação).

Resposta esperada:
    answers.tema / answers.tom = {type, choice, confidence?, probabilities?}
Chave vencedora fora do config => sem valor (erro logado). Texto truncado em
`limites.truncar_chars`; jev-1.13 tem 32k tokens.
"""
import logging

from . import openrouter_client as ort

log = logging.getLogger("pipeline.jev")

LIMITE_CONFIANCA = 0.60
FALLBACK_TEMA = "outros"
FALLBACK_TOM = "outros_nao_classificado"


def construir_criteria(config):
    """{chave_config: texto_criterio} das categorias, na ordem do config.yaml."""
    return {
        chave: info["criterio_jev"]
        for chave, info in (config.get("categorias") or {}).items()
    }


def construir_criteria_tons(config):
    """{chave_config: texto_criterio} dos tons do discurso."""
    return {
        chave: info["criterio_jev"]
        for chave, info in (config.get("tons") or {}).items()
    }


def _resposta(bloco, criterias):
    """Espera {type, choice, confidence?, probabilities?}; devolve (choice, confidence, probabilities)."""
    ok = isinstance(bloco, dict) and bloco.get("type") == "choice"
    ch = bloco.get("choice") if ok else None
    if ch and ch not in criterias:
        log.warning("JEV devolveu opção inesperada '%s'", ch)
        ch = None
    return ch, (bloco.get("confidence") if ok else None), \
        (bloco.get("probabilities") if ok else None)


def _revisar_confianca(valor, confianca, fallback, rotulo, artigo):
    """Regra de segurança 60%: devolve (valor_final, forçado?). Sem confidence, mantém."""
    if valor and isinstance(confianca, (int, float)) and confianca < LIMITE_CONFIANCA:
        log.warning("Confiança JEV: %s %.2f < %.2f → FORÇADO '%s' (%s)",
                    rotulo, confianca, LIMITE_CONFIANCA, fallback, str(artigo.get('url'))[:80])
        return fallback, True
    return valor, False


def classificar(artigo, config, api_key):
    """Preenche tema/tom + confianças/custo in-place. Levanta ErroTerminal p/ cima."""
    base = (config.get("openrouter") or {}).get("endpoint_base", "https://openrouter.ai/api")
    jestev = config.get("jev") or {}
    limites = config.get("limites") or {}
    truncar = int(limites.get("truncar_chars", 6000))

    texto = (artigo.get("texto_extraido") or "")
    if not texto.strip():
        texto = artigo.get("titulo", "")

    questions = {
        "tema": {
            "type": "choice",
            "instructions": (
                "Which single theme best describes this international news item? "
                "Pick the most specific applicable theme. If in doubt (low confidence), "
                "pick the fallback category."
            ),
            "criteria": construir_criteria(config),
        },
    }
    video = (artigo.get("tipo_fonte") == "youtube") and construir_criteria_tons(config)
    if video:
        questions["tom"] = {
            "type": "choice",
            "instructions": (
                "Which single tone best describes the way this content was "
                "communicated? Judge the rhetoric, not the facts."
            ),
            "criteria": video,
        }

    payload = {
        "model": jestev.get("modelo", "typesafe/jev-1.13"),
        "state": {"titulo": artigo.get("titulo", ""), "texto": texto[:truncar]},
        "questions": questions,
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

    answers = resp.get("answers") or {}
    tema, tema_cf, tema_p = _resposta(answers.get("tema"), construir_criteria(config))
    tema, tema_forcado = _revisar_confianca(tema, tema_cf, FALLBACK_TEMA, "tema", artigo)

    tom, tom_cf, tom_p = (None, None, None)
    tom_forcado = False
    if "tom" in questions:
        tom, tom_cf, tom_p = _resposta(answers.get("tom"), video)
        tom, tom_forcado = _revisar_confianca(tom, tom_cf, FALLBACK_TOM, "tom", artigo)
    artigo["tom"] = tom
    artigo["tom_confianca"] = tom_cf
    artigo["tom_probabilidades"] = tom_p

    uso = resp.get("usage") or {}
    artigo["tema"] = tema
    artigo["tema_confianca"] = tema_cf
    artigo["tema_probabilidades"] = tema_p
    artigo["tema_modelo"] = resp.get("model") or payload["model"]
    artigo["tema_forcado"] = tema_forcado
    artigo["tom_forcado"] = tom_forcado
    artigo["custo_classificacao"] = float(uso.get("cost") or 0.0)
    artigo["classificacao_erro"] = None if tema else "resposta_invalida"
    return artigo
