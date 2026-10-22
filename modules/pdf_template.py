# -*- coding: utf-8 -*-
"""Template editorial de jornal para Briefing Diário de Relações Internacionais.

Dependência: pip install reportlab
Execução: python pdf_template.py

Ajuste o dicionário DADOS ou passe seu objeto de dados para gerar_relatorio().
Usa BaseDocTemplate + Frame para capa/radar em coluna única e miolo em duas colunas.
"""

import os
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
    TableStyle, PageBreak, NextPageTemplate, KeepTogether, HRFlowable,
    Flowable, Image
)
from reportlab.graphics.shapes import Drawing, String, Rect
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import HorizontalBarChart

# ---------------------------------------------------------------------
# IDENTIDADE VISUAL — jornal impresso clássico
# ---------------------------------------------------------------------
INK = colors.HexColor("#191F26")
NAVY = colors.HexColor("#1D3348")
ACCENT = colors.HexColor("#B33A32")
PAPER = colors.HexColor("#FBFAF7")
PALE = colors.HexColor("#F1EFE9")
RULE = colors.HexColor("#D8D4CC")
MUTED = colors.HexColor("#64748B")
WHITE = colors.white

# Cores Semânticas
CORES_SEMANTICAS = {
    "CONFLITOS": colors.HexColor("#B33A32"),
    "ECONOMIA": colors.HexColor("#2E5B3A"),
    "DIPLOMACIA": colors.HexColor("#1D3348"),
    "TECNOLOGIA": colors.HexColor("#5A3A8C"),
}

PAGE_W, PAGE_H = A4
MARGIN_X = 17.5 * mm
MARGIN_TOP = 21 * mm
MARGIN_BOTTOM = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X
COLUMN_GAP = 6.5 * mm
COLUMN_W = (CONTENT_W - COLUMN_GAP) / 2


# ---------------------------------------------------------------------
# DADOS DE DEMONSTRAÇÃO — Atualizado com auditoria, thumbnail e novos temas
# ---------------------------------------------------------------------
DADOS = {
    "data": "22/10/2026",
    "edicao": "EDIÇÃO 001",
    "modelo_ia": "GPT-6",
    "artigos_analisados": 42,
    "titulo_capa": "O MUNDO EM\nMOVIMENTO",
    "subtitulo_capa": "Sinais diplomáticos, riscos estratégicos e os temas que moldam a agenda internacional.",
    "auditoria": {
        "fontes_lidas": "1.432 fontes (agências, feeds governamentais, redes)",
        "total_artigos": 42,
        "custo_estimado": "$ 0,45 (tokens API)",
        "modelos_ia": "GPT-4o (Síntese) e Claude 3.5 Sonnet (Revisão)",
        "nota_metodologica": "As classificações de tom e confiança são atribuídas por modelos probabilísticos automatizados e não substituem o julgamento analítico humano."
    },
    "dados_tendencias": {
        "texto_analise": (
            "Sanções combina índice de interesse elevado com crescimento expressivo, enquanto "
            "Geopolítica mantém relevância alta no período. A variação de cada termo deve ser "
            "interpretada junto ao índice atual e à janela de comparação, não isoladamente."
        ),
        "termos": [
            {"termo": "Geopolítica", "indice_atual": 85, "variacao": "+45%", "periodo": "vs. 7 dias", "status": "alta"},
            {"termo": "Sanções", "indice_atual": 92, "variacao": "+120%", "periodo": "vs. 30 dias", "status": "alta"},
            {"termo": "Eleições", "indice_atual": 15, "variacao": "-10%", "periodo": "vs. 7 dias", "status": "queda"},
        ],
    },
    "panorama_geral": [
        "A agenda internacional do período foi marcada por movimentações diplomáticas e pela continuidade de tensões regionais. Os governos envolvidos buscaram preservar canais de negociação, enquanto divergências estratégicas limitaram avanços concretos.",
        "No campo econômico, decisões regulatórias e sinais dos principais atores continuam relevantes para os fluxos comerciais e para a percepção de risco. Os próximos desdobramentos dependerão da implementação das medidas anunciadas e da resposta dos parceiros internacionais.",
    ],
    "analise_narrativas": (
        "Vídeos de comentário político ampliaram a circulação de interpretações sobre a crise, "
        "com forte ênfase em cenários de escalada. A leitura deve separar fatos verificáveis, "
        "opiniões dos apresentadores e hipóteses ainda sem confirmação independente."
    ),
    "tematicas": [
        {
            "nome": "Conflitos e segurança",
            "rotulo": "CONFLITOS",
            "destaque": "A dinâmica de segurança permanece entre os fatores de maior impacto para a estabilidade regional.",
            "artigos": [
                {
                    "titulo": "Tensões regionais mantêm governos em alerta máximo",
                    "resumo": "Autoridades discutiram novas medidas de segurança e avaliaram seus possíveis impactos regionais. Analistas destacam que a implementação prática será determinante para os próximos passos.",
                    "fonte": "Agência Internacional", "data": "22/10/2026", "confianca": 97,
                    "link": "https://example.com/noticia-seguranca", "tipo_fonte": "web", "tom": "analítico",
                },
                {
                    "titulo": "Comentaristas divergem sobre os próximos passos da crise",
                    "resumo": "Um vídeo de análise reuniu interpretações sobre o cenário e seus possíveis desdobramentos. Parte das conclusões é opinativa e deve ser confrontada com comunicados oficiais e cobertura independente.",
                    "fonte": "Canal de análise internacional", "data": "22/10/2026", "confianca": 88,
                    "link": "https://www.youtube.com/watch?v=example", "tipo_fonte": "youtube",
                    "thumbnail_path": "miniatura_mock.jpg", # Path simulado para ativar a feature visual
                    "views": "128 mil", "engajamento": "6,4%", "tom": "alarmista",
                    "pull_quote": "Parte das conclusões é opinativa e deve ser confrontada com fontes independentes.",
                },
            ],
        },
        {
            "nome": "Diplomacia e relações bilaterais",
            "rotulo": "DIPLOMACIA",
            "destaque": "Os contatos diplomáticos sinalizam disposição para o diálogo, embora persistam divergências sobre os termos de um eventual acordo.",
            "artigos": [
                {
                    "titulo": "Representantes retomam conversas sobre agenda bilateral",
                    "resumo": "As delegações discutiram prioridades e possíveis mecanismos de cooperação. Não houve confirmação de um acordo definitivo até o fechamento deste briefing diário.",
                    "fonte": "Portal de Notícias", "data": "22/10/2026", "confianca": 91,
                    "link": "https://example.com/agenda-bilateral", "tipo_fonte": "web", "tom": "neutro",
                },
            ],
        },
        {
            "nome": "Economia global",
            "rotulo": "ECONOMIA",
            "destaque": "Decisões regulatórias e sinais de política comercial seguem no radar de empresas e governos.",
            "artigos": [
                {
                    "titulo": "Mercados observam novos sinais sobre política comercial",
                    "resumo": "Investidores e formuladores de política acompanham possíveis mudanças nas regras de comércio. O impacto dependerá do alcance das medidas e da reação dos principais parceiros.",
                    "fonte": "Observatório Econômico", "data": "22/10/2026", "confianca": 89,
                    "link": "https://example.com/politica-comercial", "tipo_fonte": "web", "tom": "cauteloso",
                },
            ],
        },
        {
            "nome": "Avanços Tecnológicos",
            "rotulo": "TECNOLOGIA",
            "destaque": "Regulação da IA domina os debates parlamentares globais.",
            "artigos": [
                {
                    "titulo": "Novo marco regulatório para inteligência artificial artificial entra em pauta",
                    "resumo": "O parlamento europeu abriu espaço para novas emendas na lei que governa a aplicação de modelos gerativos nos setores públicos e privados.",
                    "fonte": "Tech Insight", "data": "22/10/2026", "confianca": 93,
                    "link": "https://example.com/tech", "tipo_fonte": "web", "tom": "analítico",
                },
            ],
        }
    ],
}


