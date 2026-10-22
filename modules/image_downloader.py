# -*- coding: utf-8 -*-
"""Download de thumbnails do YouTube (CDN pública) com cache local.

Cache por id de vídeo em `output/imagens/{id}.jpg`: a segunda corrida não
refaz o download. Política: direto da CDN do YouTube via requests, sem
serviço intermediário; nunca levanta — falha de rede devolve None e o
template do PDF usa o fallback visual (retângulo rotulado).
"""
import hashlib
import logging
import re
from pathlib import Path

import requests

log = logging.getLogger("pipeline.imagem")

UA = "Mozilla/5.0 (compat; VisaoGlobalPipeline/1.0; uso editorial local)"


def _id_do_video(url):
    m = re.search(r"(?:watch\?v=|youtu\.be/|shorts/)([A-Za-z0-9_-]+)", str(url or ""))
    if m:
        return m.group(1)
    return hashlib.sha256(str(url).encode("utf-8")).hexdigest()[:12]


def buscar(url_thumbnail, url_video, dir_cache="output/imagens"):
    """Baixa a thumbnail; devolve o caminho local ou None (nunca levanta)."""
    if not url_thumbnail:
        return None
    try:
        pasta = Path(dir_cache)
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"{_id_do_video(url_video)}.jpg"
        if destino.exists() and destino.stat().st_size > 1024:
            return str(destino)
        resp = requests.get(url_thumbnail, timeout=(5, 10), headers={"User-Agent": UA})
        resp.raise_for_status()
        if len(resp.content) < 1024:
            log.info("imagem: '%s' muito pequena; ignorada", str(url_thumbnail)[:60])
            return None
        destino.write_bytes(resp.content)
        log.info("imagem: thumbnail baixada -> %s", destino.name)
        return str(destino)
    except Exception as exc:
        log.info("imagem: download ignorado (%s)", type(exc).__name__)
        return None
