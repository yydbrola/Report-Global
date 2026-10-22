# -*- coding: utf-8 -*-
"""Fixtures determinísticas para a suíte de QA do Briefing Diário.

Princípios:
- Nenhuma chamada de rede: o PDF de teste é construído por
  pdf_builder.montar_dados() + pdf_template.gerar_relatorio() com dados
  sintéticos (a mesma rota da produção, sem JEV/resumo/editorial).
- Zero efeito colateral no estado real: a numeração de edições é lida de
  `dir_dados` temporário (montar_dados só lê — quem incrementa é gerar()).
- Sem thumbnails (thumbnail_url ausente → sem download de imagem).
"""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def config():
    """Config real do projeto (categorias/tons/fontes — nada é mutado)."""
    with open(ROOT / "config.yaml", encoding="utf-8") as arq:
        return yaml.safe_load(arq)


@pytest.fixture(scope="session")
def editorial_teste():
    """Editorial determinístico (como se o modo directo tivesse respondido)."""
    return {
        "ativo": True,
        "titulo_capa": "TESTE DE REGRESSÃO\nDO BRIEFING",
        "subtitulo_capa": "Fixture determinística da suíte de QA — agenda sintética.",
        "panorama_geral": [
            "Parágrafo sintético um da camada editorial para a prova de integração.",
            "Parágrafo sintético dois, com vocabulário neutro e estrutura estável.",
        ],
        "destaques_por_tema": {
            "conflitos_guerras": "Sentença determinística de destaque do briefing.",
        },
        "analise_narrativas": (
            "Os canais em destaque são Canais Sinteticos SA, Revista Fixture e "
            "Times QA. O enquadramento dominante é o de posicionalidade técnica, "
            "com factualidade predominante nos cortes maiores e minoritária "
            "no volume total. O debate de economia concentra dois terços das exibições "
            "auditadas e é conduzido em tom crítico ao plano fiscal, enquanto os "
            "balões eleitorais usam enquadramento de agenda de campanha."
        ),
    }


def _artigo_rss(titulo, fonte, tema, url, dias):
    return {
        "titulo": titulo,
        "url": url,
        "fonte": fonte,
        "data_publicacao": f"2026-02-{19 + dias:02d}",
        "texto_extraido": "parágrafo determinístico do fixture. " * 60,
        "tipo_fonte": "rss",
        "tema": tema,
        "tema_confianca": 0.92,
        "resumo_curto": "Resumo sintético do fixture, frase única e estável.",
    }


def _artigo_video(titulo, canal, tema, tom, probs, url):
    return {
        "titulo": titulo,
        "url": url,
        "fonte": canal,
        "data_publicacao": "2026-02-20",
        "texto_extraido": "fala transcrita determinística do fixture. " * 120,
        "tipo_fonte": "youtube",
        "tema": tema,
        "tema_confianca": 0.78,
        "resumo_curto": (
            "Resumo sintético do vídeo do fixture com duas frases. " * 4
        ) + "Corte final do resumo auditado.",
        "canal": canal,
        "views": 40123,
        "likes": 933,
        "engajamento_pct": 2.3,
        "tom": tom,
        "tom_confianca": 0.71,
        "tom_probabilidades": probs,
        "tom_forcado": False,
        "termo_busca": "economia",
        "thumbnail_url": None,
        "pull_quote": "Cotação determinística extraída do transcrição do fixture.",
    }


@pytest.fixture(scope="session")
def artigos_teste():
    """3 artigos: 2 RSS + 1 vídeo (cache total, rede zero)."""
    return [
        _artigo_rss(
            "Órgãos do ISS emitem parecer conjunto sobre sanções comerciais",
            "Fonte Fixture Mundial", "conflitos_guerras",
            "https://fixture.example/parecer-conjunto", 1,
        ),
        _artigo_rss(
            "Acordo bilateral avança após rodada de negociações técnicas",
            "Diário Fixture", "diplomacia_negociacoes",
            "https://fixture.example/acordo-bilateral", 2,
        ),
        _artigo_video(
            "ECONOMIA 2026: câmara aprova plano e opositores criticam",
            "Canais Sinteticos SA", "economia_comercio", "critico_oposicao",
            {"critico_oposicao": 0.71, "neutro_informativo": 0.21},
            "https://www.youtube.com/watch?v=FIXT0000000",
        ),
    ]


@pytest.fixture(scope="session")
def radar_teste():
    """Radar com séries de 14 pontos para os sparklines (sem rede)."""
    series = {}
    termos = []
    for i, termo in enumerate(("geopolítica", "economia", "eleições")):
        pontos = [{"date": f"2026-02-{9 + j:02d}", "value": float(10 + j * 2 + i)}
                  for j in range(14)]
        series[termo] = pontos
        termos.append({
            "termo": termo,
            "indice_atual": 10 + 13 * 2 + i,
            "variacao": f"+{1200 - i * 171}%",
            "periodo": "7 dias",
            "status": "alta",
        })
    return {
        "top_trends": list(series.keys()),
        "termos": termos,
        "series": series,
        "texto_analise": (
            "Economia combina índice alto com aceleração expressiva; eleições "
            "cresce a partir de uma base baixa. Leitura sintética determinística "
            "do fixture para a prova de integração do painel de tendências."
        ),
    }


@pytest.fixture(scope="session")
def estatisticas_teste():
    return {
        "artigos": 3,
        "com_tema_especifico": 3,
        "com_resumo": 3,
        "em_cache": 0,
        "videos_youtube": 1,
        "custo_classificacao_usd": 0.0,
        "custo_resumo_usd": 0.0,
        "custo_editorial_usd": 0.0,
        "custo_total_usd": 0.0,
    }


@pytest.fixture(scope="session")
def _pasta_sessao(tmp_path_factory):
    """Diretório da sessão: PDF + edicao.json próprios dos testes."""
    pasta = tmp_path_factory.mktemp("qa_briefing")
    (pasta / "edicao.json").write_text('{"proxima": 7}', encoding="utf-8")
    return pasta


@pytest.fixture(scope="session")
def pdf_de_teste(_pasta_sessao, config, editorial_teste, artigos_teste,
                 radar_teste, estatisticas_teste):
    """Constrói o PDF da prova UMA vez por sessão; devolve (dict dados, caminho).

    Rota exata da produção — montar_dados() + gerar_relatorio() — sem as
    camadas que tocam a rede (JEV/sumário/editorial LLM/Trends/YouTube).
    """
    from modules import pdf_builder, pdf_template

    dados = pdf_builder.montar_dados(
        artigos_teste, config, editorial_teste, "20/02/2026",
        dir_dados=str(_pasta_sessao), radar_tendencias=radar_teste,
        estatisticas=estatisticas_teste, dir_saida=str(_pasta_sessao),
    )
    caminho = _pasta_sessao / "prova_briefing.pdf"
    pdf_template.gerar_relatorio(dados, str(caminho))
    return {"dados": dados, "pdf": caminho}