# ---------------------------------------------------------------------
# HELPERS E ESTILOS
# ---------------------------------------------------------------------
def esc(texto):
    """Escapa dados externos para uso seguro em Paragraph (markup XML)."""
    if texto is None:
        return ""
    return escape(str(texto)).replace("\n", "<br/>")


def fmt_views(valor):
    """46210 -> '46k'; 1200000 -> '1,2M'; strings passam intactas."""
    if isinstance(valor, (int, float)) and valor >= 1000:
        if valor >= 1_000_000:
            return f"{valor / 1_000_000:.1f}".replace(".", ",") + "M"
        return f"{valor / 1_000:.0f}k"
    return str(valor if valor is not None else "n/d")


def estilos():
    """Estilos de uma publicação impressa: serifas no editorial, sans nos serviços."""
    return {
        "masthead": ParagraphStyle(
            "Masthead", fontName="Times-Bold", fontSize=26, leading=29,
            textColor=INK, alignment=TA_CENTER, spaceAfter=2,
        ),
        "masthead_deck": ParagraphStyle(
            "MastheadDeck", fontName="Helvetica-Bold", fontSize=7.2, leading=9,
            textColor=NAVY, alignment=TA_CENTER, spaceAfter=3, tracking=1.1,
        ),
        "cover_kicker": ParagraphStyle(
            "CoverKicker", fontName="Helvetica-Bold", fontSize=8, leading=10,
            textColor=ACCENT, alignment=TA_CENTER, spaceAfter=4, tracking=1.0,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle", fontName="Times-Bold", fontSize=43, leading=44,
            textColor=INK, alignment=TA_CENTER, spaceAfter=7,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle", fontName="Times-Roman", fontSize=14, leading=18,
            textColor=NAVY, alignment=TA_CENTER, leftIndent=12*mm, rightIndent=12*mm,
        ),
        "cover_meta": ParagraphStyle(
            "CoverMeta", fontName="Helvetica", fontSize=8, leading=11,
            textColor=INK, alignment=TA_CENTER,
        ),
        "cover_teaser_head": ParagraphStyle(
            "CoverTeaserHead", fontName="Helvetica-Bold", fontSize=7.5, leading=9,
            textColor=ACCENT, tracking=1.0, spaceAfter=4,
        ),
        "cover_teaser": ParagraphStyle(
            "CoverTeaser", fontName="Times-Bold", fontSize=10, leading=13,
            textColor=INK,
        ),
        "disclaimer": ParagraphStyle(
            "Disclaimer", fontName="Helvetica", fontSize=6.8, leading=9,
            textColor=MUTED, alignment=TA_CENTER,
        ),
        "section_kicker": ParagraphStyle(
            "SectionKicker", fontName="Helvetica-Bold", fontSize=7.2, leading=9,
            textColor=ACCENT, tracking=1.0, spaceAfter=3,
        ),
        "section": ParagraphStyle(
            "Section", fontName="Times-Bold", fontSize=24, leading=27,
            textColor=INK, spaceAfter=4,
        ),
        "section_deck": ParagraphStyle(
            "SectionDeck", fontName="Times-Italic", fontSize=10.5, leading=14,
            textColor=NAVY, spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "Body", fontName="Times-Roman", fontSize=10.2, leading=14,
            textColor=INK, spaceAfter=7, alignment=TA_JUSTIFY, # Justificado
        ),
        "dropcap_letter": ParagraphStyle(
            "DropCapLetter", fontName="Times-Bold", fontSize=38, leading=38,
            textColor=ACCENT, alignment=TA_CENTER,
        ),
        "body_after_dropcap": ParagraphStyle(
            "BodyAfterDropCap", fontName="Times-Roman", fontSize=10.2,
            leading=14, textColor=INK, spaceAfter=7, alignment=TA_JUSTIFY,
        ),
        "panel_label": ParagraphStyle(
            "PanelLabel", fontName="Helvetica-Bold", fontSize=7, leading=9,
            textColor=ACCENT, tracking=.7, spaceAfter=3,
        ),
        "theme_kicker": ParagraphStyle(
            "ThemeKicker", fontName="Helvetica-Bold", fontSize=7.2, leading=9,
            textColor=ACCENT, tracking=.8, spaceAfter=2,
        ),
        "theme": ParagraphStyle(
            "Theme", fontName="Times-Bold", fontSize=18, leading=20,
            textColor=INK, spaceAfter=4,
        ),
        "theme_deck": ParagraphStyle(
            "ThemeDeck", fontName="Times-Italic", fontSize=9.5, leading=12.5,
            textColor=NAVY, spaceAfter=5,
        ),
        "article_kicker": ParagraphStyle(
            "ArticleKicker", fontName="Helvetica-Bold", fontSize=6.7, leading=8.5,
            textColor=ACCENT, tracking=.5, spaceAfter=2,
        ),
        "hero_title": ParagraphStyle(
            "HeroTitle", fontName="Times-Bold", fontSize=16, leading=19,
            textColor=INK, spaceAfter=3,
        ),
        "article_title": ParagraphStyle(
            "ArticleTitle", fontName="Times-Bold", fontSize=12.5, leading=14.5,
            textColor=INK, spaceAfter=3,
        ),
        "summary": ParagraphStyle(
            "Summary", fontName="Times-Roman", fontSize=9.2, leading=12.2,
            textColor=INK, spaceAfter=4, alignment=TA_JUSTIFY, # Justificado
        ),
        "meta": ParagraphStyle(
            "Meta", fontName="Helvetica", fontSize=6.7, leading=8.5,
            textColor=MUTED, spaceAfter=3,
        ),
        "tom_chip": ParagraphStyle(
            "TomChip", fontName="Helvetica", fontSize=6.7, leading=9,
            textColor=NAVY, spaceAfter=3,
        ),
        "link": ParagraphStyle(
            "Link", fontName="Helvetica-Bold", fontSize=6.9, leading=9,
            textColor=NAVY, wordWrap="CJK",
        ),
        "youtube_band": ParagraphStyle(
            "YouTubeBand", fontName="Helvetica-Bold", fontSize=6.0, leading=8,
            textColor=WHITE, spaceAfter=0,
        ),
        "pull_quote": ParagraphStyle(
            "PullQuote", fontName="Times-Italic", fontSize=11.5, leading=14.5,
            textColor=NAVY, alignment=TA_CENTER, leftIndent=5, rightIndent=5,
        ),
        "trend_term": ParagraphStyle(
            "TrendTerm", fontName="Times-Bold", fontSize=13, leading=15,
            textColor=INK, spaceAfter=2,
        ),
        "trend_status": ParagraphStyle(
            "TrendStatus", fontName="Helvetica-Bold", fontSize=6.2, leading=8,
            textColor=ACCENT, tracking=.3,
        ),
        "trend_label": ParagraphStyle(
            "TrendLabel", fontName="Helvetica-Bold", fontSize=6.3, leading=8,
            textColor=MUTED, tracking=.25, spaceAfter=2,
        ),
        "trend_index": ParagraphStyle(
            "TrendIndex", fontName="Times-Bold", fontSize=14, leading=16,
            textColor=NAVY,
        ),
        "trend_variation": ParagraphStyle(
            "TrendVariation", fontName="Times-Bold", fontSize=14, leading=16,
            textColor=ACCENT, spaceAfter=1,
        ),
        "trend_period": ParagraphStyle(
            "TrendPeriod", fontName="Helvetica", fontSize=6.8, leading=9,
            textColor=MUTED,
        ),
        "trend_analysis": ParagraphStyle(
            "TrendAnalysis", fontName="Times-Roman", fontSize=10, leading=14,
            textColor=INK, spaceAfter=3,
        ),
        "trend_note": ParagraphStyle(
            "TrendNote", fontName="Helvetica", fontSize=6.7, leading=9,
            textColor=MUTED,
        ),
        "trend_head": ParagraphStyle(
            "TrendHead", fontName="Helvetica-Bold", fontSize=6.2, leading=8,
            textColor=MUTED, tracking=.25,
        ),
        "dashboard_label": ParagraphStyle(
            "DashboardLabel", fontName="Helvetica-Bold", fontSize=7.2, leading=9,
            textColor=NAVY, tracking=.4, spaceAfter=2,
        ),
        "audit_head": ParagraphStyle(
            "AuditHead", fontName="Helvetica-Bold", fontSize=6.6, leading=9,
            textColor=MUTED, tracking=.3,
        ),
        "audit_value": ParagraphStyle(
            "AuditValue", fontName="Times-Roman", fontSize=9.6, leading=12.5,
            textColor=INK,
        ),
    }


