# -*- coding: utf-8 -*-
"""Template editorial/jornalístico para Relatório Diário de Relações Internacionais.

Portado do modelo fornecido pelo usuário (design editorial Times/Helvetica,
masthead, caixa de panorama, KeepTogether por artigo). Mudanças em relação ao
original: sem DADOS de demonstração e sem execução em `__main__`; a seção
"Panorama Geral" só é renderizada quando há texto (editorial desativado →
PDF degrada limpo, apenas artigos).

Contrato de entrada (chaves dinner `gerar_relatorio(dados, caminho_saida)`):
    data, edicao, artigos_analisados, modelo_ia, custo, titulo_capa,
    subtitulo_capa, panorama_geral (lista de parágrafos), tematicas: [
        {nome, rotulo, destaque?, artigos: [
            {titulo, resumo?, fonte, data, confianca?, link}]}]
"""
from datetime import datetime
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)

# ---------------------------------------------------------------------
# IDENTIDADE VISUAL: jornal contemporâneo / briefing editorial
# ---------------------------------------------------------------------
INK = colors.HexColor('#191F26')          # quase preto editorial
NAVY = colors.HexColor('#1D3348')         # azul escuro para navegação
ACCENT = colors.HexColor('#B33A32')       # vermelho editorial discreto
PAPER = colors.HexColor('#FBFAF7')        # papel levemente quente
PALE = colors.HexColor('#F1EFE9')         # fundo de apoio
RULE = colors.HexColor('#D8D4CC')         # fios/divisórias
MUTED = colors.HexColor('#6D716F')        # metadados
WHITE = colors.white


def esc(txt):
    """Escapa texto de dados para inclusão em Paragraph/markup XML."""
    return escape(str(txt if txt is not None else '')).replace('\n', '<br/>')


def estilos():
    # Dupla tipográfica editorial: Times para manchetes; Helvetica para serviço.
    return {
        'masthead': ParagraphStyle('Masthead', fontName='Helvetica-Bold', fontSize=10,
            leading=12, textColor=INK, alignment=TA_CENTER, tracking=2),
        'edition': ParagraphStyle('Edition', fontName='Helvetica', fontSize=7.5,
            leading=10, textColor=MUTED, alignment=TA_CENTER),
        'cover_kicker': ParagraphStyle('CoverKicker', fontName='Helvetica-Bold',
            fontSize=8.5, leading=11, textColor=ACCENT, alignment=TA_CENTER, tracking=1.5),
        'cover_title': ParagraphStyle('CoverTitle', fontName='Times-Bold', fontSize=38,
            leading=39, textColor=INK, alignment=TA_CENTER, spaceAfter=10),
        'cover_subtitle': ParagraphStyle('CoverSubtitle', fontName='Times-Roman',
            fontSize=15, leading=20, textColor=NAVY, alignment=TA_CENTER),
        'section_kicker': ParagraphStyle('SectionKicker', fontName='Helvetica-Bold',
            fontSize=7.5, leading=9, textColor=ACCENT, tracking=1.1, spaceAfter=5),
        'section': ParagraphStyle('Section', fontName='Times-Bold', fontSize=25,
            leading=28, textColor=INK, spaceAfter=7),
        'theme': ParagraphStyle('Theme', fontName='Times-Bold', fontSize=21,
            leading=24, textColor=INK, spaceAfter=5),
        'theme_deck': ParagraphStyle('ThemeDeck', fontName='Times-Italic', fontSize=11,
            leading=15, textColor=NAVY, spaceAfter=10),
        'body': ParagraphStyle('Body', fontName='Times-Roman', fontSize=11,
            leading=16, textColor=INK, spaceAfter=8, alignment=TA_LEFT),
        'panel_label': ParagraphStyle('PanelLabel', fontName='Helvetica-Bold',
            fontSize=7.5, leading=9, textColor=ACCENT, tracking=1.0, spaceAfter=5),
        'panel_body': ParagraphStyle('PanelBody', fontName='Times-Roman',
            fontSize=10.5, leading=15, textColor=INK, spaceAfter=5),
        'article_kicker': ParagraphStyle('ArticleKicker', fontName='Helvetica-Bold',
            fontSize=7, leading=9, textColor=ACCENT, tracking=.7, spaceAfter=3),
        'article_title': ParagraphStyle('ArticleTitle', fontName='Times-Bold',
            fontSize=13, leading=16, textColor=INK, spaceAfter=4),
        'summary': ParagraphStyle('Summary', fontName='Times-Roman', fontSize=9.5,
            leading=13, textColor=INK, spaceAfter=5),
        'meta': ParagraphStyle('Meta', fontName='Helvetica', fontSize=7.2,
            leading=9.5, textColor=MUTED, spaceAfter=4),
        'link': ParagraphStyle('Link', fontName='Helvetica-Bold', fontSize=7.5,
            leading=10, textColor=NAVY, wordWrap='CJK'),
        'cover_meta_label': ParagraphStyle('CoverMetaLabel', fontName='Helvetica-Bold',
            fontSize=6.7, leading=8, textColor=MUTED, alignment=TA_CENTER, tracking=.4),
        'cover_meta_value': ParagraphStyle('CoverMetaValue', fontName='Helvetica-Bold',
            fontSize=10, leading=12, textColor=INK, alignment=TA_CENTER),
        'disclaimer': ParagraphStyle('Disclaimer', fontName='Helvetica', fontSize=7.2,
            leading=10, textColor=MUTED, alignment=TA_CENTER),
    }


