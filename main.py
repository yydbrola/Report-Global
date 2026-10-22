# -*- coding: utf-8 -*-
"""Orquestrador do pipeline Visão Global.

Uso:
    python main.py                     execução completa (JEV + resumo + editorial + PDF + rascunho)
    python main.py --dry-run           só scraping + extração (não gasta API)
    python main.py --no-editorial      PDF sem camada editorial
    python main.py --no-email          não cria rascunho no Gmail
    python main.py --no-sumario        pula resumo por artigo
    python main.py --trends            inclui o Radar de Tendências (Trends API)
    python main.py --youtube           vídeos por termo em alta do Radar (yt-dlp)
    python main.py --email-only        re-envia o último PDF (teste de Gmail)
    python main.py --limit 10          cap de artigos para teste barato
    python main.py --config CAMINHO    config alternativo (default: config.yaml)

A chave OPENROUTER_API_KEY lê-se do ambiente; nunca vive no config.
"""
import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from modules import (classifier_jev, editorial_generator, extractor,
                     gmail_sender, openrouter_client as ort, pdf_builder,
                     scraper, summarizer, trends_scraper, youtube_scraper)

RAIZ = Path(__file__).resolve().parent
DIR_DADOS = RAIZ / "data"
DIR_SAIDA = RAIZ / "output"
DELAY_INTERCHAMADAS = 0.5

log = logging.getLogger("pipeline.main")


def carregar_config(caminho):
    with open(caminho, "r", encoding="utf-8") as ptr:
        return yaml.safe_load(ptr)


def salvar_json(caminho, obj):
    Path(caminho).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _chave_url(url):
    return hashlib.sha256(str(url).encode("utf-8")).hexdigest()[:16]


