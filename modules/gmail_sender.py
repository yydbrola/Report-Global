# -*- coding: utf-8 -*-
"""Entrega do PDF no Gmail — rascunho por padrão, envio direto opcional.

simplegmail (OAuth Desktop): precisa de `client_secret.json` (tipo
"Aplicativo de computador") na raiz do projeto e cria `gmail_token.json`
no fluxo de autorização do navegador na 1ª execução. Desde então as
credenciais são recarregadas automaticamente.

⚠ App OAuth em status "Testing": o refresh token EXPIRA EM 7 DIAS.
   Solução oficial: publicar o app como "Production" no OAuth consent
   screen do Google Cloud Console (sem verificação adicional necessária
   para uso pessoal).
"""
import logging
import os

log = logging.getLogger("pipeline.gmail")


def _resolver_destino(config):
    email_conf = config.get("email") or {}
    destino = email_conf.get("destino") or os.environ.get("EMAIL_DESTINO", "")
    if not destino:
        raise RuntimeError(
            "E-MAIL DE DESTINO NÃO CONFIGURADO — defina config/email.destino "
            "ou a variável de ambiente EMAIL_DESTINO."
        )
    return destino


def _corpo(dados):
    tematicas = dados.get("tematicas") or []
    itens = []
    for tematic in tematicas:
        far = tematic.get("artigos") or []
        if far:
            itens.append(f"• {tematic.get('nome')}: {len(far)} artigo(s)")
    linhas = [
        dados.get("edicao", ""),
        "",
        f"Artigos analisados: {dados.get('artigos_analisados', '—')}",
        f"Modelo de classificação: {dados.get('modelo_ia', '—')}",
        f"Custo estimado: {dados.get('custo', '—')}",
        "",
        *(itens or ["(sem temáticas renderizadas)"]),
        "",
        "PDF completo em anexo. Análise sintetizada com IA — verifique as fontes originais.",
    ]
    return "\n".join(linhas)


def _corpo_html(dados):
    linhas_html = "".join(
        f"<li>{t.get('nome')} — {len(t.get('artigos') or [])} artigo(s)</li>"
        for t in (dados.get("tematicas") or [])
        if (t.get("artigos") or [])
    ) or "<li>(sem temáticas renderizadas)</li>"
    return (
        f"<p><strong>{dados.get('edicao', '')}</strong></p>"
        f"<p>Artigos analisados: <strong>{dados.get('artigos_analisados', '—')}</strong><br>"
        f"Modelo: <code>{dados.get('modelo_ia', '—')}</code> · "
        f"Custo: <code>{dados.get('custo', '—')}</code></p>"
        f"<ul>{linhas_html}</ul>"
        "<p><em>Análise sintetizada com IA — verifique as fontes originais.</em></p>"
    )


def entregar(config, caminho_pdf, dados, modo=None):
    """Cria rascunho (padrão) ou envia direto. Devolve o recurso criado."""
    from simplegmail import Gmail

    conf = config.get("email") or {}
    modo = (modo or conf.get("modo", "draft")).lower()
    destino = _resolver_destino(config)

    gmail = Gmail(
        client_secret_file=conf.get("client_secret", "client_secret.json"),
        creds_file=conf.get("arquivo_credenciais", "gmail_token.json"),
    )
    assunto = f"Relatório de Relações Internacionais – {dados.get('data', '')}"
    kwargs = dict(
        sender="me",
        to=destino,
        subject=assunto,
        msg_plain=_corpo(dados),
        msg_html=_corpo_html(dados),
        attachments=[str(caminho_pdf)],
    )
    if modo == "send":
        recurso = gmail.send_message(**kwargs)
        log.info("e-mail direto enviado para %s", destino)
    else:
        recurso = gmail.create_draft(**kwargs)
        log.info("rascunho criado para %s (id=%s)", destino,
                 (recurso or {}).get("id", "?"))
    return recurso