def metadata_capa(dados, st):
    fields = [
        ('DATA', dados.get('data', '—')),
        ('ARTIGOS ANALISADOS', str(dados.get('artigos_analisados', '—'))),
        ('MODELO DE IA', dados.get('modelo_ia', '—')),
        ('CUSTO ESTIMADO', dados.get('custo', '—')),
    ]
    row = []
    for label, value in fields:
        row.append([
            Paragraph(esc(label), st['cover_meta_label']),
            Spacer(1, 3),
            Paragraph(esc(value), st['cover_meta_value'])
        ])
    t = Table([row], colWidths=[43.5*mm]*4, hAlign='CENTER')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), PALE),
        ('BOX', (0,0), (-1,-1), .6, RULE),
        ('INNERGRID', (0,0), (-1,-1), .5, RULE),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 9),
    ]))
    return t


def panorama_box(paragrafos, st):
    content = [Paragraph('O QUE IMPORTA HOJE', st['panel_label'])]
    for p in paragrafos:
        content.append(Paragraph(esc(p), st['panel_body']))
    t = Table([[content]], colWidths=[174*mm], hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), PALE),
        ('LINEBEFORE', (0,0), (0,0), 3, ACCENT),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    return t


def barra_indice(indice, largura_mm=34):
    """Barra 0-100 do interesse de busca, com o valor impresso ao lado."""
    from reportlab.graphics.shapes import Drawing, Rect, String
    largura = largura_mm * mm
    altura = 4.2 * mm
    d = Drawing(largura + 9*mm, altura)
    d.add(Rect(0, 0, largura, altura,
               fillColor=colors.HexColor('#EDEAE3'), strokeColor=None))
    fill = ACCENT if indice >= 70 else (NAVY if indice >= 35 else MUTED)
    d.add(Rect(0, 0, largura * max(0.0, min(100.0, indice)) / 100.0, altura,
               fillColor=fill, strokeColor=None))
    d.add(String(largura + 1.2*mm, altura - 3.4*mm, f"{int(round(indice))}",
                 fontName='Helvetica-Bold', fontSize=7, fillColor=NAVY))
    return d


