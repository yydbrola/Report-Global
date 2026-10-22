# -*- coding: utf-8 -*-
"""Coleta de notícias de relações internacionais.

Suporta fontes de dois tipos (config.yaml):
- rss  : feedparser lê o feed, extrai título/link/data de publicação;
- html : requests + BeautifulSoup varre a página listando links de notícias.

Regras de polite scraping: robots.txt por domínio (urllib.robotparser, cache),
delay configurável entre requisições e User-Agent identificado. URLs são
normalizadas (sem query/trailing slash) e desduplicadas entre fontes.
"""
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import requests
from bs4 import BeautifulSoup

log = logging.getLogger("pipeline.scraper")

USER_AGENT_DEFAULT = "VisaoGlobalPipeline/1.0 (uso editorial local; robots respeitado)"
_scraping = {}


def _normalizar_url(url):
    p = urlparse(url.strip())
    host = p.netloc.lower()
    caminho = p.path.rstrip("/")
    return f"{host}{caminho}"


def _robots_permitido(url, user_agent):
    """True se robots.txt do domínio permite o fetch; falha de rede → cauteloso False."""
    dominio = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    rp = _scraping.get("robots", {}).get(dominio)
    if rp is None:
        rp = RobotFileParser()
        try:
            rp.set_url(f"{dominio}/robots.txt")
            rp.read()
        except Exception as exc:
            log.warning("robots.txt não lido para %s (%s): tratando como não permitido", dominio, exc)
            rp = None
        _scraping.setdefault("robots", {})[dominio] = rp
    if rp is None:
        return False
    try:
        return rp.can_fetch(user_agent, url)
    except Exception as exc:
        log.warning("erro avaliando robots para %s: %s", url, exc)
        return False


def _parse_entry_date(entry):
    for attr in ("published_parsed", "updated_parsed"):
        st = getattr(entry, attr, None)
        if st:
            try:
                return datetime.fromtimestamp(
                    __import__("calendar").timegm(st), tz=timezone.utc
                ).isoformat()
            except Exception:
                pass
    return None


def _coletar_rss(fonte, usuario, limite, delay):
    log.info("RSS %s: %s", fonte["nome"], fonte["url"])
    if not _robots_permitido(fonte["url"], usuario):
        log.warning("robots.txt proíbe fetch da fonte %s; pulando.", fonte["nome"])
        return []
    parse = feedparser.parse(fonte["url"], request_headers={"User-Agent": usuario})
    itens = []
    for entry in parse.entries[:limite]:
        link = getattr(entry, "link", None)
        titulo = getattr(entry, "title", None)
        if not link or not titulo:
            continue
        itens.append({
            "titulo": titulo.strip(),
            "url": link.strip(),
            "fonte": fonte["nome"],
            "tipo_fonte": "rss",
            "data_publicacao": _parse_entry_date(entry),
        })
    time.sleep(delay)
    return itens


_NOTICIAS_CSS = [
    "article a[href]",
    "h2 a[href]", "h3 a[href]",
    "a[data-testid='card-link']", "a[aria-label]",
]


def _coletar_html(fonte, usuario, limite, delay):
    log.info("HTML %s: %s", fonte["nome"], fonte["url"])
    if not _robots_permitido(fonte["url"], usuario):
        log.warning("robots.txt proíbe fetch da fonte %s; pulando.", fonte["nome"])
        return []
    resp = requests.get(
        fonte["url"],
        headers={"User-Agent": usuario},
        timeout=(10, 40),
    )
    resp.raise_for_status()
    sopa = BeautifulSoup(resp.text, "html.parser")

    dominio = urlparse(fonte["url"]).netloc
    vistos, itens = set(), []
    for seletor in _NOTICIAS_CSS:
        for a in sopa.select(seletor):
            href = a.get("href")
            if not href:
                continue
            if href.startswith("/"):
                href = f"https://{dominio}{href}"
            if not href.startswith(("https://", "http://")):
                continue
            alvo = urlparse(href)
            if alvo.netloc != dominio or len(alvo.path.split("/")) < 3:
                continue
            titulo = a.get_text(" ", strip=True)
            if not titulo or len(titulo) < 24 or href in vistos:
                continue
            vistos.add(href)
            itens.append({
                "titulo": titulo,
                "url": href,
                "fonte": fonte["nome"],
                "tipo_fonte": "html",
                "data_publicacao": None,
            })
            if len(itens) >= limite:
                break
        if len(itens) >= limite:
            break
    time.sleep(delay)
    return itens


def coletar(config, limite_total=None):
    """Coleta todas as fontes ativas; retorna lista dedup por URL normalizada."""
    usuario = config.get("user_agent", USER_AGENT_DEFAULT)
    limites = config.get("limites", {})
    max_por_fonte = int(limites.get("max_artigos_por_fonte", 25))
    delay = float(limites.get("delay_segundos", 2.5))

    brutos, visto = [], set()
    for fonte in config.get("fontes", []):
        if not fonte.get("ativo", True):
            continue
        try:
            if fonte.get("tipo", "rss") == "rss":
                itens = _coletar_rss(fonte, usuario, max_por_fonte, delay)
            else:
                itens = _coletar_html(fonte, usuario, max_por_fonte, delay)
        except Exception as exc:
            log.error("fonte %s falhou: %s", fonte.get("nome"), exc)
            continue
        for it in itens:
            chave = _normalizar_url(it["url"])
            if chave in visto:
                continue
            visto.add(chave)
            it["url_normalizada"] = chave
            brutos.append(it)
        if limite_total and len(brutos) >= limite_total:
            brutos = brutos[:limite_total]
            break

    log.info("Coleta concluída: %d artigos brutos de %d fontes ativas",
             len(brutos), sum(1 for f in config.get("fontes", []) if f.get("ativo", True)))
    return brutos
