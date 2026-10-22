# -*- coding: utf-8 -*-
"""Adaptador: formato do pipeline -> dicionário que o pdf_template consome.

Contrato do template editorial (capa, radar, dashboard, ficha técnica):
- dados_tendencias: {texto_analise, termos[{termo, indice_atual, variacao,
  periodo, status, series[{date, value}]}]}  — série alimenta o Sparkline
- tematicas: [{nome, rotulo, destaque, artigos[...]}, ...] com artigo
  {titulo, resumo, fonte, data, confianca, link, tipo_fonte, canal, views,
  engajamento_pct, likes, thumbnail_path, tom, tom_chip{...}}
- auditoria: dados REAIS de execução (funil, cache, custo por camada,
  modelos) para a Ficha Técnica — nada de números de demonstração.

Downloads de thumbnail ficam cacheados em output/imagens (image_downloader).
KeepTogether por artigo e sparkline vivem dentro do template.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import image_downloader, pdf_template

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


def _tom_chip(artigo, tons):
    """Payload do chip de tom exibido no card de vídeo (rotulos + top-2)."""
    chave = artigo.get("tom")
    if not chave:
        return None
    probs = artigo.get("tom_probabilidades") or {}
    top = sorted(probs.items(), key=lambda p: -float(p[1] or 0))[:2]
    return {
        "termo": artigo.get("termo_busca"),
        "tom_label": (tons.get(chave) or {}).get("nome") or chave,
        "confianca_pct": (round(float(artigo.get("tom_confianca")) * 100)
                          if isinstance(artigo.get("tom_confianca"), (int, float))
                          else None),
        "top": [{
            "nome": (tons.get(k) or {}).get("nome") or k,
            "pct": round(float(v) * 100),
        } for k, v in top if isinstance(v, (int, float))],
        "forcado": bool(artigo.get("tom_forcado")),
    }


def _artigo_pdf(a, tons, data_str, dir_saida):
    confianca = a.get("tema_confianca")
    thumb_url = a.get("thumbnail_url")
    return {
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
        "likes": a.get("likes"),
        "tom": a.get("tom"),
        "tom_chip": _tom_chip(a, tons),
        "thumbnail_path": (
            image_downloader.buscar(thumb_url, a.get("url"),
                                    dir_cache=str(Path(dir_saida) / "imagens"))
            if a.get("tipo_fonte") == "youtube" and thumb_url else None
        ),
        "pull_quote": a.get("pull_quote"),
    }


def _auditoria(artigos, config, editorial, stats):
    fontes = config.get("fontes") or []
    ativas = sum(1 for f in fontes if f.get("ativo", True))
    custo_c = float((stats or {}).get("custo_classificacao_usd") or 0.0)
    custo_r = float((stats or {}).get("custo_resumo_usd") or 0.0)
    custo_e = float((stats or {}).get("custo_editorial_usd") or 0.0)
    total = custo_c + custo_r + custo_e
    return {
        "fontes_lidas": f"{ativas} fontes ativas de {len(fontes)} configuradas (RSS; robots.txt respeitado)",
        "total_artigos": (stats or {}).get("artigos", len(artigos)),
        "funil": (
            "coletados {art} → com tema {tema} → com resumo {res} "
            "(reaproveitados do cache: {cache}; vídeos do YouTube: {vid})"
        ).format(
            art=(stats or {}).get("artigos", len(artigos)),
            tema=(stats or {}).get("com_tema_especifico", 0),
            res=(stats or {}).get("com_resumo", 0),
            cache=(stats or {}).get("em_cache", 0),
            vid=(stats or {}).get("videos_youtube", 0),
        ),
        "custo_estimado": _fmt_custo(total),
        "custo_por_camada": [
            ("Classificação tema/tom", custo_c),
            ("Resumo por artigo", custo_r),
            ("Camada editorial", custo_e),
        ],
        "modelos_ia": (
            "JEV {jev} (tema/tom) · {sum} (resumo) · {ed} (editorial, motor directo)"
        ).format(
            jev=(config.get("jev") or {}).get("modelo", "typesafe/jev-1.13"),
            sum=(config.get("sumario") or {}).get("modelo", "—"),
            ed=(config.get("editorial") or {}).get("modelo", "—"),
        ),
        "nota_metodologica": (
            "Classificações (tema, tom, confiança) são atribuídas por modelos "
            "probabilísticos automatizados; itens abaixo do limiar de "
            "confiança 0.60 recebem a categoria de fallback e são marcados. "
            "São estimativas de apoio exploratório — não substituem a "
            "verificação humana nas fontes originais (links de ABRIR FONTE)."
        ),
    }


def montar_dados(artigos, config, editorial, data_execucao=None, dir_dados="data",
                 radar_tendencias=None, estatisticas=None, dir_saida="output"):
    """Constrói o dicionário no contrato do pdf_template (sem gerar PDF)."""
    cats = config.get("categorias") or {}
    tons = config.get("tons") or {}
    config_ed = config.get("editorial") or {}
    hoje = datetime.now(FUSO)
    data_str = data_execucao or hoje.strftime("%d/%m/%Y")

    custo_total = (
        float((estatisticas or {}).get("custo_total_usd") or 0.0)
        or sum(float(a.get("custo_classificacao") or 0.0) for a in artigos)
    )
    editorial_ativo = bool(editorial.get("ativo"))
    modelo_ia = (config.get("jev") or {}).get("modelo", "typesafe/jev-1.13")

    tematicas = []
    for chave, info in cats.items():
        itens = [a for a in artigos if (a.get("tema") or "outros") == chave]
        if not itens:
            continue
        tematicas.append({
            "nome": info.get("nome", chave),
            "rotulo": (info.get("rotulo") or info.get("nome", chave)).upper(),
            "destaque": ((editorial.get("destaques_por_tema") or {}).get(chave))
                        if editorial_ativo else None,
            "artigos": [_artigo_pdf(a, tons, data_str, dir_saida) for a in itens],
        })

    radar = radar_tendencias or {}
    series = radar.get("series") or {}
    termos = []
    for item in radar.get("termos") or []:
        pontos = (series.get(item.get("termo")) or [])[-14:]
        termos.append({
            "termo": item.get("termo"),
            "indice_atual": item.get("indice_atual"),
            "variacao": item.get("variacao"),
            "periodo": item.get("periodo"),
            "status": item.get("status"),
            "series": [{"date": str(p.get("date", "")), "value": p.get("value")}
                       for p in pontos if isinstance(p, dict)],
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
        "dados_tendencias": {
            "texto_analise": radar.get("texto_analise", ""),
            "termos": termos,
        },
        "analise_narrativas": (editorial.get("analise_narrativas") or "")
                              if editorial_ativo else "",
        "tematicas": tematicas,
        "auditoria": _auditoria(artigos, config, editorial, estatisticas),
    }
    return dados


def gerar(artigos, config, editorial, dir_saida="output", dir_dados="data",
          data_execucao=None, radar_tendencias=None, estatisticas=None):
    """Gera o PDF da edição e devolve o dict `dados` (com a chave extra 'pdf').

    O nº da edição é computado uma única vez aqui — chamadas separadas de
    montar_dados na mesma execução fazem o contador incrementar em dobro.
    """
    Path(dir_saida).mkdir(parents=True, exist_ok=True)
    dados = montar_dados(artigos, config, editorial, data_execucao, dir_dados,
                         radar_tendencias, estatisticas, dir_saida)
    data_ref = datetime.now(FUSO).strftime("%Y-%m-%d")
    caminho = Path(dir_saida) / f"relatorio_ri_{data_ref}.pdf"

    try:
        pdf_template.gerar_relatorio(dados, str(caminho))
    except Exception:
        caminho_dbg = Path(dir_saida) / f"dados_{data_ref}_crash.json"
        log.warning("template falhou; dados salvos em %s para reprodução offline",
                    caminho_dbg)
        try:
            caminho_dbg.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        except Exception:
            log.exception("falha ao gravar dados de crash")
        raise
    numero_usado = int((dados.get("edicao") or "000").split("EDIÇÃO")[-1].strip())
    _salvar_proxima_edicao(dir_dados, numero_usado)
    dados["pdf"] = str(caminho)
    log.info("PDF gerado: %s (edição %03d)", caminho, numero_usado)
    return dados
