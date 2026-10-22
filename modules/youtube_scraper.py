# -*- coding: utf-8 -*-
"""Busca dinâmica de vídeos no YouTube a partir dos termos em alta do Radar.

Goal 1.5: nada de canais fixos — cada termo do Radar com status 'alta'
dispara `ytsearch{n}` no YouTube via yt-dlp (API Python). A transcrição
(pt/en, youtube-transcript-api) vira o corpo de texto do "artigo"; sem
transcrição usa-se a descrição do vídeo (metodo_extracao: descricao_youtube).

Metadados seguem no artigo para a tarja do PDF e para a pergunta de TOM no
JEV: tipo_fonte='youtube', termo_busca, canal, views, likes, engajamento_pct.

Política: nunca levanta — termo que falha é logado e pulado; sem termos em
alta ou sem dependência instalada, coletar_videos devolve [].
"""
import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs

log = logging.getLogger("pipeline.youtube")


def _transcrever(video_id):
    """Texto da transcrição (pt→en) ou None. Suporta API 1.x e 0.x."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        log.warning("youtube: pacote youtube-transcript-api ausente")
        return None
    try:  # API 1.x
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=["pt", "en"])
        texto = " ".join(seg.text for seg in fetched)
        return texto.strip() or None
    except Exception:
        pass
    try:  # API 0.x
        lista = YouTubeTranscriptApi.list_transcripts(video_id)
        tr = lista.find_transcript(["pt", "en"])
        return " ".join(seg["text"] for seg in tr.fetch()).strip() or None
    except Exception as exc:
        log.info("youtube: sem transcrição pt/en (%s) — %s", video_id,
                 type(exc).__name__)
        return None


def _id_do_video(url):
    """Extrai o id de watch?v=…, youtu.be/… ou do próprio caminho."""
    caminho = str(url or "")
    qs = parse_qs(urlparse(caminho).query).get("v")
    if qs:
        return qs[0]
    final = urlparse(caminho).path.rstrip("/").split("/")[-1]
    return final or caminho


def _montar_artigo(entry, termo, min_views, dias):
    """Dict no contrato padrão do pipeline; None = vídeo descartado."""
    video_id = entry.get("id") or ""
    url = entry.get("webpage_url") or (f"https://www.youtube.com/watch?v={video_id}"
                                       if video_id else "")
    if not url:
        return None
    views = entry.get("view_count")
    if isinstance(views, (int, float)) and views < min_views:
        log.info("youtube: '%s' descartado (%.0f views < %d)",
                 str(entry.get("title"))[:60], views, min_views)
        return None

    data_iso = None
    brutal = entry.get("upload_date")
    if brutal and len(brutal) == 8:
        try:
            data_iso = datetime.strptime(brutal, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            data_iso = None
    if data_iso:
        limite = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%d")
        if data_iso < limite:
            log.info("youtube: '%s' descartado (publicado %s, fora da janela de %d dias)",
                     str(entry.get("title"))[:60], data_iso, dias)
            return None

    likes = entry.get("like_count")
    engajamento = round(likes / views * 100.0, 1) \
        if isinstance(views, (int, float)) and views \
        and isinstance(likes, (int, float)) and likes is not None else 0.0

    transcricao = _transcrever(video_id) if video_id else None
    if transcricao:
        texto, metodo = transcricao, "transcricao_youtube"
    else:
        texto = (entry.get("description") or "").strip()
        metodo = "descricao_youtube" if texto else "fallback_titulo"
    texto = texto or entry.get("title") or ""

    canal = (entry.get("channel") or entry.get("uploader") or "YouTube")
    return {
        "titulo": (entry.get("title") or "").strip() or "Sem título",
        "url": url,
        "fonte": canal,
        "data_publicacao": data_iso,
        "texto_extraido": texto,
        "metodo_extracao": metodo,
        "tipo_fonte": "youtube",
        "termo_busca": termo,
        "canal": canal,
        "views": views if isinstance(views, (int, float)) else None,
        "likes": likes if isinstance(likes, (int, float)) else None,
        "engajamento_pct": engajamento,
    }


def buscar_videos_por_termo(termo, config):
    """Busca `ytsearch{top_n}:{termo}` e devolve artigos-prontos (nunca levanta)."""
    conf = config.get("youtube_busca") or {}
    limite = int(conf.get("top_n_videos", 3))
    min_views = int(conf.get("min_views", 1000))
    dias = int(conf.get("dias_retroativos", 2))
    try:
        import yt_dlp
    except ImportError:
        log.error("youtube: pacote yt-dlp ausente (pip install yt-dlp)")
        return []
    opcoes = {"quiet": True, "no_warnings": True, "skip_download": True}
    consulta = f"ytsearch{limite}:{termo}"
    try:
        info = yt_dlp.YoutubeDL(opcoes).extract_info(consulta, download=False)
    except Exception as exc:
        log.warning("youtube: busca '%s' falhou (%s)", termo, exc)
        return []
    artigos = []
    for entry in (info or {}).get("entries") or []:
        try:
            artigo = _montar_artigo(entry, termo, min_views, dias)
        except Exception as exc:
            log.warning("youtube: vídeo em '%s' quebrou no parse (%s)", termo, exc)
            artigo = None
        if artigo:
            artigos.append(artigo)
    for artigo in artigos:
        log.info("youtube: [%s] %s — canal %s, views %.0f, transcrição %d chars",
                 termo, artigo["titulo"][:55], artigo["canal"],
                 artigo.get("views") or 0,
                 len(artigo.get("texto_extraido") or ""))
    return artigos


def coletar_videos(radar, config):
    """Itera termos em alta do Radar e mescla vídeos (cap global; nunca levanta)."""
    if not radar:
        return []
    termos = [t.get("termo") for t in (radar.get("termos") or [])
              if t.get("status") == "alta" and t.get("termo")]
    if not termos:
        log.info("youtube: nenhum termo com status 'alta'; busca dinâmica pulada")
        return []
    cap = int((config.get("youtube_busca") or {}).get("max_videos_total", 8))
    vistos, saida = set(), []
    for termo in termos:
        if len(saida) >= cap:
            break
        for artigo in buscar_videos_por_termo(termo, config):
            chave = _id_do_video(artigo.get("url"))
            if chave in vistos:
                continue
            vistos.add(chave)
            saida.append(artigo)
            if len(saida) >= cap:
                break
        time.sleep(1.0)  # cortesia entre buscas de termo distintos
    log.info("youtube: %d vídeo(s) coletado(s) — termos em alta: %s; cap %d",
             len(saida), ", ".join(termos), cap)
    return saida[:cap]
