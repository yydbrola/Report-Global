# -*- coding: utf-8 -*-
"""Adaptador: formato do pipeline -> dicionário que o pdf_template consome.

Responsabilidades: montar `dados` no contrato do template editorial
(capa, panorama, temáticas com rotulo/destaque, artigos com titulo/resumo/
fonte/data/confianca/link), calcular custo acumulado, numerar a edição
(persistido em data/edicao.json) e chamar pdf_template.gerar_relatorio.
KeepTogether por artigo vem de dentro do template.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import pdf_template

log = logging.getLogger("pipeline.pdf")

FUSO = ZoneInfo("America/Sao_Paulo")


def _data_legivel(iso):
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return None


def _fmt_custo(valor):
    if valor <= 0:
        return "US$ 0,00"
    if valor < 0.05:
        return "US$ " + f"{valor:.4f}".replace(".", ",")
    return "US$ " + f"{valor:.2f}".replace(".", ",")


def _proxima_edicao(dir_dados):
    arq = Path(dir_dados) / "edicao.json"
    if arq.exists():
        try:
            return int((json.loads(arq.read_text(encoding="utf-8"))).get("proxima", 1))
        except (ValueError, json.JSONDecodeError):
            pass
    return 1


def _salvar_proxima_edicao(dir_dados, numero):
    arq = Path(dir_dados) / "edicao.json"
    arq.write_text(json.dumps({"proxima": numero + 1}, ensure_ascii=False), encoding="utf-8")


def montar_dados(artigos, config, editorial, data_execucao=None, dir_dados="data",
                 radar_tendencias=None):
    """Constrói o dicionário no contrato do pdf_template (sem gerar PDF)."""
    cats = config.get("categorias") or {}
    config_ed = config.get("editorial") or {}
    hoje = datetime.now(FUSO)
    data_str = data_execucao or hoje.strftime("%d/%m/%Y")

    custo_total = sum(float(a.get("custo_classificacao") or 0.0) for a in artigos)
    editorial_ativo = bool(editorial.get("ativo"))
    modelo_ia = (config.get("jev") or {}).get("modelo", "typesafe/jev-1.13")

    tematicas = []
    for chave, info in cats.items():
        itens = [a for a in artigos if (a.get("tema") or "outros") == chave]
        if not itens:
            continue
        lista_artigos = []
        for a in itens:
            confianca = a.get("tema_confianca")
            lista_artigos.append({
                "titulo": a.get("titulo", "Sem título"),
                "resumo": a.get("resumo_curto"),
                "fonte": a.get("fonte", "Não informada"),
                "data": _data_legivel(a.get("data_publicacao")) or data_str,
                "confianca": int(round(confianca * 100))
                            if isinstance(confianca, (int, float)) else None,
                "link": a.get("url", ""),
                "tipo_fonte": a.get("tipo_fonte"),
                "canal": a.get("canal"),
                "views": a.get("views"),
                "engajamento_pct": a.get("engajamento_pct"),
                "tom": a.get("tom"),
            })
        tematicas.append({
            "nome": info.get("nome", chave),
            "rotulo": (info.get("rotulo") or info.get("nome", chave)).upper(),
            "destaque": ((editorial.get("destaques_por_tema") or {}).get(chave))
                        if editorial_ativo else None,
            "artigos": lista_artigos,
        })

    dados = {
        "data": data_str,
        "edicao": f"BRIEFING DIÁRIO  |  EDIÇÃO {_proxima_edicao(dir_dados):03d}",
        "artigos_analisados": len(artigos),
        "modelo_ia": modelo_ia,
        "custo": _fmt_custo(custo_total),
        "titulo_capa": (editorial.get("titulo_capa")
                        or config_ed.get("titulo_capa_fallback")
                        or "O MUNDO EM MOVIMENTO"),
        "subtitulo_capa": (editorial.get("subtitulo_capa")
                           or config_ed.get("subtitulo_capa_fallback")
                           or "Análise diária da agenda internacional."),
        "panorama_geral": [p for p in (editorial.get("panorama_geral") or [])
                           if editorial_ativo and str(p).strip()],
        "radar_tendencias": radar_tendencias,
        "analise_narrativas": (editorial.get("analise_narrativas") or "")
                              if editorial_ativo else "",
        "tematicas": tematicas,
    }
    return dados


def gerar(artigos, config, editorial, dir_saida="output", dir_dados="data",
          data_execucao=None, radar_tendencias=None):
    """Gera o PDF da edição e devolve o dict `dados` (com a chave extra 'pdf').

    O nº da edição é computado uma única vez aqui — chamadas separadas de
    montar_dados na mesma execução fazem o contador incrementar em dobro.
    """
    Path(dir_saida).mkdir(parents=True, exist_ok=True)
    dados = montar_dados(artigos, config, editorial, data_execucao, dir_dados,
                         radar_tendencias)
    data_ref = datetime.now(FUSO).strftime("%Y-%m-%d")
    caminho = Path(dir_saida) / f"relatorio_ri_{data_ref}.pdf"

    pdf_template.gerar_relatorio(dados, str(caminho))
    numero_usado = int((dados.get("edicao") or "000").split("EDIÇÃO")[-1].strip())
    _salvar_proxima_edicao(dir_dados, numero_usado)
    dados["pdf"] = str(caminho)
    log.info("PDF gerado: %s (edição %03d)", caminho, numero_usado)
    return dados