def radar_tendencias_flowables(radar, st):
    """Seção 'Radar de tendências': índice de interesse + variação qualificada.

    Recebe o contrato de main.py (dados['radar_tendencias']): texto_analise,
    termos [{termo, indice_atual, variacao, periodo, status}], top_trends.
    Sem dados/termos → retorna [] (a seção não existe no PDF).
    """
    termos = ((radar or {}).get('termos') or [])
    if not termos:
        return []
    st_termo = ParagraphStyle('RadarTermo', fontName='Times-Bold', fontSize=11.5,
                              leading=14, textColor=INK)
    st_var = ParagraphStyle('RadarVariacao', fontName='Helvetica-Bold', fontSize=8.2,
                            leading=11, textColor=INK)
    useca = [Paragraph('LEITURA DO PÚBLICO', st['section_kicker']),
             Paragraph('Radar de tendências', st['section']),
             Paragraph('Interesse de busca no YouTube (escala 0-100). Variação em '
                       'coral indica alta; em cinza, queda ou estabilidade.',
                       st['theme_deck']),
             HRFlowable(width='100%', thickness=1.1, color=INK,
                        spaceBefore=0, spaceAfter=10)]
    linhas = [[Paragraph('TERMO', st['cover_meta_label']),
               Paragraph('INTERESSE (0-100)', st['cover_meta_label']),
               Paragraph('VARIAÇÃO', st['cover_meta_label']),
               Paragraph('JANELA', st['cover_meta_label'])]]
    for item in termos:
        status = str(item.get('status') or '').lower()
        alta = status == 'alta' or (not status and '+' in str(item.get('variacao', '')))
        cor = '#B33A32' if alta else '#6D716F'
        variacao = item.get('variacao', '—')
        linhas.append([
            Paragraph(esc(item.get('termo', '—')), st_termo),
            barra_indice(item.get('indice_atual') or 0),
            Paragraph(f'<font color="{cor}"><b>{esc(variacao)}</b></font>', st_var),
            Paragraph(esc(item.get('periodo', '—')), st['meta']),
        ])
    tabela = Table(linhas, colWidths=[46*mm, 50*mm, 34*mm, 44*mm], hAlign='LEFT')
    tabela.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,0), 1.0, INK),
        ('LINEBELOW', (0,-1), (-1,-1), .9, INK),
        ('LINEBELOW', (0,0), (-1,-2), .45, RULE),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (0,-1), 0),
    ]))
    seguido = useca + [tabela]
    if (radar or {}).get('texto_analise'):
        caixa = Table([[[
            Paragraph('O QUE O RADAR DIZ', st['panel_label']),
            Paragraph(esc(radar['texto_analise']), st['panel_body'])]]],
            colWidths=[174*mm], hAlign='LEFT')
        caixa.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), PALE),
            ('LINEBEFORE', (0,0), (0,0), 3, ACCENT),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
            ('TOPPADDING', (0,0), (-1,-1), 9),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        seguido += [Spacer(1, 5*mm), caixa]
    seguido.append(Spacer(1, 9*mm))
    return [KeepTogether(seguido)]


