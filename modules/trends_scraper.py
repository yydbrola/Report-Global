# -*- coding: utf-8 -*-
"""Radar de tendências: interesse de busca no YouTube via Trends API (trendsapi.ai).

Endpoint único: POST https://api.trendsapi.ai/api (Auth: Bearer TRENDSAPI_KEY).
O SDK oficial (trendsapi-youtube) decodifica por inteiro o envelope de resposta
(`statusCode` + `body` em string — a double-parse manual não é invocada aqui).

Cota free: 100 req/mês — apenas respostas 200 contam. O cache local em
`data/cache_trends.json` congela por seção:
    top_trends   → TTL config `youtube_trends.top_trends_ttl_horas` (padrão 24h)
    série/termo  → TTL `youtube_trends.atualizar_historico_dias` (padrão 7d)
A variação é calculada LOCALMENTE da série (média das últimas N semanas vs N
anteriores, N = janela_variacao_dias / 7): nenhuma requisição extra no cálculo.

Retorno (contrato consumido por main.py / pdf_builder / editorial):
{
  "texto_analise": "",            # preenchido pela camada editorial
  "termos": [{termo, indice_atual, variacao, periodo, status, em_lista_top}],
  "top_trends": [[rank, rotulo], ...],
  "series": {termo: [{date, value}, ...]},   # bruto p/ JSON, ignorado no PDF
}
A chave do ambiente TRENDSAPI_KEY nunca vive no config nem no código.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger("pipeline.trends")

_RAIZ = Path(__file__).resolve().parent.parent
ARQ_CACHE = _RAIZ / "data" / "cache_trends.json"

FEED_YOUTUBE = "YouTube Trending"   # nome exato do feed ao vivo (docs oficiais)


def _carregar_cache():
    if ARQ_CACHE.exists():
        try:
            import json
            return json.loads(ARQ_CACHE.read_text(encoding="utf-8"))
        except Exception as exc:  # arquivo corrompido recomeça do zero
            log.warning("cache_trends.json ilegível (%s); ficha zerada", exc)
    return {}


def _salvar_cache(cache):
    import json
    ARQ_CACHE.parent.mkdir(parents=True, exist_ok=True)
    ARQ_CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def _valido(quando, ttl_horas):
    try:
        dt = datetime.fromisoformat(quando)
        return datetime.now(timezone.utc) - dt <= timedelta(hours=float(ttl_horas))
    except (ValueError, TypeError):
        return False


def _contar_req(cache):
    """Registra requisições bem-sucedidas para acompanhar a cota mensal (100)."""
    mes = datetime.now(timezone.utc).strftime("%Y-%m")
    registro = cache.get("reqs_mes") or {}
    if registro.get("mes") != mes:
        registro = {"mes": mes, "usadas": 0}
    registro["usadas"] = int(registro.get("usadas", 0)) + 1
    cache["reqs_mes"] = registro
    return registro["usadas"]


def _atualiza_top_trends(cliente, conf, cache):
    """Feed ao vivo (1 req quando vencer o TTL)."""
    top = cache.get("top_trends")
    ttl = float(conf.get("top_trends_ttl_horas", 24))
    if top and _valido(top.get("quando"), ttl):
        log.info("trends: top_trends em cache (%d itens, atualizado às %s)",
                 len(top.get("data") or []), str(top.get("quando"))[:16])
        return top.get("data") or []
    try:
        resposta = cliente.get_top_trends(
            type=FEED_YOUTUBE, limit=int(conf.get("limite_top_trends", 10))
        )
    except Exception as exc:
        log.warning("trends: get_top_trends falhou (%s) — usando cache/nothing", exc)
        return (top or {}).get("data") or []
    dados = [[int(r), str(rotulo)] for r, rotulo in (getattr(resposta, "data", None) or [])]
    cache["top_trends"] = {
        "quando": datetime.now(timezone.utc).isoformat(),
        "data": dados,
    }
    usadas = _contar_req(cache)
    log.info("trends: top_trends atualizado (%d itens) — cota mensal: %d/100",
             len(dados), usadas)
    return dados


def _obter_serie(cliente, termo, cache, conf):
    """Série semanal 0-100 do termo (1 req quando vencer o TTL)."""
    series = cache.setdefault("series", {})
    reg = series.get(termo) or {}
    ttl = float(conf.get("atualizar_historico_dias", 7)) * 24
    if reg.get("pontos") and _valido(reg.get("quando"), ttl):
        log.info("trends: série '%s' em cache (%.0f dias, %d pontos)",
                 termo, float(conf.get("atualizar_historico_dias", 7)),
                 len(reg["pontos"]))
        return reg["pontos"]
    try:
        resposta = cliente.get_time_series(termo)  # source=youtube é o default
    except Exception as exc:
        log.warning("trends: série '%s' falhou (%s) — usando cache/nada", termo, exc)
        return reg.get("pontos") or []
    # Free tier devolve ~90 dias; trunca por segurança contratual
    pontos = [{"date": str(p.date), "value": float(p.value)}
              for p in (resposta or [])][:91]
    series[termo] = {
        "quando": datetime.now(timezone.utc).isoformat(),
        "pontos": pontos,
    }
    usadas = _contar_req(cache)
    log.info("trends: série '%s' atualizada (%d pontos) — cota mensal: %d/100",
             termo, len(pontos), usadas)
    return pontos


def _metrica(pontos, janela_dias):
    """indice_atual, variacao e status calculados da própria série (0 req).

    Série semanal: janela_dias/7 pontos recentes vs os N anteriores a eles.
    """
    janela_dias = int(janela_dias or 30)
    semanas = max(1, round(janela_dias / 7))
    if len(pontos) < semanas + 2:  # série insuficiente para comparar
        return None, indice_ultimo(pontos), "estável"
    valores = [p["value"] for p in pontos]
    recentes = valores[-semanas:]
    anteriores = valores[-2 * semanas:-semanas]
    base = sum(anteriores) / len(anteriores)
    nova = sum(recentes) / len(recentes)
    variacao = (nova - base) / base * 100.0 if base > 1e-9 else None
    status = "estável"
    if variacao is not None:
        if variacao >= 2.0:
            status = "alta"
        elif variacao <= -2.0:
            status = "queda"
    return variacao, valores[-1], status


def indice_ultimo(pontos):
    return pontos[-1]["value"] if pontos else 0.0


def coletar_tendencias(config):
    """Produtor do Radar de Tendências. Nunca levanta: erro => sem Radar no PDF."""
    conf = config.get("youtube_trends") or {}
    termos = [str(t).strip() for t in (conf.get("termos_de_interesse") or [])
              if str(t).strip()]
    if not termos:
        log.info("trends: sem termos_de_interesse no config; radar pulado")
        return None
    chave = os.environ.get("TRENDSAPI_KEY", "")
    if not chave:
        log.warning("trends: TRENDSAPI_KEY ausente; PDF sai sem Radar")
        return None
    try:
        from trendsapi_youtube import TrendsAPI
    except ImportError:
        log.error("trends: pacote ausente (pip install trendsapi-youtube)")
        return None

    cliente = TrendsAPI(api_key=chave)
    cache = _carregar_cache()
    top = _atualiza_top_trends(cliente, conf, cache)
    top_rotulos = [rotulo for _rank, rotulo in top]

    janela = conf.get("janela_variacao_dias", 30)
    saida = []
    for termo in termos:
        pontos = _obter_serie(cliente, termo, cache, conf)
        em_top = any(termo.casefold() in rotulo.casefold() for rotulo in top_rotulos)
        if not pontos:
            log.warning("trends: '%s' sem série — fuori da tabela do Radar", termo)
            continue
        variacao, indice, status = _metrica(pontos, janela)
        saida.append({
            "termo": termo,
            "indice_atual": round(indice),
            "variacao": ("—" if variacao is None else f"{variacao:+.0f}%"),
            "periodo": f"vs. {janela} dias",
            "status": status,
            "em_lista_top": em_top,
        })
        log.info("trends: %-12s índice %3d | variação %6s | %s%s",
                 termo, round(indice),
                 ("—" if variacao is None else f"{variacao:+.0f}%"), status,
                 " | EM ALTA NO FEED" if em_top else "")

    # Ordem executiva: maior interesse de busca primeiro
    saida.sort(key=lambda t: -float(t.get("indice_atual") or 0))
    _salvar_cache(cache)

    if not saida:
        log.warning("trends: nenhum termo monitorado com série válida")
        return None
    return {
        "texto_analise": "",          # preenchido pela camada editorial
        "termos": saida,
        "top_trends": top,
        "series": {t["termo"]: cache.get("series", {}).get(t["termo"], {}).get("pontos", [])
                   for t in saida},
        "contagem": cache.get("reqs_mes"),
    }
