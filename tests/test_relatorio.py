# -*- coding: utf-8 -*-
"""QA do artefato PDF do Briefing Diário (rota mock, determinística).

Usa pypdf para extrair o texto do PDF gerado pela FIXTURE (mesma rota de
produção: montar_dados + gerar_relatorio) e verifica integridade mínima:
capa, seções críticas e consistência PDF x JSON de saída.

Testes marcados `@pytest.mark.e2e` executam o pipeline REAL (rede, lento)
e só rodam via `python run_tests.py --e2e` ou `pytest -m e2e`.
"""
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pytest
from pypdf import PdfReader


def _norm(txt):
    """Maiúsculas sem acentos — insensível ao kerning do stream do reportlab."""
    if not txt:
        return ""
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", txt).upper()


def _texto(pdf_path):
    leitor = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in leitor.pages)


def _conta_artigos(norm_txt):
    """Cada artigo tem um link 'ABRIR FONTE <dominio>'; a nota metodológica
    da Ficha menciona '... (links de ABRIR FONTE)' — cuja ocorrência termina
    em ')' e é excluída da contagem por lookahead negativo."""
    return len(re.findall(r"ABRIR FONTE(?!\))", norm_txt))


# ----------------------------------------------------------------- #
# Testes da rota MOCK (rápidos, determinísticos, sem rede)
# ----------------------------------------------------------------- #

def test_pdf_integro(pdf_de_teste):
    dados = pdf_de_teste["dados"]
    pdf = pdf_de_teste["pdf"]
    assert pdf.exists() and pdf.stat().st_size > 10000
    leitor = PdfReader(str(pdf))
    assert len(leitor.pages) >= 4  # capa + radar + miolo + ficha técnica
    assert dados["edicao"] == "BRIEFING DIÁRIO  |  EDIÇÃO 007"


def test_secoes_criticas_no_texto(pdf_de_teste):
    txt = _norm(_texto(pdf_de_teste["pdf"]))
    for ancora in ("RADAR DE TEND", "NARRATIVAS DIGITAIS", "FICHA TECNICA"):
        assert ancora in txt, f"seção ausente no PDF: {ancora}"


def test_capa_com_titulo_editorial(pdf_de_teste):
    txt = _norm(_texto(pdf_de_teste["pdf"]))
    assert "TESTE DE REGRESSAO DO BRIEFING" in txt
    assert "BRIEFING DIARIO" in txt
    assert "EDICAO 007" in txt


def test_artigos_pdf_bateria_json(pdf_de_teste):
    dados = pdf_de_teste["dados"]
    txt = _norm(_texto(pdf_de_teste["pdf"]))
    esperado = sum(len(t.get("artigos") or []) for t in dados["tematicas"])
    n_pdf = _conta_artigos(txt)
    assert esperado == 3, "fixture deve ter 3 artigos no JSON"
    assert n_pdf == esperado, f"PDF tem {n_pdf} artigos, JSON tem {esperado}"


# ----------------------------------------------------------------- #
# Teste E2E real (opt-in) — rede, contrato completo do pipeline
# ----------------------------------------------------------------- #

@pytest.mark.e2e
def test_e2e_pipeline_real():
    """Roda main.py --limit 2 --no-email e valida o artefato de hoje."""
    raiz = Path(__file__).parent.parent
    processo = subprocess.run(
        [sys.executable, "main.py", "--trends", "--youtube",
         "--limit", "2", "--no-email"],
        capture_output=True, text=True, cwd=str(raiz), timeout=1200,
        encoding="utf-8", errors="replace", env=os.environ,
    )
    output = raiz / "output"
    hoje = datetime.now().strftime("%Y-%m-%d")
    pdf_path = output / f"relatorio_ri_{hoje}.pdf"
    json_path = output / f"dados_{hoje}.json"

    assert processo.returncode == 0, (
        f"pipeline falhou:\n{processo.stdout}\n{processo.stderr}")
    assert pdf_path.exists() and json_path.exists()
    import json
    dados = json.loads(json_path.read_text(encoding="utf-8"))
    txt = _norm(_texto(pdf_path))
    for ancora in ("RADAR DE TEND", "FICHA TECNICA"):
        assert ancora in txt
    esperado = sum(len(t.get("artigos") or []) for t in dados["tematicas"])
    n_pdf = _conta_artigos(txt)
    assert n_pdf == esperado, f"E2E: PDF {n_pdf} != JSON {esperado}"