def artigo_flowable(artigo, rotulo, st):
    titulo = Paragraph(esc(artigo.get('titulo', 'Sem título')), st['article_title'])
    resumo = Paragraph(esc(artigo.get('resumo', 'Resumo não disponível.')), st['summary'])
    metadados = [
        f"<b>FONTE</b>  {esc(artigo.get('fonte', 'Não informada'))}",
        f"<b>DATA</b>  {esc(artigo.get('data', 'Não informada'))}",
    ]
    if artigo.get('confianca') is not None:
        metadados.append(f"<b>CONFIANÇA IA</b>  {esc(artigo['confianca'])}%")
    meta = Paragraph(' &nbsp;&nbsp; / &nbsp;&nbsp; '.join(metadados), st['meta'])

    url = str(artigo.get('link', '') or '').strip()
    if url.startswith(('https://', 'http://')):
        domain = urlparse(url).netloc or url
        safe_url = escape(url, {'"': '&quot;'})
        # Link fica clicável em "LER MATÉRIA" e o domínio aparece ao lado.
        link = Paragraph(
            f'<link href="{safe_url}" color="#1D3348"><u>LER MATÉRIA</u></link>'
            f'&nbsp;&nbsp;<font color="#6D716F">{esc(domain)}</font>', st['link'])
    else:
        link = Paragraph('LINK NÃO DISPONÍVEL', st['meta'])

    # Linha editorial: filete vertical e conteúdo, sem cartões arredondados.
    inner = [Paragraph(esc(rotulo.upper()), st['article_kicker']), titulo, resumo, meta, link]
    t = Table([['', inner]], colWidths=[3*mm, 171*mm], hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), ACCENT),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (0,0), 0),
        ('RIGHTPADDING', (0,0), (0,0), 0),
        ('LEFTPADDING', (1,0), (1,0), 9),
        ('RIGHTPADDING', (1,0), (1,0), 0),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
    ]))
    return t


def bloco_tematica(tematica, st):
    nome = tematica.get('nome', 'Temática')
    rotulo = tematica.get('rotulo', nome).upper()
    cabecalho = [
        Paragraph(esc(rotulo), st['section_kicker']),
        Paragraph(esc(nome), st['theme']),
    ]
    if tematica.get('destaque'):
        cabecalho.append(Paragraph(esc(tematica['destaque']), st['theme_deck']))
    cabecalho.append(HRFlowable(width='100%', thickness=1.1, color=INK,
                                spaceBefore=0, spaceAfter=11))

    artigos = list(tematica.get('artigos', []))
    flow = []
    if artigos:
        # Agrupa cabeçalho + primeira matéria numa única unidade, evitando
        # cabeçalhos de temática órfãos. Os artigos seguintes também não quebram.
        primeira = artigo_flowable(artigos[0], rotulo, st)
        flow.append(KeepTogether(cabecalho + [primeira, Spacer(1, 11),
            HRFlowable(width='100%', thickness=.45, color=RULE,
                       spaceBefore=0, spaceAfter=11)]))
        for artigo in artigos[1:]:
            flow.append(KeepTogether([artigo_flowable(artigo, rotulo, st),
                Spacer(1, 11), HRFlowable(width='100%', thickness=.45, color=RULE,
                                         spaceBefore=0, spaceAfter=11)]))
    else:
        flow.append(KeepTogether(cabecalho))
    flow.append(Spacer(1, 5))
    return flow


def header_footer(canvas, doc, data_referencia):
    canvas.saveState()
    w, h = A4
    if doc.page > 1:
        # Linha de cabeçalho e assinatura editorial
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(.55)
        canvas.line(18*mm, h-14*mm, w-18*mm, h-14*mm)
        canvas.setFillColor(INK)
        canvas.setFont('Helvetica-Bold', 7.3)
        canvas.drawString(18*mm, h-10.5*mm, 'RELATÓRIO DE RELAÇÕES INTERNACIONAIS')
        canvas.setFillColor(ACCENT)
        canvas.setFont('Helvetica-Bold', 7.3)
        canvas.drawRightString(w-18*mm, h-10.5*mm, 'BRIEFING DIÁRIO')
        # Rodapé
        canvas.setStrokeColor(RULE)
        canvas.line(18*mm, 13*mm, w-18*mm, 13*mm)
        canvas.setFillColor(MUTED)
        canvas.setFont('Helvetica', 7.2)
        canvas.drawString(18*mm, 8.5*mm, f'EDIÇÃO DE {data_referencia}')
        canvas.drawRightString(w-18*mm, 8.5*mm, f'{doc.page:02d}')
    canvas.restoreState()


