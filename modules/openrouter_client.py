# -*- coding: utf-8 -*-
"""Cliente HTTP mínimo para a OpenRouter.

Política de retry (doc oficial Decisions API):
- Tentar de novo: 408, 429, 5xx, 529, e 402 específico de
  "openrouter_in_flight_budget";
- Não tentar de novo: 400, 401, 402/403 de créditos, 413 (erro terminal);
- Backoff: header Retry-After quando existir, senão exponencial com jitter
  (base * 2^(n-1), teto configurável).

Caso especial: OpenRouter pode devolver HTTP 200 com corpo
{"error": {...}} (ex.: "Upstream idle timeout exceeded", code 504) e sem
"choices" — tratamos o código embutido com a mesma política de retry.
"""
import random
import time

import requests


class ErroTerminal(Exception):
    """Erro da API que não adianta re-tentar (request mal-formado, auth, créditos)."""


class ErroRetry(Exception):
    """Esgotaram-se as tentativas tentáveis."""

    def __init__(self, mensagem, retry_after=None):
        super().__init__(mensagem)
        self.retry_after = retry_after


def post_json(url, payload, api_key, tentativas=5, backoff_base=1.0,
              backoff_max=30.0, timeout=(10, 60), headers_extra=None):
    """POST com retry; devolve dict da resposta ou levanta ErroTerminal/ErroRetry."""
    cab = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    cab.update(headers_extra or {})
    ultimo_rty = None

    for tentativa in range(1, tentativas + 1):
        falha = None
        try:
            resp = requests.post(url, headers=cab, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            falha = ErroRetry(f"falha de transporte: {exc}")
        else:
            if resp.ok:
                try:
                    corpo_json = resp.json()
                except ValueError:
                    corpo_json = None
                tem_erro_embutido = (isinstance(corpo_json, dict)
                                     and "error" in corpo_json
                                     and "choices" not in corpo_json)
                if corpo_json is None:
                    raise ErroTerminal(
                        "HTTP 200 com corpo não decodificável como JSON")
                if not tem_erro_embutido:
                    return corpo_json
                erro = corpo_json["error"]
                codigo = erro.get("code") if isinstance(erro, dict) else None
                if isinstance(codigo, int) and (codigo in (408, 429) or codigo >= 500):
                    falha = ErroRetry(
                        f"corpo de erro dentro de HTTP 200: {resp.text[:400]}")
                else:
                    raise ErroTerminal(
                        f"corpo de erro dentro de HTTP 200: {resp.text[:400]}")
            else:
                corpo = resp.text[:400]
                if resp.status_code in (408, 429) or resp.status_code >= 500:
                    falha = ErroRetry(f"HTTP {resp.status_code}: {corpo}",
                                      _retry_after(resp.headers.get("Retry-After")))
                elif resp.status_code == 402 and "openrouter_in_flight_budget" in resp.text:
                    falha = ErroRetry(f"HTTP 402 in-flight budget: {corpo}",
                                      _retry_after(resp.headers.get("Retry-After")))
                else:
                    raise ErroTerminal(f"HTTP {resp.status_code}: {corpo}")

        espera = max(falha.retry_after or 0.0, 0.0)
        if espera == 0.0:
            espera = min(backoff_max, backoff_base * (2 ** (tentativa - 1)))
            espera += random.uniform(0, 1)
        if tentativa < tentativas:
            time.sleep(espera)
        else:
            ultimo_rty = falha

    raise ErroRetry(f"esgotaram {tentativas} tentativas; última falha: {ultimo_rty}",
                    getattr(ultimo_rty, "retry_after", None))


def _retry_after(valor):
    try:
        return float(valor) if valor else None
    except (TypeError, ValueError):
        return None
