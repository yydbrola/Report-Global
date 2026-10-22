# -*- coding: utf-8 -*-
"""Orquestrador da suíte de QA do Briefing Diário.

Fases (cada uma reporta exit-code próprio; artefatos em output/qa/):
1. Testes de PDF via pypdf sobre a rota mock (rápida, sem rede)
   → report.html
2. (opcional, requires rede) Run real do pipeline com --limit 2
   → report_e2e.html
3. Validação visual do relatório HTML com Playwright (Chromium headless)
   → report_qa_visual.html + evidencia.png

Uso:
    python run_tests.py           # fases 1 e 3 (mock + visual)
    python run_tests.py --e2e     # inclui fase 2 (pipeline real, ~3 min)
"""
import argparse
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).parent
QA_DIR = RAIZ / "output" / "qa"


def _fase(nome, args):
    print(f"\n{'=' * 62}\n{nome}\n{'=' * 62}")
    print("$ " + " ".join(str(a) for a in args))
    codigo = subprocess.call([str(a) for a in args], cwd=str(RAIZ))
    tag = "OK" if codigo == 0 else "FALHOU"
    print(f"[{tag}] {nome} (exit {codigo})")
    return codigo


def main():
    parser = argparse.ArgumentParser(description="Suite QA do Briefing Diário")
    parser.add_argument("--e2e", action="store_true",
                        help="inclui o run real do pipeline (rede, lento)")
    args = parser.parse_args()

    QA_DIR.mkdir(parents=True, exist_ok=True)
    pytest = [sys.executable, "-m", "pytest"]
    failing = []

    # Fase 1 — integridade do PDF (pypdf, mock determinístico)
    cod = _fase("FASE 1/3 — Integridade do PDF (pypdf, rota mock)", [
        *pytest, "tests", "-m", "not e2e and not qa_report", "-q",
        f"--html={QA_DIR / 'report.html'}", "--self-contained-html",
    ])
    if cod:
        failing.append("fase 1 (PDF)")

    # Fase 2 — pipeline real (opt-in; herda env: OPENROUTER/TRENDSAPI)
    if args.e2e:
        cod = _fase("FASE 2/3 — E2E do pipeline real (--limit 2)", [
            *pytest, "tests", "-m", "e2e", "-q",
            f"--html={QA_DIR / 'report_e2e.html'}", "--self-contained-html",
        ])
        if cod:
            failing.append("fase 2 (E2E)")
    else:
        print("\n[skip] FASE 2 (E2E) — use --e2e para incluir")

    # Fase 3 — audita o report.html no Chromium e grava evidencia.png
    cod = _fase("FASE 3/3 — QA visual do relatório (Playwright)", [
        *pytest, "tests/test_qa_report.py", "-m", "qa_report", "-q",
        f"--html={QA_DIR / 'report_qa_visual.html'}", "--self-contained-html",
    ])
    if cod:
        failing.append("fase 3 (Playwright)")

    print(f"\n{'=' * 62}\nRESUMO QA\n{'=' * 62}")
    print(f"relatório:   {QA_DIR / 'report.html'}")
    if args.e2e:
        print(f"e2e:         {QA_DIR / 'report_e2e.html'}")
    print(f"visual:      {QA_DIR / 'report_qa_visual.html'}")
    print(f"evidência:   {QA_DIR / 'evidencia.png'}")
    if failing:
        print(f"FALHAS: {', '.join(failing)}")
        return 1
    print("SUÍTE COMPLETA: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