def gerar_relatorio(dados, caminho_saida='relatorio_relacoes_internacionais_jornalistico.pdf'):
    st = estilos()
    doc = SimpleDocTemplate(
        caminho_saida, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=21*mm, bottomMargin=19*mm,
        title='Relatório de Relações Internacionais | Briefing Diário',
        author='Equipe de Inteligência',
        subject='Briefing editorial de relações internacionais'
    )
    story = []

    # CAPA / MASTHEAD
    story += [Spacer(1, 13*mm),
        Paragraph('OBSERVATÓRIO', st['masthead']),
        Paragraph('POLÍTICA INTERNACIONAL  •  INTELIGÊNCIA  •  CONTEXTO', st['edition']),
        Spacer(1, 3*mm),
        HRFlowable(width='100%', thickness=1.2, color=INK, spaceBefore=0, spaceAfter=2),
        HRFlowable(width='100%', thickness=.45, color=INK, spaceBefore=0, spaceAfter=7*mm),
        Paragraph(esc(dados.get('edicao', 'BRIEFING DIÁRIO')).upper(), st['cover_kicker']),
        Spacer(1, 5*mm),
        Paragraph(esc(dados.get('titulo_capa', 'O MUNDO EM MOVIMENTO')), st['cover_title']),
        HRFlowable(width='19%', thickness=3, color=ACCENT, hAlign='CENTER',
                   spaceBefore=3*mm, spaceAfter=7*mm),
        Paragraph(esc(dados.get('subtitulo_capa', 'Análise diária da agenda internacional.')),
                  st['cover_subtitle']),
        Spacer(1, 14*mm), metadata_capa(dados, st), Spacer(1, 5*mm),
        Paragraph('ANÁLISE SINTETIZADA COM APOIO DE IA • VERIFIQUE AS FONTES ORIGINAIS',
                  st['disclaimer']), Spacer(1, 15*mm)]

    # Teaser na capa: nomes das seções, funciona como índice simples
    story.append(HRFlowable(width='100%', thickness=.6, color=RULE,
                            spaceBefore=0, spaceAfter=4*mm))
    story.append(Paragraph('NA EDIÇÃO DE HOJE', st['section_kicker']))
    teasers = []
    for tematica in dados.get('tematicas', []):
        teasers.append(Paragraph(
            f'<font color="#B33A32"><b>•</b></font>&nbsp;&nbsp;{esc(tematica.get("nome", "Temática"))}',
            ParagraphStyle('Teaser', fontName='Times-Roman', fontSize=11,
                           leading=15, textColor=INK)))
    teaser_table = Table([[teasers]], colWidths=[174*mm], hAlign='LEFT')
    teaser_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), PAPER),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.extend([teaser_table, PageBreak()])

    # RADAR DE TENDÊNCIAS — logo após a capa; só existe quando há dados
    story.extend(radar_tendencias_flowables(dados.get('radar_tendencias'), st))

    # PANORAMA GERAL (só com editorial ativo e texto)
    if dados.get('panorama_geral'):
        story.extend([
            Paragraph('LEITURA DO DIA', st['section_kicker']),
            Paragraph('Panorama geral', st['section']),
            Paragraph('Os principais movimentos, suas conexões e o que merece acompanhamento.', st['theme_deck']),
            HRFlowable(width='100%', thickness=1.1, color=INK, spaceBefore=0, spaceAfter=10),
            panorama_box(dados.get('panorama_geral', []), st),
            Spacer(1, 9*mm),
            Paragraph('TEMAS EM FOCO', st['section_kicker']),
        ])
    else:
        story.append(Paragraph('TEMAS EM FOCO', st['section_kicker']))

    # Temáticas fluem de forma contínua; sem page break forçado a cada seção.
    for i, tematica in enumerate(dados.get('tematicas', [])):
        if i > 0:
            story.append(Spacer(1, 3*mm))
        story.extend(bloco_tematica(tematica, st))

    draw = lambda canvas, doc: header_footer(canvas, doc, dados.get('data', ''))
    doc.build(story, onFirstPage=draw, onLaterPages=draw)
    return caminho_saida