class DropCapBlock(Flowable):
    """Bloco de parágrafo com capitular de três a quatro linhas de altura."""
    def __init__(self, texto, st, cap_width=12*mm):
        super().__init__()
        texto = str(texto or "")
        if texto:
            self.letra = texto[0]
            self.restante = texto[1:].lstrip()
        else:
            self.letra, self.restante = "", ""
        self.st = st
        self.cap_width = cap_width
        self._table = None

    def wrap(self, availWidth, availHeight):
        cap_w = min(self.cap_width, availWidth * .22)
        self._table = Table(
            [[Paragraph(esc(self.letra), self.st["dropcap_letter"]),
              Paragraph(esc(self.restante), self.st["body_after_dropcap"])]],
            colWidths=[cap_w, max(1, availWidth-cap_w)], hAlign="LEFT",
        )
        self._table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        self.width, self.height = self._table.wrap(availWidth, availHeight)
        return self.width, self.height

    def draw(self):
        if self._table:
            self._table.drawOn(self.canv, 0, 0)


class PullQuote(Flowable):
    """Citação destacada por duas linhas finas."""
    def __init__(self, texto, st, pad=6):
        super().__init__()
        self.texto = texto
        self.st = st
        self.pad = pad
        self.paragraph = Paragraph(esc(texto), st["pull_quote"])
        self.paragraph_height = 0

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        _, self.paragraph_height = self.paragraph.wrap(max(1, availWidth-10), availHeight)
        self.height = self.paragraph_height + self.pad*2 + 4
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setStrokeColor(ACCENT)
        c.setLineWidth(.8)
        c.line(0, self.height-1, self.width, self.height-1)
        c.line(0, 1, self.width, 1)
        self.paragraph.drawOn(c, 5, self.pad+2)


class BarraInteresse(Flowable):
    """Barra para o índice relativo do Google Trends, limitado à escala 0-100."""
    def __init__(self, valor, status="estável", width=54*mm, height=3.2*mm):
        super().__init__()
        try:
            self.valor = max(0.0, min(100.0, float(valor)))
        except (TypeError, ValueError):
            self.valor = 0.0
        self.status = str(status or "estável").lower()
        self.width = width
        self.height = height

    def wrap(self, availWidth, availHeight):
        self.width = min(self.width, availWidth)
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(PALE)
        c.rect(0, 0, self.width, self.height, stroke=0, fill=1)
        cor = ACCENT if any(x in self.status for x in ("alta", "subida")) else NAVY if any(x in self.status for x in ("queda", "declínio", "declinio", "baixa")) else MUTED
        preenchido = self.width * self.valor / 100.0
        if preenchido > 0:
            c.setFillColor(cor)
            c.rect(0, 0, preenchido, self.height, stroke=0, fill=1)


