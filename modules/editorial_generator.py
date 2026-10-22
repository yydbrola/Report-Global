# -*- coding: utf-8 -*-
"""Camada editorial do briefing (opcional, flag editorial.ativo).

Motor padrão: smolagents — ToolCallingAgent com duas ferramentas
(`ler_dados_relatorio` para ler o digest da edição e `salvar_editorial` para
devolver os textos) dirigindo um modelo OpenRouter. A saída estruturada preenche:

- panorama_geral: lista de 2–3 parágrafos (exige o template do PDF);
- destaques_por_tema: texto por chave de temática (destaque editorial);
- titulo_capa / subtitulo_capa: capa gerada por IA (fallback estático do config).

Motor alternativo `directo`: uma única chamada de chat pedindo o mesmo JSON —
ativa via `editorial.motor: directo` a qualquer hora. Ambos os engines falham
silenciosamente: a edição sai sem camada editorial (o PDF degrada limpo).
"""
import json
import logging

from . import openrouter_client as ort

log = logging.getLogger("pipeline.editorial")

_RESULTADO = {"salvo": False, "editorial": {}}
_DADOS_EDICAO = {}


def _preparar_digest(artigos, config, radar_tendencias=None):
    """Imagem compacta da edição para o agente/editor decidir o que destacar."""
    cats = config.get("categorias") or {}
    digest = {"artigos_analisados": 0, "temas": []}
    por_tema = {}
    for art in artigos:
        digest["artigos_analisados"] += 1
        chave = art.get("tema") or "outros"
        if chave not in cats:
            chave = "outros"
        por_tema.setdefault(chave, []).append(art)
    for chave, lista in por_tema.items():
        info_cat = cats.get(chave) or {}
        atos = []
        for art in lista:
            atos.append({
                "titulo": art.get("titulo", ""),
                "resumo": (art.get("resumo_curto") or "")[:340],
                "confianca": (
                    int(art["tema_confianca"] * 100)
                    if isinstance(art.get("tema_confianca"), (int, float)) else None
                ),
                "fonte": art.get("fonte", ""),
            })
        digest["temas"].append({
            "chave": chave,
            "nome": info_cat.get("nome", chave),
            "rotulo": info_cat.get("rotulo", chave.upper()),
            "quantidade": len(lista),
            "artigos": atos,
        })
    if radar_tendencias and radar_tendencias.get("termos"):
        digest["radar_tendencias"] = {
            "termos": [{
                "termo": t.get("termo"),
                "indice_atual": t.get("indice_atual"),
                "variacao": t.get("variacao"),
                "periodo": t.get("periodo"),
                "status": t.get("status"),
            } for t in radar_tendencias["termos"]],
            "top_trends_youtube": [str(rotulo) for _r, rotulo
                                   in (radar_tendencias.get("top_trends") or [])][:6],
        }
    _DADOS_EDICAO.clear()
    _DADOS_EDICAO.update(digest)
    return digest


def _ferramentas():
    try:
        from smolagents import tool
    except ImportError:  # smolagents antigos
        from smolagents.tools import tool

    @tool
    def ler_dados_relatorio() -> str:
        """Dados completos da edição atual: quantidade por tema e candidatos a destaque.
        Returns:
            JSON com 'artigos_analisados' e lista de 'temas' (nome, rotulo, quantidade, artigos com titulo/resumo/confianca/fonte).
        """
        return json.dumps(_DADOS_EDICAO, ensure_ascii=False)

    @tool
    def salvar_editorial(panorama_geral: str, destaques_por_tema: str,
                         titulo_capa: str, subtitulo_capa: str,
                         analise_tendencias: str = "") -> str:
        """Entrega o corpo editorial estruturado da edição.
        Args:
            panorama_geral: JSON array com 2-3 parágrafos em português do Brasil (strings).
            destaques_por_tema: JSON object mapeando a chave da temática para um texto de destaque (2-3 frases; omita temas irrelevantes).
            titulo_capa: manchete da capa em CAIXA ALTA, no máximo 24 caracteres, pode ter '\n' para duas linhas.
            subtitulo_capa: subtítulo da capa em uma frase (português do Brasil).
            analise_tendencias: OBRIGATÓRIO apenas se o digest tiver 'radar_tendencias': um único parágrafo (2-4 frases) interpretando o Radar (use EXATAMENTE os índices/percentuais fornecidos; nunca invente números). Caso contrário, string vazia.
        Returns:
            'salvo' em sucesso ou 'erro: motivo'.
        """
        try:
            pano_bruto = json.loads(panorama_geral)
            destaques_brutos = json.loads(destaques_por_tema)
        except json.JSONDecodeError as exc:
            return f"erro: json_invalido ({exc})"
        if not isinstance(pano_bruto, list):
            pano_bruto = [pano_bruto]
        _RESULTADO["editorial"] = {
            "panorama_geral": [str(p).strip() for p in pano_bruto if str(p).strip()][:4],
            "destaques_por_tema": {str(k): str(v).strip()
                                    for k, v in (destaques_brutos or {}).items() if str(v).strip()},
            "titulo_capa": (titulo_capa or "").strip() or None,
            "subtitulo_capa": (subtitulo_capa or "").strip() or None,
            "analise_tendencias": (analise_tendencias or "").strip() or None,
        }
        _RESULTADO["salvo"] = True
        return "salvo"

    return [ler_dados_relatorio, salvar_editorial]


