# -*- coding: utf-8 -*-
"""Extração do texto principal dos artigos.

Pipeline de duas etapas conforme briefing:
1. newspaper3k (primário) — baixa e parseia a página;
2. trafilatura (fallback) — quando o texto do newspaper tem < ~100 caracteres;
3. fallback_titulo — paywall/página inacessível: título + meta_description
   (e primeiro parágrafo visível da página, se houver HTML parcial).

Sempre grava texto_extraido e metodo_extracao em {'newspaper',
'trafilatura', 'fallback_titulo'}. Completa data_publicacao com
article.publish_date quando a fonte não forneceu.
"""
import logging
import re
from datetime import datetime, timezone

import requests

log = logging.getLogger("pipeline.extractor")

MINIMO_CHARS = 100  # limiar do briefing: fallback abaixo disto


def _limpar(texto):
    return re.sub(r"\n{3,}", "\n\n", texto or "").strip()


def _descricao_do_html(html):
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup
        sopa = BeautifulSoup(html, "html.parser")
        for sel in ("meta[property='og:description']", "meta[name='description']"):
            tag = sopa.select_one(sel)
            if tag and tag.get("content"):
                return tag["content"].strip()
        for p in sopa.find_all("p"):
            txt = p.get_text(" ", strip=True)
            if txt and len(txt) >= 80:
                return txt
    except Exception:
        pass
    return ""


def extrair(artigo, usuario, delay=1.5):
    """Preenche texto_extraido / metodo_extracao em-place e devolve o artigo."""
    url = artigo.get("url", "")
    metodo, texto = None, ""

    texto_newspaper, html, data_url = None, None, None
    try:
        from newspaper import Article
        art = Article(url, fetch_images=False, http_success_codes=[202])
        art.config.NUM_FETCH_THREADS = 1
        art.close()
        art = Article(url)
        art.set_header({"User-Agent": usuario})
        art.download()
        art.parse()
        texto_newspaper = _limpar(art.text)
        html = art.html
        data_url = getattr(art, "publish_date", None)
        if texto_newspaper and len(texto_newspaper) >= MINIMO_CHARS:
            metodo, texto = "newspaper", texto_newspaper
    except Exception as exc:
        log.debug("newspaper falhou em %s: %s", url, exc)

    if metodo is None:
        # Fallback 1: trafilatura sobre o HTML que o newspaper (ou requests) trouxe
        if html is None:
            try:
                resp = requests.get(url, headers={"User-Agent": usuario}, timeout=(10, 40))
                resp.raise_for_status()
                html = resp.text
            except Exception as exc:
                log.debug("requests direto falhou em %s: %s", url, exc)
        if html:
            try:
                import trafilatura
                txt = trafilatura.extract(html, output_format="txt", include_comments=False)
                txt = _limpar(txt or "")
                if len(txt) >= MINIMO_CHARS:
                    metodo, texto = "trafilatura", txt
                elif texto_newspaper:
                    # newspaper trouxe algo curto, mas melhor que nada
                    metodo, texto = "newspaper", texto_newspaper
            except Exception as exc:
                log.debug("trafilatura falhou em %s: %s", url, exc)

    if metodo is None:
        # Fallback 2 (paywall): título + descrição/primeiro parágrafo
        descricao = _descricao_do_html(html) if html else ""
        if not descricao and texto_newspaper:
            descricao = texto_newspaper.split("\n")[0]
        texto = _limpar(artigo.get("titulo", "") or "")
        if descricao:
            texto = f"{texto}\n\n{descricao}"
        metodo = "fallback_titulo"

    if not artigo.get("data_publicacao") and data_url:
        try:
            if data_url.tzinfo is None:
                data_url = data_url.replace(tzinfo=timezone.utc)
            artigo["data_publicacao"] = data_url.astimezone(timezone.utc).isoformat()
        except Exception:
            pass

    artigo["texto_extraido"] = texto
    artigo["metodo_extracao"] = metodo
    return artigo