class Sparkline(Flowable):
    """Mini-gráfico de linha da série semanal do termo (últimos N pontos).

    Fallback: sem série, o Radar usa BarraInteresse. Marca o pico com um
    ponto cheio e escreve o máximo (0-100) à direita da linha.
    """
    def __init__(self, pontos, cor=NAVY, width=54*mm, height=9*mm):
        super().__init__()
        self.valores = []
        for p in (pontos or []):
            try:
                self.valores.append(max(0.0, min(100.0, float(p.get("value")))))
            except (TypeError, ValueError, AttributeError):
                continue
        self.cor = cor
        self.width = width
        self.height = height

    def wrap(self, availWidth, availHeight):
        self.width = min(self.width, availWidth)
        return self.width, self.height

    def draw(self):
        c = self.canv
        if len(self.valores) < 2:
            return
        w, h = self.width, self.height
        m = 3  # margem interna
        passo = (w - 2 * m) / (len(self.valores) - 1)
        maximo = max(self.valores)
        indice_pico = self.valores.index(maximo)
        coords = [
            (m + i * passo, m + (h - 2 * m) * v / 100.0)
            for i, v in enumerate(self.valores)
        ]
        # trilho
        c.setFillColor(PALE)
        c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setStrokeColor(self.cor)
        c.setLineWidth(1.1)
        c.setLineJoin(1)
        caminho = c.beginPath()
        caminho.moveTo(*coords[0])
        for x, y in coords[1:]:
            caminho.lineTo(x, y)
        c.drawPath(caminho, stroke=1, fill=0)
        # ponto do pico
        px, py = coords[indice_pico]
        c.setFillColor(ACCENT)
        c.circle(px, py, 1.6, stroke=0, fill=1)
        # rótulo do pico (suficiente para leitura no papel)
        c.setFont("Helvetica-Bold", 5.2)
        c.setFillColor(ACCENT)
        texto = f"pico {maximo:.0f}"
        c.drawString(min(w - 22, px + 3), min(h - 6, py + 3), texto)


# ---------------------------------------------------------------------
# COMPONENTES DE CONTEÚDO
# ---------------------------------------------------------------------

def identificar_hero_story(dados):
    """Identifica o artigo com a maior confiança e o marca como 'is_hero' = True."""
    maior_confianca = -1
    hero_artigo = None
    for tematica in dados.get("tematicas", []):
        for artigo in tematica.get("artigos", []):
            conf = artigo.get("confianca", 0)
            if isinstance(conf, (int, float)) and conf > maior_confianca:
                maior_confianca = conf
                hero_artigo = artigo

    if hero_artigo:
        hero_artigo["is_hero"] = True


def _grafico_barras(rotulos, valores, largura, altura, cor=NAVY, maxlen=18):
    """Barras horizontais reutilizáveis (tons, fontes...). Rótulos truncados."""
    d = Drawing(largura, altura)
    bar = HorizontalBarChart()
    bar.x = 110
    bar.y = 12
    bar.width = largura - 170
    bar.height = max(12, altura - 26)
    bar.data = [valores or [0]]
    bar.categoryAxis.categoryNames = [
        (str(r)[:maxlen] + "…") if len(str(r)) > maxlen else str(r)
        for r in (rotulos or ["—"])
    ]
    bar.valueAxis.valueMin = 0
    bar.valueAxis.valueMax = max(1, max(valores or [1]))
    bar.valueAxis.valueStep = max(1, int(max(valores or [1], default=1) / 2))
    bar.bars[0].fillColor = cor
    bar.categoryAxis.labels.fontName = "Helvetica"
    bar.categoryAxis.labels.fontSize = 6.5
    bar.valueAxis.labels.fontName = "Helvetica"
    bar.valueAxis.labels.fontSize = 6.5
    bar.strokeColor = RULE
    d.add(bar)
    return d


def criar_dashboard(dados, st):
    """Cria uma página de painel analítico com gráficos de distribuição."""
    fluxo = [
        Paragraph("PAINEL DE INTELIGÊNCIA", st["section_kicker"]),
        Paragraph("Dashboard Analítico", st["section"]),
        Paragraph("Distribuição temática, tom das narrativas e cobertura por fonte da edição.", st["section_deck"]),
        HRFlowable(width="100%", thickness=1.0, color=INK, spaceAfter=15),
    ]

    tematicas = dados.get("tematicas", [])

    # 1. Contagem de Temáticas
    theme_counts = {t.get("rotulo", t.get("nome")): len(t.get("artigos", [])) for t in tematicas}

    # 2. Contagem de Tons Narrativos
    tone_counts = Counter()
    fonte_counts = Counter()
    for t in tematicas:
        for a in t.get("artigos", []):
            tom = str(a.get("tom") or "não classificado")
            tone_counts[tom.capitalize()] += 1
            fonte_counts[str(a.get("fonte") or "n/d")] += 1

    # Montando Gráfico de Rosca (Temáticas)
    if theme_counts:
        d_pie = Drawing(CONTENT_W, 180)
        pie = Pie()
        pie.x = (CONTENT_W / 2) - 80
        pie.y = 20
        pie.width = 140
        pie.height = 140
        pie.data = list(theme_counts.values())
        pie.labels = list(theme_counts.keys())
        pie.sideLabels = 1

        # Aplicando cores semânticas se as fatias baterem com o dicionário
        for i, label in enumerate(pie.labels):
            cor_hex = CORES_SEMANTICAS.get(label.upper(), ACCENT)
            pie.slices[i].fillColor = cor_hex

        d_pie.add(pie)
        fluxo.extend([
            Paragraph("<b>Distribuição por Eixo Temático</b>", st["body"]),
            Spacer(1, 5),
            d_pie,
        ])

    # Grafico de Tons
    if tone_counts:
        rotulos = list(tone_counts.keys())
        fluxo.extend([
            Spacer(1, 20),
            Paragraph("<b>Distribuição de Tons Narrativos Globais</b>", st["body"]),
            Spacer(1, 10),
            _grafico_barras(rotulos, [tone_counts[r] for r in rotulos], CONTENT_W * 0.9, 130),
        ])

    # Gráfico de Cobertura por Fonte (melhoria 5)
    if fonte_counts:
        top_fontes = fonte_counts.most_common(6)
        rotulos = [nome for nome, _ in top_fontes]
        valores = [n for _, n in top_fontes]
        fluxo.extend([
            Spacer(1, 20),
            Paragraph("<b>Cobertura por Fonte (top 6)</b>", st["body"]),
            Spacer(1, 10),
            _grafico_barras(rotulos, valores, CONTENT_W * 0.9, 130, cor=ACCENT),
        ])

    fluxo.extend([
        Spacer(1, 20),
        HRFlowable(width="100%", thickness=.5, color=RULE, spaceAfter=5),
        Paragraph("<i>Legenda: Gráficos gerados automaticamente com base no volume e nas métricas de classificação da Inteligência Artificial.</i>", st["disclaimer"])
    ])

    return fluxo