def _construir_modelo(config, api_key):
    """OpenAIServerModel (smolagents novo) → OpenAIModel (velho) → LiteLLMModel."""
    base = (config.get("openrouter") or {}).get("endpoint_base", "https://openrouter.ai/api")
    api_base = f"{base}/v1"
    config_ed = config.get("editorial") or {}
    modelo_id = config_ed.get("modelo", "minimax/minimax-m3.1-flash:free")

    try:
        from smolagents import OpenAIServerModel
        return OpenAIServerModel(model_id=modelo_id, api_base=api_base, api_key=api_key)
    except ImportError:
        pass
    try:
        from smolagents import OpenAIModel
        return OpenAIModel(model_id=modelo_id, api_base=api_base, api_key=api_key)
    except ImportError:
        pass
    from smolagents import LiteLLMModel
    return LiteLLMModel(model_id=f"openrouter/{modelo_id}", api_key=api_key)


_TAREFA = """Você é o editor-chefe do briefing diário 'Visão Global', de relações internacionais.

Passos:
1. Chame ler_dados_relatorio() e leia os temas e artigos da edição.
2. Escreva o corpo editorial e chame salvar_editorial UMA vez. Diretrizes:
   - panorama_geral: 2-3 parágrafos coesos em português do Brasil (sem listas),
     conectando os principais movimentos geopolíticos da edição; tom editorial;
     cada parágrafo entre 2 e 4 frases.
   - destaques_por_tema: para cada tema com artigos relevantes, 2-3 frases em
     português apontando o que mais importa (use chaves TAL QUAIS estão no digest).
   - titulo_capa: manchete da capa em CAIXA ALTA, até 24 caracteres; pode usar
     '\\n' para separar em duas linhas. Deve sintetizar o espírito da edição.
   - subtitulo_capa: uma frase de subtítulo em português do Brasil.
   - analise_tendencias: SE o digest contiver 'radar_tendencias', escreva um
     único parágrafo (2-4 frases) interpretando os termos em alta — conectando
     com as notícias da edição quando houver relação. Use EXATAMENTE os
     índices (0-100) e percentuais fornecidos no radar; NUNCA invente ou
     re-aproxime números. Se não houver radar no digest, passe string vazia.
Não escreva textos fora da chamada salvar_editorial."""


def _via_smolagents(config, api_key):
    from smolagents import ToolCallingAgent

    agente = ToolCallingAgent(
        tools=_ferramentas(),
        model=_construir_modelo(config, api_key),
        max_steps=int((config.get("editorial") or {}).get("max_passos", 8)),
    )
    agente.run(_TAREFA)
    if not _RESULTADO["salvo"]:
        raise RuntimeError("agente não chamou salvar_editorial")
    return _RESULTADO["editorial"]


_PROMPT_DIRECTO = (
    "Você é o editor-chefe do briefing diário 'Visão Global' de relações internacionais.\n"
    "Recebe abaixo o digest da edição (temas + artigos). Produza o corpo editorial em "
    "português do Brasil e responda APENAS com JSON:\n"
    "{\n"
    '  "panorama_geral": ["parágrafo 1", "parágrafo 2"],\n'
    '  "destaques_por_tema": {"chave_tema": "texto de 2-3 frases"},\n'
    '  "titulo_capa": "MANCHETE EM CAIXA ALTA (até 24 caracteres)",\n'
    '  "subtitulo_capa": "frase de subtítulo",\n'
    '  "analise_tendencias": "parágrafo único ou string vazia"\n'
    "}\n"
    "Regras: panorama com 2-3 parágrafos coesos; destaques por tema com 2-3 frases "
    "usando as chaves do digest; título em caixa alta até 24 caracteres.\n"
    "analise_tendencias: obrigatório APENAS se o digest tiver 'radar_tendencias' — "
    "um parágrafo único (2-4 frases) interpretando o radar, citando os números "
    "EXATAMENTE como fornecidos (nunca invente índices/percentuais) e conectando "
    "com as notícias quando fizer sentido. Sem radar: string vazia.\n\n"
    "DIGEST DA EDIÇÃO:\n{digest}"
)