def _carregar_cache(ativo):
    if not ativo:
        return {}
    arq = DIR_DADOS / "cache.json"
    if arq.exists():
        try:
            return json.loads(arq.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("cache.json corrompido; ficha zerada")
    return {}


def _salvar_cache(cache):
    DIR_DADOS.mkdir(parents=True, exist_ok=True)
    (DIR_DADOS / "cache.json").write_text(
        json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def _cache_valido(registro, ttl_dias):
    try:
        quando = datetime.fromisoformat(registro["quando"])
        return datetime.now(timezone.utc) - quando <= timedelta(days=int(ttl_dias))
    except (KeyError, ValueError, TypeError):
        return False


def _herdar_cache(artigo, cache, ttl_dias, tons_validos=None, temas_validos=None):
    """Aplica tema/resumo em cache ao artigo antes de gastar chamadas de API.

    tons_validos: chaves atuais da taxonomia de tons; tom em cache fora dela
    (ex.: `diplomatico_oficial` aposentado) é invalidado para reclassificação.
    temas_validos: idem para temas — renomear categoria no config reclassifica.
    """
    reg = cache.get(_chave_url(artigo.get("url", ""))) or {}
    bloco = reg.get("tema")
    if bloco and _cache_valido(bloco, ttl_dias):
        for campo in ("tema", "tema_confianca", "tema_probabilidades",
                      "tema_modelo", "tema_forcado", "tom", "tom_confianca",
                      "tom_probabilidades", "tom_modelo", "tom_forcado"):
            if campo in bloco:
                artigo[campo] = bloco[campo]
        if (temas_validos is not None and artigo.get("tema")
                and artigo["tema"] not in temas_validos):
            log.info("cache: tema '%s' fora da taxonomia atual; reclassificando %s",
                     artigo["tema"], str(artigo.get("url", ""))[:60])
            for campo in ("tema", "tema_confianca", "tema_probabilidades",
                          "tema_modelo", "tema_forcado"):
                artigo.pop(campo, None)
        if (tons_validos is not None and artigo.get("tom")
                and artigo["tom"] not in tons_validos):
            log.info("cache: tom '%s' fora da taxonomia atual; reclassificando %s",
                     artigo["tom"], str(artigo.get("url", ""))[:60])
            for campo in ("tom", "tom_confianca", "tom_probabilidades",
                          "tom_modelo", "tom_forcado"):
                artigo.pop(campo, None)
        artigo["custo_classificacao"] = 0.0
        artigo["do_cache"] = True
    bloco = reg.get("resumo")
    if bloco and "resumo_curto" in bloco and bloco.get("resumo_curto"):
        if _cache_valido(bloco, ttl_dias):
            artigo["resumo_curto"] = bloco["resumo_curto"]
            artigo["metodo_resumo"] = "cache"
            artigo["do_cache"] = True
            if bloco.get("titulo_traduzido"):
                artigo["titulo_traduzido"] = bloco["titulo_traduzido"]


def _gravar_cache(cache, artigo, campos, secao):
    """Secao 'tema' grava só quando classificação teve sucesso; 'resumo' idem."""
    bloco = {k: artigo[k] for k in campos if artigo.get(k) is not None}
    if not bloco:
        return
    bloco["quando"] = datetime.now(timezone.utc).isoformat()
    cache.setdefault(_chave_url(artigo.get("url", "")), {})[secao] = bloco


def passo_scrape_extrai(config, limite_total):
    artigos = scraper.coletar(config, limite_total=limite_total)
    data = datetime.now().strftime("%Y-%m-%d")
    salvar_json(DIR_DADOS / f"raw_{data}.json", artigos)
    usuario = config.get(
        "user_agent", "VisaoGlobalPipeline/1.0 (uso editorial local; robots respeitado)"
    )
    delay = float((config.get("limites") or {}).get("delay_segundos", 2.5)) / 2.0
    falhas = 0
    for artigo in artigos:
        try:
            extractor.extrair(artigo, usuario, delay=delay)
        except Exception as exc:
            artigo["texto_extraido"] = artigo.get("titulo", "")
            artigo["metodo_extracao"] = "fallback_titulo"
            falhas += 1
            log.error("extração falhou (%s): %s", artigo.get("url"), exc)
        log.info("extração [%s] %s chars — %s",
                 artigo.get("metodo_extracao"),
                 len(artigo.get("texto_extraido") or ""),
                 artigo.get("url", "")[:80])
    salvar_json(DIR_DADOS / f"extraidos_{data}.json", artigos)
    log.info("extração concluída: %d artigos, %d falha(s)", len(artigos), falhas)
    return artigos


def passo_classificar(artigos, config, api_key, cache, ttl_dias):
    if not api_key:
        log.warning("OPENROUTER_API_KEY ausente: classificação pulada (artigos ficarão em 'outros')")
        return artigos
    suc, falha = 0, 0
    for artigo in artigos:
        if artigo.get("tema"):
            suc += 1
            continue
        try:
            classifier_jev.classificar(artigo, config, api_key)
        except (ort.ErroTerminal, ort.ErroRetry) as exc:
            falha += 1
            artigo["classificacao_erro"] = str(exc)[:180]
            log.error("classificação %s: %s", artigo.get("url", "")[:80], exc)
        else:
            if artigo.get("tema"):
                _gravar_cache(cache, artigo,
                              ("tema", "tema_confianca", "tema_probabilidades",
                               "tema_modelo", "tema_forcado", "tom",
                               "tom_confianca", "tom_probabilidades",
                               "tom_modelo", "tom_forcado"), "tema")
                suc += 1
        time.sleep(DELAY_INTERCHAMADAS)
    log.info("classificação concluída: %d ok, %d falha(s)", suc, falha)
    return artigos


def passo_resumir(artigos, config, api_key, cache, ttl_dias, desativar=False):
    if desativar:
        log.info("resumo por artigo desativado via flag")
        return artigos
    if not api_key:
        log.warning("sem OPENROUTER_API_KEY: resumo pulado")
        return artigos
    suc, pulados, falha = 0, 0, 0
    for artigo in artigos:
        if artigo.get("resumo_curto"):
            suc += 1
            continue
        if (artigo.get("texto_extraido") or "").strip().count(" ") < 3:
            pulados += 1
            artigo["metodo_resumo"] = artigo.get("metodo_resumo") or "sem_conteudo"
            continue
        try:
            summarizer.resumir(artigo, config, api_key)
        except (ort.ErroTerminal, ort.ErroRetry) as exc:
            falha += 1
            artigo["metodo_resumo"] = "erro_resumo"
            log.error("resumo %s: %s", artigo.get("url", "")[:80], exc)
        else:
            if artigo.get("resumo_curto"):
                _gravar_cache(cache, artigo,
                              ("resumo_curto", "titulo_traduzido"), "resumo")
                suc += 1
        time.sleep(DELAY_INTERCHAMADAS)
    log.info("resumo concluído: %d ok, %d falha(s), %d sem conteúdo",
             suc, falha, pulados)
    return artigos


def _resumo_execucao(artigos, editorial, radar=None, em_cache=0, limite=None):
    custo_classif = sum(float(a.get("custo_classificacao") or 0.0) for a in artigos)
    custo_resumo = sum(float(a.get("custo_resumo") or 0.0) for a in artigos)
    custo_editorial = float((editorial or {}).get("custo_editorial") or 0.0)
    return {
        "artigos": len(artigos),
        "limite_solicitado": limite,
        "em_cache": em_cache,
        "com_tema_especifico": sum(
            1 for a in artigos if a.get("tema") and a["tema"] != "outros"),
        "com_resumo": sum(1 for a in artigos if a.get("resumo_curto")),
        "videos_youtube": sum(1 for a in artigos if a.get("tipo_fonte") == "youtube"),
        "custo_classificacao_usd": round(custo_classif, 6),
        "custo_resumo_usd": round(custo_resumo, 6),
        "custo_editorial_usd": round(custo_editorial, 6),
        "custo_trends_usd": 0.0,  # cota gratuita da Trends API; custo por req n/a
        "custo_total_usd": round(custo_classif + custo_resumo + custo_editorial, 6),
        "editorial_ativo": bool((editorial or {}).get("ativo")),
        "radar_tendencias": bool(radar),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pipeline Visão Global")
    parser.add_argument("--config", default=str(RAIZ / "config.yaml"))
    parser.add_argument("--no-editorial", action="store_true")
    parser.add_argument("--no-email", action="store_true")
    parser.add_argument("--no-sumario", action="store_true")
    parser.add_argument("--email-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--trends", action="store_true")
    parser.add_argument("--youtube", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    config = carregar_config(args.config)
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    DIR_DADOS.mkdir(exist_ok=True)
    DIR_SAIDA.mkdir(exist_ok=True)

    if args.email_only:
        arquivos = sorted(DIR_SAIDA.glob("dados_*.json"))
        pdocs = sorted(DIR_SAIDA.glob("relatorio_ri_*.pdf"))
        if not arquivos or not pdocs:
            log.error("não achei dados_/relatorio_ de runs anteriores em output/")
            return 2
        dados = json.loads(arquivos[-1].read_text(encoding="utf-8"))
        gmail_sender.entregar(config, pdocs[-1], dados)
        return 0

    limite = args.limit or int(
        (config.get("limites") or {}).get("max_artigos_total", 60)
    )
    artigos = passo_scrape_extrai(config, limite)
    if args.dry_run:
        log.info("dry-run: parado após extração (nenhuma chamada de API)")
        log.info("prévia OK — %d | %s", len(artigos), artigos[0].get("titulo", "") if artigos else "")
        return 0

    cache_config = config.get("cache") or {}
    cache = _carregar_cache(bool(cache_config.get("ativo", True)))
    ttl = int(cache_config.get("ttl_dias", 7))
    tons_validos = set((config.get("tons") or {}).keys())
    temas_validos = set((config.get("categorias") or {}).keys())
    for artigo in artigos:
        _herdar_cache(artigo, cache, ttl, tons_validos, temas_validos)

    # Radar ANTES da classificação: o --youtube precisa dos termos em alta.
    radar_tendencias = None
    if args.trends:
        try:
            radar_tendencias = trends_scraper.coletar_tendencias(config)
        except Exception as exc:
            log.warning("radar de tendências falhou (PDF sai sem Radar): %s", exc)

    if args.youtube:
        if radar_tendencias:
            videos = youtube_scraper.coletar_videos(radar_tendencias, config)
            for video in videos:
                _herdar_cache(video, cache, ttl, tons_validos, temas_validos)
            artigos.extend(videos)
        else:
            log.warning("youtube: --youtube exige --trends; sem termos em alta para buscar")

    em_cache = sum(1 for a in artigos if a.get("do_cache"))
    if em_cache:
        log.info("%d artigo(s) reaproveitado(s) do cache (TTL %d dias)", em_cache, ttl)

    artigos = passo_classificar(artigos, config, api_key, cache, ttl)
    artigos = passo_resumir(artigos, config, api_key, cache, ttl,
                            desativar=args.no_sumario)
    _salvar_cache(cache)

    editorial = (
        {"ativo": False}
        if args.no_editorial
        else editorial_generator.gerar_editorial(
            artigos, config, api_key, radar_tendencias=radar_tendencias)
    )
    if radar_tendencias is not None:
        radar_tendencias["texto_analise"] = (
            (editorial or {}).get("analise_tendencias") or ""
        )

    stats_execucao = _resumo_execucao(artigos, editorial, radar=radar_tendencias,
                                   em_cache=em_cache, limite=limite)
    hoje_ext = datetime.now().strftime("%d/%m/%Y")
    dados_rel = pdf_builder.gerar(
        artigos, config, editorial,
        dir_saida=str(DIR_SAIDA), dir_dados=str(DIR_DADOS), data_execucao=hoje_ext,
        radar_tendencias=radar_tendencias, estatisticas=stats_execucao,
    )
    dados_rel["resumo_execucao"] = stats_execucao

    salvar_json(DIR_SAIDA / f"dados_{datetime.now().strftime('%Y-%m-%d')}.json", dados_rel)

    if not args.no_email:
        try:
            gmail_sender.entregar(config, dados_rel.get("pdf"), dados_rel)
        except Exception as exc:
            log.warning("entrega no Gmail falhou (PDF fica em %s): %s", dados_rel.get("pdf"), exc)

    stats = dados_rel["resumo_execucao"]
    log.info("FIM — artigos %d | com tema %d | com resumo %d | custo US$ %.4f | PDF %s",
             stats["artigos"], stats["com_tema_especifico"], stats["com_resumo"],
             stats["custo_total_usd"], dados_rel.get("pdf"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