def ficha_tecnica(dados, st):
    """Gera a página final de auditoria metodológica."""
    auditoria = dados.get("auditoria", {})
    fluxo = [
        Paragraph("TRANSPARÊNCIA E METODOLOGIA", st["section_kicker"]),
        Paragraph("Ficha Técnica da Edição", st["section"]),
        Paragraph("Números reais de execução do pipeline nesta data.", st["section_deck"]),
        HRFlowable(width="100%", thickness=1.0, color=INK, spaceAfter=15),
    ]

    infos = [
        f"<b>Fontes Lidas (Coverage):</b> {esc(auditoria.get('fontes_lidas', 'N/A'))}",
        f"<b>Funil de Artigos:</b> {esc(auditoria.get('funil', 'N/A'))}",
        f"<b>Total de Artigos Analisados (Filtro Final):</b> {esc(auditoria.get('total_artigos', 'N/A'))}",
        f"<b>Custo Estimado da Edição:</b> {esc(auditoria.get('custo_estimado', 'N/A'))}",
        f"<b>Modelos de IA Utilizados:</b> {esc(auditoria.get('modelos_ia', 'N/A'))}",
    ]
    for info in infos:
        fluxo.append(Paragraph(info, st["body"]))
        fluxo.append(Spacer(1, 3))

    # custo por camada (tabela compacta)
    camadas = auditoria.get("custo_por_camada") or []
    if camadas:
        celulas = [
            [Paragraph("CAMADA", st["audit_head"]),
             Paragraph("CUSTO REAL", st["audit_head"])]
        ]
        for nome, valor in camadas:
            celulas.append([
                Paragraph(esc(nome), st["audit_value"]),
                Paragraph(esc(_fmt_custo(valor)), st["audit_value"]),
            ])
        tab = Table(celulas, colWidths=[80*mm, 45*mm], hAlign="LEFT")
        tab.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, 0), .9, INK),
            ("LINEBELOW", (0, -1), (-1, -1), .55, RULE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        fluxo.extend([Spacer(1, 10), Paragraph("<b>Custo por camada</b>", st["body"]), tab])

    fluxo.extend([
        Spacer(1, 12),
        Paragraph("<b>Nota Metodológica:</b>", st["body"]),
        Paragraph(auditoria.get("nota_metodologica", "Informações classificadas automaticamente."), st["body"]),
    ])

    return fluxo


def _fmt_custo_pdf(valor):
    if isinstance(valor, (int, float)):
        if valor <= 0:
            return "US$ 0,00"
        if valor < 0.05:
            return "US$ " + f"{valor:.4f}".replace(".", ",")
        return "US$ " + f"{valor:.2f}".replace(".", ",")
    return str(valor)


_fmt_custo = _fmt_custo_pdf  # usado pela tabela de camadas


def metadata_capa(dados, st):
    campos = [
        ("DATA", dados.get("data", "—")),
        ("EDIÇÃO", dados.get("edicao", "—")),
        ("MODELO DE IA", dados.get("modelo_ia", "Não informado")),
        ("ARTIGOS", dados.get("artigos_analisados", "—")),
    ]
    celulas = []
    for rotulo, valor in campos:
        celulas.append(Paragraph(
            f'<font name="Helvetica-Bold" size="6.2" color="#64748B">{esc(rotulo)}</font>'
            f'<br/><font name="Helvetica-Bold" size="8.5" color="#191F26">{esc(valor)}</font>',
            st["cover_meta"],
        ))
    tab = Table([celulas], colWidths=[CONTENT_W/len(celulas)]*len(celulas), hAlign="LEFT")
    commands = [
        ("LINEABOVE", (0, 0), (-1, -1), .7, INK),
        ("LINEBELOW", (0, 0), (-1, -1), .7, INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for i in range(1, len(celulas)):
        commands.append(("LINEBEFORE", (i, 0), (i, 0), .6, RULE))
    tab.setStyle(TableStyle(commands))
    return tab


def barra_analise_radar(texto, st):
    contenido = [
        Paragraph("LEITURA ANALÍTICA", st["panel_label"]),
        Paragraph(esc(texto or "Não há análise textual disponível."), st["trend_analysis"]),
    ]
    tab = Table([[contenido]], colWidths=[CONTENT_W], hAlign="LEFT")
    tab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("LINEBEFORE", (0, 0), (0, 0), 2.5, ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tab


def bloco_termo_tendencia(item, st):
    nome = esc(item.get("termo", "Termo sem nome"))
    try:
        indice = max(0, min(100, int(float(item.get("indice_atual", 0)))))
    except (ValueError, TypeError):
        indice = 0
    variacao = esc(item.get("variacao", "Não informada"))
    periodo = esc(item.get("periodo", "período não informado"))
    status = str(item.get("status", "estável") or "estável").lower()
    if "alta" in status or "subida" in status:
        status_texto, status_cor, var_cor = "EM ALTA", ACCENT, ACCENT
    elif any(x in status for x in ("queda", "baixa", "declínio", "declinio")):
        status_texto, status_cor, var_cor = "EM QUEDA", NAVY, NAVY
    else:
        status_texto, status_cor, var_cor = "ESTÁVEL", MUTED, INK

    col_termo = [Paragraph(nome, st["trend_term"]),
                 Paragraph(f'<font color="{status_cor.hexval()}">{status_texto}</font>', st["trend_status"])]

    # Série histórica: Sparkline quando disponível; barra estática como fallback.
    serie = item.get("series") or []
    cor_var = NAVY if any(x in status for x in ("queda", "baixa", "declínio", "declinio")) else ACCENT
    if len(serie) >= 2:
        medidor = Sparkline(serie, cor=cor_var, width=53*mm)
        legenda_serie = Paragraph("SÉRIE 7D (PICO DESTACADO)", st["trend_label"])
    else:
        medidor = BarraInteresse(indice, status, width=53*mm)
        legenda_serie = None

    col_indice = [Paragraph("ÍNDICE DE INTERESSE (0-100)", st["trend_label"]),
                  Paragraph(f'{indice}<font size="8" color="#64748B"> / 100</font>', st["trend_index"]),
                  Spacer(1, 2), medidor]
    if legenda_serie:
        col_indice.append(legenda_serie)
    col_variacao = [Paragraph("VARIAÇÃO", st["trend_label"]),
                    Paragraph(f'<font color="{var_cor.hexval()}">{variacao}</font>', st["trend_variation"]),
                    Paragraph(f'<b>Comparação:</b> {periodo}', st["trend_period"])]
    tab = Table([[col_termo, col_indice, col_variacao]],
                colWidths=[47*mm, 70*mm, CONTENT_W-117*mm], hAlign="LEFT")
    tab.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), .55, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return tab


def secao_radar(dados_tendencias, st):
    radar = dados_tendencias or {}
    fluxo = [
        Paragraph("SINAIS DE ATENÇÃO", st["section_kicker"]),
        Paragraph("Radar de tendências", st["section"]),
        Paragraph("Interesse de busca, variação e janela de comparação.", st["section_deck"]),
        HRFlowable(width="100%", thickness=1.0, color=INK, spaceAfter=8),
        barra_analise_radar(radar.get("texto_analise", ""), st),
        Spacer(1, 5*mm),
    ]
    termos = radar.get("termos", []) or []
    if termos:
        cab = Table([[
            Paragraph("TERMO", st["trend_head"]),
            Paragraph("INTERESSE ATUAL", st["trend_head"]),
            Paragraph("VARIAÇÃO / PERÍODO", st["trend_head"]),
        ]], colWidths=[47*mm, 70*mm, CONTENT_W-117*mm], hAlign="LEFT")
        cab.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 1.0, INK),
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        fluxo.append(cab)
        for item in termos:
            fluxo.extend([KeepTogether([bloco_termo_tendencia(item, st)]), Spacer(1, 1*mm)])
    else:
        fluxo.append(Paragraph("Nenhum termo de tendência foi fornecido.", st["body"]))
    fluxo.extend([
        Spacer(1, 3*mm),
        HRFlowable(width="100%", thickness=.5, color=RULE, spaceAfter=4),
        Paragraph(
            "NOTA METODOLÓGICA — O índice de interesse do Google Trends é relativo e normalizado em uma escala de 0 a 100; não representa contagem absoluta de buscas. Interprete a variação junto ao índice atual e ao período de comparação indicado.",
            st["trend_note"],
        ),
    ])
    return fluxo


def cria_pull_quote(artigo, st):
    texto = str(artigo.get("pull_quote") or "").strip()
    resumo = str(artigo.get("resumo") or "").strip()
    if not texto and len(resumo) >= 220:
        sentencas = resumo.split(". ")
        texto = sentencas[0].strip().rstrip(".")
        if len(texto) > 175:
            texto = texto[:172].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."
    if texto:
        return PullQuote(texto, st)
    return None


def linha_tom_chip(artigo, st):
    """Linha de chips do vídeo: origem no Radar + sentimento + margem (melhoria 4)."""
    chip = artigo.get("tom_chip") or {}
    pedacos = []
    if chip.get("termo"):
        pedacos.append(f"<b>TERMO:</b> {esc(chip['termo'])}")
    tops = chip.get("top") or []
    if tops:
        nome0 = tops[0].get("nome", "")
        pcts = [f"{esc(nome0)} {tops[0].get('pct', 0)}%"]
        if len(tops) > 1:
            pcts.append(f"({esc(tops[1].get('nome', ''))} {tops[1].get('pct', 0)}%)")
        pedacos.append(f"<b>SENTIMENTO:</b> {' '.join(pcts)}")
    elif chip.get("tom_label"):
        pedacos.append(f"<b>SENTIMENTO:</b> {esc(chip['tom_label'])}")
    marcador = " (R)" if chip.get("forcado") else ""
    if pedacos:
        return Paragraph(
            "&nbsp;&nbsp;|&nbsp;&nbsp;".join(pedacos) + marcador,
            st["tom_chip"],
        )
    return None


def artigo_flowables(artigo, rotulo, cor_kicker, st):
    titulo = esc(artigo.get("titulo", "Sem título"))
    resumo = esc(artigo.get("resumo", "Resumo não disponível."))
    is_hero = artigo.get("is_hero", False)

    # 1. Kicker (Tag Superior) com cor injetada
    kicker_p = Paragraph(f'<font color="{cor_kicker.hexval()}">{esc(rotulo.upper())}</font>', st["article_kicker"])

    # 2. Hero Story (Formatação Especial) ou Manchete Padrão
    if is_hero:
        blocos_titulo = [
            HRFlowable(width="100%", thickness=2.5, color=ACCENT, spaceBefore=4, spaceAfter=6),
            Paragraph(titulo, st["hero_title"]),
            HRFlowable(width="100%", thickness=2.5, color=ACCENT, spaceBefore=2, spaceAfter=6),
        ]
    else:
        blocos_titulo = [
            HRFlowable(width="100%", thickness=.55, color=RULE, spaceBefore=2, spaceAfter=4),
            Paragraph(titulo, st["article_title"]),
            HRFlowable(width="100%", thickness=.55, color=RULE, spaceBefore=1, spaceAfter=5),
        ]
    # AVISO: KeepTogether dentro de célula de Table quebra o layout — o
    # keep.wrap() devolve o sentinel 0xffffff (16.777.215 pt) para forçar
    # split, e a Table passa a medir a row com essa altura. No fluxo de frame
    # funciona (split normal); na célula usamos `blocos_titulo` soltos.
    title_block = KeepTogether(blocos_titulo)

    pull = cria_pull_quote(artigo, st)

    # 3. Tratamento de Vídeo e Layout YouTube Side-by-Side
    tipo_fonte = str(artigo.get("tipo_fonte", "") or "").lower()
    link_original = str(artigo.get("link", "") or "").strip()
    fonte = str(artigo.get("fonte", "") or "").lower()
    eh_youtube = (
        "youtube" in tipo_fonte or "youtu.be" in link_original.lower()
        or "youtube.com" in link_original.lower() or "youtube" in fonte
    )
    thumb_path = artigo.get("thumbnail_path")
    chip_p = linha_tom_chip(artigo, st) if eh_youtube else None

    youtube_band_block = None
    if eh_youtube:
        views = artigo.get("views", artigo.get("visualizacoes", artigo.get("visualizações", "n/d")))
        eng = artigo.get("engajamento_pct", artigo.get("engajamento", artigo.get("engagement", "n/d")))
        eng_txt = f"{eng}%".replace(".", ",") if isinstance(eng, (int, float)) else eng
        likes = artigo.get("likes")
        faixa = (
            f'<font color="#FFFFFF"><b>VÍDEO</b>  |  '
            f'VIEWS: {esc(fmt_views(views))}  |  TOM: {esc(str(artigo.get("tom", "não classificado")).upper())}'
        )
        if isinstance(eng, (int, float)):
            faixa += f'  |  ENG: {esc(eng_txt)}'
        if likes is not None:
            faixa += f'  |  LIKES: {esc(fmt_views(likes))}'
        faixa += '</font>'
        # Limita a largura da banda se for num side-by-side
        w_band = (COLUMN_W * 0.7) if thumb_path else COLUMN_W
        tab_band = Table([[Paragraph(faixa, st["youtube_band"])]], colWidths=[w_band])
        tab_band.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        youtube_band_block = tab_band

    # 4. Metadados e Links
    metadados = [
        f'<b>FONTE</b> {esc(artigo.get("fonte", "Não informada"))}',
        f'<b>DATA</b> {esc(artigo.get("data", "Não informada"))}',
    ]
    if artigo.get("confianca") is not None:
        metadados.append(f'<b>CONFIANÇA IA</b> {esc(artigo.get("confianca"))}%')
    meta_p = Paragraph("&nbsp;&nbsp;|&nbsp;&nbsp;".join(metadados), st["meta"])

    if link_original.startswith(("https://", "http://")):
        dominio = urlparse(link_original).netloc or link_original
        link_xml = escape(link_original, {'"': "&quot;"})
        link_p = Paragraph(
            f'<link href="{link_xml}" color="#1D3348"><u>ABRIR FONTE</u></link>'
            f'&nbsp;&nbsp;<font color="#64748B">{esc(dominio)}</font>',
            st["link"],
        )
    else:
        link_p = Paragraph("LINK NÃO DISPONÍVEL", st["meta"])

    divisor = HRFlowable(width="100%", thickness=.45, color=RULE, spaceBefore=7, spaceAfter=8)

    # 5. Montagem do Output (Tabela Side-by-Side ou Fluxo Normal)
    saida = []

    if eh_youtube and thumb_path and os.path.exists(thumb_path):
        w_img = COLUMN_W * 0.3
        h_img = w_img * 0.75 # Formato 4:3

        img_obj = Image(thumb_path, width=w_img, height=h_img)

        col_direita = [kicker_p, youtube_band_block, Spacer(1, 4)] + \
            list(blocos_titulo) + [Paragraph(resumo, st["summary"])]
        if chip_p:
            col_direita.extend([chip_p])
        if pull:
            col_direita.extend([Spacer(1, 2), pull, Spacer(1, 5)])
        col_direita.extend([meta_p, link_p])

        t_layout = Table([[img_obj, col_direita]], colWidths=[COLUMN_W*0.3, COLUMN_W*0.7])
        t_layout.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (0,0), 6), # Espaçamento entre miniatura e texto
        ]))

        saida.append(t_layout)
        saida.append(divisor)

    else:
        saida.extend([kicker_p, title_block, Paragraph(resumo, st["summary"])])
        if chip_p:
            saida.extend([chip_p])
        if pull:
            saida.extend([Spacer(1, 2), pull, Spacer(1, 5)])
        if youtube_band_block:
            saida.extend([youtube_band_block, Spacer(1, 4)])

        saida.extend([meta_p, link_p, divisor])

    return saida