def _via_directo(config, api_key, digest):
    conf = config.get("editorial") or {}
    confirm = {chave: info.get("nome") for chave, info in (config.get("categorias") or {}).items()}
    import copy
    dig = copy.deepcopy(digest)
    dig["_legenda_chaves"] = confirm
    base = (config.get("openrouter") or {}).get("endpoint_base", "https://openrouter.ai/api")
    payload = {
        "model": conf.get("modelo", "minimax/minimax-m3.1-flash:free"),
        "temperature": 0.4,
        # alto: modelos com raciocínio (MiniMax M3.1) gastam tokens de
        # pensamento antes do JSON; teto baixo => content None
        "max_tokens": int(conf.get("max_tokens", 3000)),
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": _PROMPT_DIRECTO.format(
            digest=json.dumps(dig, ensure_ascii=False))}],
    }
    resp = ort.post_json(f"{base}/v1/chat/completions", payload, api_key,
                         tentativas=int(conf.get("tentativas", 5)),
                         backoff_base=float(conf.get("backoff_base_seg", 1.0)),
                         backoff_max=float(conf.get("backoff_max_seg", 30.0)))
    mensagem = (resp.get("choices") or [{}])[0].get("message") or {}
    conteudo = mensagem.get("content")
    if not conteudo:
        motivo = ((resp.get("choices") or [{}])[0].get("finish_reason"))
        raise RuntimeError(
            f"resposta sem conteúdo (finish_reason={motivo}); "
            "aumente editorial.max_tokens"
        )
    bruto = json.loads(conteudo)
    if isinstance(bruto, str):  # JSON duplamente codificado
        bruto = json.loads(bruto)
    return _padronizar(bruto, config)


def _padronizar(bruto, config):
    cats = set((config.get("categorias") or {}).keys())
    pano = bruto.get("panorama_geral")
    if isinstance(pano, str):
        pano = [pano]
    pano = [str(p).strip() for p in (pano or []) if str(p).strip()][:4]
    destaques = {
        str(k).strip(): str(v).strip()
        for k, v in (bruto.get("destaques_por_tema") or {}).items()
        if str(v).strip()
    }
    destaques = {k: v for k, v in destaques.items() if k in cats}
    return {
        "panorama_geral": pano,
        "destaques_por_tema": destaques,
        "titulo_capa": (bruto.get("titulo_capa") or "").strip() or None,
        "subtitulo_capa": (bruto.get("subtitulo_capa") or "").strip() or None,
        "analise_tendencias": (bruto.get("analise_tendencias") or "").strip() or None,
    }


def gerar_editorial(artigos, config, api_key, radar_tendencias=None):
    """Devolve o editorial da edição; nunca levanta — erro significa 'sem editorial'."""
    config_ed = config.get("editorial") or {}
    if not config_ed.get("ativo", True):
        log.info("editorial desativado no config; pulando camada editorial")
        return {"ativo": False}
    digest = _preparar_digest(artigos, config, radar_tendencias)
    _RESULTADO["salvo"], _RESULTADO["editorial"] = False, {}

    motor = (config_ed.get("motor") or "smolagents").lower()
    bruto = None
    if api_key:
        try:
            if motor == "smolagents":
                bruto = _via_smolagents(config, api_key)
            else:
                bruto = _via_directo(config, api_key, digest)
        except Exception as exc:
            log.warning("editorial via %s falhou (%s); tentando modo directo",
                        motor, exc)
            if motor == "smolagents":
                try:
                    bruto = _via_directo(config, api_key, digest)
                except Exception as exc2:
                    log.warning("editorial modo directo também falhou: %s", exc2)
    else:
        log.warning("sem OPENROUTER_API_KEY; editorial ignorado")

    if not bruto:
        return {"ativo": False}

    padronizado = _padronizar(bruto, config)
    if not padronizado.get("titulo_capa"):
        padronizado["titulo_capa"] = (config_ed.get("titulo_capa_fallback") or "").strip() or None
    if not padronizado.get("subtitulo_capa"):
        padronizado["subtitulo_capa"] = (config_ed.get("subtitulo_capa_fallback") or "").strip() or None
    padronizado["ativo"] = bool(padronizado["panorama_geral"] or padronizado["destaques_por_tema"])
    padronizado["motor"] = motor if bruto else None
    return padronizado
