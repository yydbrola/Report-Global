# Visão Global — Pipeline de Curadoria de Notícias Internacionais

Pipeline automatizado que coleta notícias de relações internacionais, extrai o texto,
classifica tematicamente com o modelo de decisão **Jev** via OpenRouter **Decisions API**,
resume cada artigo com um chat Modelo (MiniMax via OpenRouter), gera a camada editorial
com **smolagents** e entrega um PDF editorial diário por e-mail (rascunho no Gmail).

```text
RSS/HTML ──> extração ──> classificação Jev ──> resumo por artigo ──> editorial (smolagents) ──> PDF ──> Gmail
            (newspaper3k      (typesafe/jev-1.13,   (minimax free,        (CodeAgent/ToolCallingAgent)
             → trafilatura     Choice + confiança)   cacheado) 
             → fallback título)
```

## Estrutura

```
pipeline_ri/
├── config.yaml          # fontes, categorias+rotulo, flags, TTL de cache, limites
├── main.py              # orquestrador CLI
├── modules/
│   ├── scraper.py           coleta (feedparser/requests+BS4, robots.txt, delays, dedup)
│   ├── extractor.py         extração (newspaper3k → trafilatura <100 chars → fallback_titulo)
│   ├── classifier_jev.py    classificação via Decisions API (endpoint_base parametrizado)
│   ├── summarizer.py        resumo 1–2 frases por artigo (chat, JSON estruturado)
│   ├── editorial_generator.py  camada editorial via smolagents (+ fallback directo)
│   ├── pdf_template.py      template editorial (ReportLab Platypus, KeepTogether por artigo)
│   ├── pdf_builder.py       adaptador: saída do pipeline → DADOS do template
│   └── gmail_sender.py      rascunho/envio via simplegmail
├── data/     (raw_*.json, extraidos_*.json, cache.json, edicao.json)  [gitignored]
└── output/   (relatorio_ri_*.pdf, dados_*.json)                        [gitignored]
```

## Setup

```powershell
cd pipeline_ri
py -3.10 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

### Chave OpenRouter (variável de ambiente; NUNCA no código)

```powershell
$env:OPENROUTER_API_KEY = "sk-or-v1-..."           # sessão
setx OPENROUTER_API_KEY "sk-or-v1-..."             # permanente (novo terminal vê)
```

### Gmail (OAuth Desktop)

1. Google Cloud Console → **APIs e serviços → Biblioteca** → ative **Gmail API**.
2. **Credenciais** → Criar credencial → ID do cliente OAuth → tipo
   **"Aplicativo de computador"** (o tipo Web NÃO funciona com simplegmail).
3. Renomear o JSON baixado para `client_secret.json` na raiz de `pipeline_ri/`.
4. Destino do e-mail: `config.yaml → email.destino` ou variável `EMAIL_DESTINO`.
5. Primeira execução abre o navegador para autorizar (conta Gmail alvo).

⚠ **App em "Testing": o refresh token expira em 7 dias.** Solução oficial: publicar o
app como **"Production"** no OAuth consent screen (uso pessoal não exige verificação).

## Uso

```powershell
.venv\Scripts\python main.py                    # run completo
.venv\Scripts\python main.py --dry-run          # só scrape+extração (não gasta API)
.venv\Scripts\python main.py --limit 10         # teste barato (10 artigos)
.venv\Scripts\python main.py --no-editorial     # skip smolagents/editorial
.venv\Scripts\python main.py --no-email         # gera PDF sem Gmail
.venv\Scripts\python main.py --email-only       # re-envia o último PDF (teste OAuth)
```

## Config principal (`config.yaml`)

- **fontes**: `tipo: rss` (feedparser) ou `tipo: html` (seção World — varre links do domínio).
  `robots.txt` é respeitado (URL proibida = pulada com log) e há delay entre requests.
- **categorias**: `nome` (exibida), `rotulo` (kicker da seção no PDF) e
  `criterio_jev` (descrição em inglês enviada para a pergunta Choice da Decisions API).
  A categoria `outros` é a opção de escape padrão (recomendação oficial: toda Choice precisa).
- **openrouter.endpoint_base**: endpoint base parametrizado — JEV usa `<base>/alpha/decisions`,
  chat usa `<base>/v1/chat/completions`. Migração = trocar essa linha.
- **editorial.motor**: `smolagents` (ToolCallingAgent com ferramentas) ou `directo` (uma
  chamada de chat pedindo o mesmo JSON). Falha do motor registra o erro e degrada o PDF.
- **cache.ttl_dias**: reusa classificação/resumo por URL (hash) por 7 dias — idempotência.
- **limites.max_artigos_por_fonte / delay_segundos / truncar_chars**: volume + contexto.

## Agendamento (Windows Task Scheduler)

```powershell
schtasks /Create /TN "VisaoGlobalBriefing" /SC DAILY /ST 07:30 ^
  /TR "powershell -ExecutionPolicy Bypass -File C:\caminho\pipeline_ri\rodar.ps1"
```

(`rodar.ps1`: ativa o venv, garante `$env:OPENROUTER_API_KEY`, roda `main.py` e registra data/hora.)

## Segurança

- `client_secret*.json`, `gmail_token.json`, `output/`, `data/`, `.env` estão no `.gitignore`.
- Verificação anti-leak antes de todo commit: `git diff --cached | grep -E "sk-or-v1|GOCSPX-|client_secret"`.
- Rotação pós-validação: a chave OpenRouter e o segredo OAuth do Google
  atravessaram canal de chat; gire ambos nos respectivos dashboards.

## Solução de problemas

| Sintoma | Causa provável | Ação |
|---|---|---|
| `punkt` download na 1ª extração | newspaper3k/nltk 1ª vez | normal; requer internet |
| HTTP 429 em `:free` | rate limit do modelo gratuito | retry/backoff automático; reduza `--limit` |
| 400 sem retry | payload inválido (Ex.: >255 opções) | cheque `criterio_jev`/config |
| 401 | chave inválida/ausente | confira `OPENROUTER_API_KEY` |
| PDF fecha sem panorama | editorial off/falhou | config `editorial.motor: directo` p/ testar |
| Gmail: redirect_uri mismatch | client tipo Web | use o tipo "Aplicativo de computador" |