def bloco_tematica(tematica, st):
    nome = tematica.get("nome", "Temática")
    rotulo = str(tematica.get("rotulo", nome) or nome).upper()

    # Define a cor semântica verificando a string do rótulo
    cor_kicker = ACCENT
    for chave, cor in CORES_SEMANTICAS.items():
        if chave in rotulo:
            cor_kicker = cor
            break

    artigos = list(tematica.get("artigos", []) or [])
    cabecalho = [
        Paragraph(f'<font color="{cor_kicker.hexval()}">{esc(rotulo)}</font>', st["theme_kicker"]),
        Paragraph(esc(nome), st["theme"]),
    ]
    if tematica.get("destaque"):
        cabecalho.append(Paragraph(esc(tematica["destaque"]), st["theme_deck"]))
    cabecalho.append(HRFlowable(width="100%", thickness=.9, color=INK, spaceAfter=6))

    fluxo = []
    if artigos:
        primeira = artigo_flowables(artigos[0], rotulo, cor_kicker, st)
        fluxo.append(KeepTogether(cabecalho + primeira[:2]))
        fluxo.extend(primeira[2:])
        for artigo in artigos[1:]:
            fluxo.extend(artigo_flowables(artigo, rotulo, cor_kicker, st))
    else:
        fluxo.append(KeepTogether(cabecalho))
    fluxo.append(Spacer(1, 4))
    return fluxo


