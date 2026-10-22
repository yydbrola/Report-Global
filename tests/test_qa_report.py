# -*- coding: utf-8 -*-
"""QA visual do relatório HTML do pytest (executado na fase 2 do run_tests.py).

O relatório `output/qa/report.html` (gerado na fase 1) é aberto no Chromium
headless via pytest-playwright; o teste confere a estrutura do resumo e
grava a evidência `output/qa/evidencia.png`.
"""
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
QA_DIR = RAIZ / "output" / "qa"

pytestmark = pytest.mark.qa_report


def test_relatorio_html_e_evidencia(page):
    report = QA_DIR / "report.html"
    if not report.exists():
        pytest.skip("report.html não encontrado — rode run_tests.py antes")

    page.goto(report.resolve().as_uri())

    conteudo = page.locator("body").inner_text().lower()
    m_pass = re.search(r"(\d+)\s*passed", conteudo)
    assert m_pass and int(m_pass.group(1)) >= 1, (
        f"relatório sem testes passados: {conteudo[:300]}")
    m_reprov = re.search(r"[1-9]\d*\s*(failed|error)", conteudo)
    assert not m_reprov, f"relatório indica reprovações: {m_reprov.group(0)}"

    evidencia = QA_DIR / "evidencia.png"
    page.screenshot(path=str(evidencia), full_page=True)
    assert evidencia.exists() and evidencia.stat().st_size > 20000