def header_footer(canvas, doc, dados):
    """Papel, cabeçalho, filete entre colunas, edição e paginação."""
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    if doc.page > 1:
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(.55)
        canvas.line(MARGIN_X, PAGE_H - 15.5*mm, PAGE_W - MARGIN_X, PAGE_H - 15.5*mm)
        canvas.setFont("Helvetica-Bold", 7.2)
        canvas.setFillColor(INK)
        canvas.drawString(MARGIN_X, PAGE_H - 12*mm, "OBSERVATÓRIO GLOBAL")
        canvas.setFont("Helvetica", 7.0)
        canvas.setFillColor(MUTED)
        right = f'{dados.get("edicao", "BRIEFING DIÁRIO")}  |  {dados.get("data", "")}'
        canvas.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 12*mm, right)

        canvas.setStrokeColor(RULE)
        canvas.line(MARGIN_X, 14.5*mm, PAGE_W - MARGIN_X, 14.5*mm)
        canvas.setFont("Helvetica", 6.8)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN_X, 9.5*mm, "BRIEFING DIÁRIO DE RELAÇÕES INTERNACIONAIS")
        canvas.drawRightString(PAGE_W - MARGIN_X, 9.5*mm, f"{doc.page:02d}")

        # Divisória vertical entre as duas colunas somente no miolo
        if getattr(doc, "page_template", None) and doc.page_template.id == "corpo":
            x = PAGE_W / 2
            canvas.setStrokeColor(RULE)
            canvas.setLineWidth(.35)
            canvas.line(x, MARGIN_BOTTOM, x, PAGE_H - MARGIN_TOP)
    canvas.restoreState()


def gerar_relatorio(dados, caminho_saida="relatorio_internacional.pdf"):
    """Gera o PDF com capa/radar de coluna única e miolo em duas colunas."""
    identificar_hero_story(dados)
    st = estilos()
    doc = BaseDocTemplate(
        caminho_saida,
        pagesize=A4,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title="Briefing Diário de Relações Internacionais",
        author="Observatório Global",
        subject="Análise diária de relações internacionais e riscos geopolíticos",
        pageCompression=1,
    )

    frame_capa = Frame(
        MARGIN_X, MARGIN_BOTTOM, CONTENT_W, PAGE_H-MARGIN_TOP-MARGIN_BOTTOM,
        id="capa_frame", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    frame_radar = Frame(
        MARGIN_X, MARGIN_BOTTOM, CONTENT_W, PAGE_H-MARGIN_TOP-MARGIN_BOTTOM,
        id="radar_frame", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    frame_esquerda = Frame(
        MARGIN_X, MARGIN_BOTTOM, COLUMN_W, PAGE_H-MARGIN_TOP-MARGIN_BOTTOM,
        id="corpo_esquerda", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    frame_direita = Frame(
        MARGIN_X + COLUMN_W + COLUMN_GAP, MARGIN_BOTTOM, COLUMN_W,
        PAGE_H-MARGIN_TOP-MARGIN_BOTTOM,
        id="corpo_direita", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )

    draw = lambda canvas, current_doc: header_footer(canvas, current_doc, dados)
    doc.addPageTemplates([
        PageTemplate(id="capa", frames=[frame_capa], onPage=draw),
        PageTemplate(id="radar", frames=[frame_radar], onPage=draw),
        PageTemplate(id="corpo", frames=[frame_esquerda, frame_direita], onPage=draw),
    ])

    story = []

    # -----------------------------------------------------------------
    # CAPA
    # -----------------------------------------------------------------
    story.extend([
        Spacer(1, 5*mm),
        HRFlowable(width="100%", thickness=2.2, color=ACCENT, spaceAfter=5),
        Paragraph("OBSERVATÓRIO GLOBAL", st["masthead"]),
        Paragraph("POLÍTICA INTERNACIONAL  •  INTELIGÊNCIA  •  CONTEXTO", st["masthead_deck"]),
        HRFlowable(width="100%", thickness=1.1, color=INK, spaceBefore=2, spaceAfter=8*mm),
        Paragraph(esc(dados.get("edicao", "EDIÇÃO DIÁRIA")).upper(), st["cover_kicker"]),
        Spacer(1, 3*mm),
        Paragraph(esc(dados.get("titulo_capa", "O MUNDO EM MOVIMENTO")), st["cover_title"]),
        HRFlowable(width="18%", thickness=2.4, color=ACCENT, hAlign="CENTER", spaceBefore=2, spaceAfter=5*mm),
        Paragraph(esc(dados.get("subtitulo_capa", "Análise diária da agenda internacional.")), st["cover_subtitle"]),
        Spacer(1, 10*mm),
        metadata_capa(dados, st),
        Spacer(1, 8*mm),
        HRFlowable(width="100%", thickness=.55, color=RULE, spaceAfter=4*mm),
        Paragraph("NESTA EDIÇÃO", st["cover_teaser_head"]),
    ])

    tematicas = list(dados.get("tematicas", []) or [])
    if tematicas:
        teaser_cells = [Paragraph(esc(t.get("nome", "Temática")), st["cover_teaser"]) for t in tematicas[:3]]
        teaser_cols = len(teaser_cells)
        teaser_table = Table([teaser_cells], colWidths=[CONTENT_W/teaser_cols]*teaser_cols, hAlign="LEFT")
        cmds = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for i in range(1, teaser_cols):
            cmds.append(("LINEBEFORE", (i, 0), (i, 0), .6, RULE))
        teaser_table.setStyle(TableStyle(cmds))
        story.extend([teaser_table, Spacer(1, 8*mm)])

    story.extend([
        HRFlowable(width="100%", thickness=.55, color=RULE, spaceAfter=4),
        Paragraph(
            "BRIEFING DE APOIO À ANÁLISE ESTRATÉGICA. Verifique afirmações relevantes nas fontes originais; sínteses e classificações de IA podem conter erros.",
            st["disclaimer"],
        ),
        NextPageTemplate("radar"),
        PageBreak(),
    ])

    # -----------------------------------------------------------------
    # RADAR E TENDÊNCIAS
    # -----------------------------------------------------------------
    story.extend(secao_radar(dados.get("dados_tendencias", {}), st))
    story.extend([NextPageTemplate("radar"), PageBreak()])

    # -----------------------------------------------------------------
    # DASHBOARD DE INTELIGÊNCIA
    # -----------------------------------------------------------------
    story.extend(criar_dashboard(dados, st))
    story.extend([NextPageTemplate("corpo"), PageBreak()])

    # -----------------------------------------------------------------
    # MIOLO EM DUAS COLUNAS
    # -----------------------------------------------------------------
    panorama = list(dados.get("panorama_geral", []) or [])
    story.extend([
        Paragraph("LEITURA DO DIA", st["section_kicker"]),
        Paragraph("Panorama geral", st["section"]),
        Paragraph("Os principais movimentos, suas conexões e o que merece acompanhamento.", st["section_deck"]),
        HRFlowable(width="100%", thickness=.9, color=INK, spaceAfter=7),
    ])
    if panorama:
        story.append(DropCapBlock(panorama[0], st))
        for paragrafo in panorama[1:]:
            story.append(Paragraph(esc(paragrafo), st["body"]))
    else:
        story.append(Paragraph("Panorama geral não informado.", st["body"]))

    analise_narrativas = str(dados.get("analise_narrativas", "") or "").strip()
    if analise_narrativas:
        story.extend([
            Spacer(1, 5),
            HRFlowable(width="100%", thickness=.8, color=INK, spaceBefore=2, spaceAfter=6),
            Paragraph("NARRATIVAS DIGITAIS", st["section_kicker"]),
            Paragraph("O que circula em vídeo", st["theme"]),
            Paragraph(esc(analise_narrativas), st["body"]),
        ])
        if len(analise_narrativas) >= 220:
            primeira_frase = analise_narrativas.split(". ")[0].rstrip(".")
            if len(primeira_frase) > 175:
                primeira_frase = primeira_frase[:172].rsplit(" ", 1)[0] + "..."
            story.extend([PullQuote(primeira_frase, st), Spacer(1, 6)])

    for i, tematica in enumerate(tematicas):
        story.extend([Spacer(1, 5), HRFlowable(width="100%", thickness=.65, color=RULE, spaceAfter=7)])
        story.extend(bloco_tematica(tematica, st))

    # -----------------------------------------------------------------
    # FICHA TÉCNICA (Nova página em coluna única)
    # -----------------------------------------------------------------
    story.extend([NextPageTemplate("radar"), PageBreak()])
    story.extend(ficha_tecnica(dados, st))

    doc.build(story)
    return caminho_saida


if __name__ == "__main__":
    destino = gerar_relatorio(DADOS, "relatorio_internacional_demo.pdf")
    print(f"PDF gerado: {destino}")
