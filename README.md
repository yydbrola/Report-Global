# Visão Global — Pipeline de Curadoria de Notícias Internacionais

Pipeline automatizado que, uma vez por dia, **coleta notícias de relações internacionais
em 18 fontes, extrai o texto, classifica cada artigo em 10 temas com o modelo de decisão
"Jev", resume os artigos em português, escreve o corpo editorial com um agente de IA,
gera um PDF editorial com design de jornal e deixa o relatório pronto como rascunho
no seu Gmail** — você só revisa e envia.

```text
┌────────────┐  ┌───────────┐  ┌──────────────┐  ┌─────────┐  ┌───────────┐   ┌──────┐  ┌────────┐
│ 1 COLETA   │→ │ 2 EXTRAÇÃO│→ │ 3 CLASSIFICA │→ │ 4 RESUMO│→ │ 5 EDITORIAL│→ │ 6 PDF│→ │ DRAFTS │
│ RSS/HTML   │  │ newspaper3k│ │ JEV Choice   │  │ chat    │  │ smolagents │  │Report│  │ Gmail  │
│ round-robin│  │ trafilatura│ │ + confiança  │  │ PT-BR   │  │Agente +directo│ Lab  │  │ anexado│
└────────────┘  └───────────┘  └──────────────┘  └─────────┘  └───────────┘   └──────┘  └────────┘
`scraper.py`   `extractor.py`  `classifier_jev.py` `summarizer.py` `editorial_generator.py` `pdf_builder.py` + `pdf_template.py` → `gmail_sender.py`
```

- Tudo é configurável em **um único arquivo** (`config.yaml`): fontes, temas, modelos,
  destino do e-mail, limites.
- Há **cache idempotente** (7 dias): reexecutar não gasta duas vezes a mesma classificação.
- Riscos tratados: quando algo falha, o pipeline **degrada limpo** — a edição sai mesmo
  sem a camada editorial ou sem resumo, e o log denuncia cada queda.
- Custo típico: com os modelos padrão (Jev pago + chat grátis), ~US$ 0,005 por edição
  de 60 artigos.

---

## 1. Pré-requisitos (contas e credenciais)

| Item | Para quê | Onde conseguir |
|---|---|---|
| **Python 3.10+** | rodar o projeto | `py -3.10 --version` p/ conferir |
| **Conta OpenRouter + chave de API** | modelos de IA (classificação, resumo, editorial) | https://openrouter.ai/settings/keys |
| **Conta Google (a do e-mail de destino)** | receber o briefing e autorizar o app | a que você quer que receba o e-mail |
| **Projeto no Google Cloud Console** | habilitar Gmail API e criar credencial OAuth | https://console.cloud.google.com — crie um projeto (ex.: `scrap-512402`) |

Nada do seu e-mail/senha fica no projeto: a integração usa **OAuth** — a única conta
Google que o app toca é a escolhida no navegador de consentimento.

**Arquivos que ficam na raiz de `pipeline_ri/` (gitignored — nunca vão pro repositório):**

| Arquivo | Origem | Papel |
|---|---|---|
| `client_secret.json` | baixado do Google Cloud Console | credencial do app OAuth |
| `gmail_token.json` | gerado na 1ª execução | token de acesso — refresh automático |

---

## 2. Setup — usar com o SEU e-mail (passo a passo)

### 2.1 Instalação

```powershell
cd pipeline_ri
py -3.10 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

### 2.2 Chave do OpenRouter (variável de ambiente — NUNCA no código)

```powershell
$env:OPENROUTER_API_KEY = "sk-or-v1-..."    # apenas esta sessão
setx OPENROUTER_API_KEY "sk-or-v1-..."      # permanente (abrir terminal NOVO depois)
```

### 2.3 Configurar o Google (quatro portões na ordem)

**a) Habilitar a Gmail API** — sem isso: `HttpError 403 ... accessNotConfigured`
> Console → *APIs e Serviços* → *Biblioteca* → **Gmail API** → **Enable**

**b) Criar a credencial OAuth** — Console → *APIs e Serviços* → *Credenciais* →
*+ Criar credenciais* → *ID do cliente OAuth*. Duas rotas válidas:

| Tipo | Peculiaridade |
|---|---|
| **Aplicativo da Web** (padrão do projeto) | precisa registrar em "URIs de redirecionamento autorizados" exatamente `http://localhost:8080/`; sem isso o erro é `Error 400: redirect_uri_mismatch` |
| **Aplicativo de computador** (Desktop) | funciona sem registrar URI — configuração mais simples |

Baixe o JSON, guarde como **`client_secret.json`** na raiz de `pipeline_ri/`.

**c) Cadastrar seu Gmail como usuário de teste** — Google Auth Platform → *Público*
→ **Usuários de teste** → + Add users → **seu@gmail.com**. Sem isso: `Erro 403: access_denied`
("app não pode ser acessado por testadores aprovados").

**d) Na primeira execução**, um navegador abre o fluxo de consentimento:
entre com a conta que vai **receber** o briefing → (aviso de app não verificado)
*Avançado* → *Ir para <nome do projeto>* → **Permitir**. O token fica salvo em
`gmail_token.json` e as próximas execuções **não** pedem consentimento.

> ⚠ App em **"Testing"**: o refresh token **expira em 7 dias** (aí é só rodar de novo e
> refazer o consentimento). Para não expirar: Google Auth Platform → *Publicar app* →
> **Production** (uso pessoal não exige verificação do Google).

### 2.4 Definir para quem vai o e-mail

No `config.yaml`:

```yaml
email:
  destino: "seu@gmail.com"     # ou deixe "" e use a variável de ambiente EMAIL_DESTINO
  modo: draft                  # draft (rascunho) | send (envia direto)
```

### 2.5 Primeiro run completo

```powershell
.venv\Scripts\python main.py --limit 10
```

O terminal mostra o progresso por etapa; no fim, o rascunho aparece no Gmail com o
assunto **"Relatório de Relações Internacionais – dd/mm/aaaa"** e o PDF em anexo.

---

## 3. Uso diário (flags do `main.py`)

```powershell
.venv\Scripts\python main.py                  # execução completa (uso diário padrão)
.venv\Scripts\python main.py --no-email       # gera o PDF; não toca no Gmail
.venv\Scripts\python main.py --dry-run        # só scraping+extração — zero chamada de API
.venv\Scripts\python main.py --limit 10       # cap de artigos p/ teste barato
.venv\Scripts\python main.py --no-editorial   # pula a camada editorial (PDF degrada)
.venv\Scripts\python main.py --no-sumario     # pula resumo por artigo
.venv\Scripts\python main.py --email-only     # só re-envia o último PDF (teste OAuth)
.venv\Scripts\python main.py --config X.yaml  # config alternativo
```

---

## 4. Usando seus modelos (OpenRouter — ou provedor próprio)

Todos os modelos vivem no `config.yaml` — nenhum no código:

```yaml
openrouter:
  endpoint_base: "https://openrouter.ai/api"   # endpoint base parametrizado

jev:
  modelo: "typesafe/jev-1.13"                  # classificação (Decisions API)

sumario:
  modelo: "nvidia/nemotron-3-ultra-550b-a55b:free"   # resumo por artigo (chat)

editorial:
  motor: "directo"                             # smolagents | directo
  modelo: "nvidia/nemotron-3.5-super-vl:free"  # camada editorial (chat)
```

- **Trocar um modelo por outro** no OpenRouter: substitua o valor de `modelo` por qualquer
  ID do catálogo (https://openrouter.ai/models) — ex. `"openai/gpt-4o-mini"`,
  `"google/gemini-2.0-flash-001"`, `"anthropic/claude-3.5-haiku"`. Modelos `:free`
  têm cota por minuto — a pipeline já tem retry/backoff automático; para volume maior,
  use modelo pago.
- **Política do projeto**: apenas modelos `:free` (registrada no cabeçalho do
  `config.yaml`); o `minimax/minimax-m3.1-flash:free` antigo foi aposentado pelo
  OpenRouter em 22/10/2026 — mantenha IDs vivos do catálogo.
- **Jev** é diferente: só roda em provedores que implementem o protocolo **Decisions**
  (`<endpoint_base>/alpha/decisions`). Com OpenRouter, mantenha os IDs da família
  `typesafe/jev-*`. Se um dia migrar de provedor, troque **só** `endpoint_base`.
- **Modelos com raciocínio** (série que "pensa antes de responder", como os Nemotron
  da NVIDIA) consomem tokens de raciocínio antes do JSON: se os resumos começarem a
  falhar com `finish_reason: length`, suba o teto:

```yaml
sumario:
  max_tokens: 4000     # padrão interno do código: 3000
editorial:
  max_tokens: 5000     # atual no config: 4500 (motor directo)
```

---

## 5. Controlando os sites visitados (fontes)

Cada fonte é um item da lista `fontes:` no `config.yaml`:

```yaml
fontes:
  - nome: "The Guardian"                                   # como exibir no PDF/log
    url: "https://www.theguardian.com/world/rss"           # a fonte em si
    tipo: rss                                              # rss | html
    ativo: true                                            # false = pulada
```

- **Adicionar**: copie um bloco, troque `nome`/`url` e cole no fim da lista
  (a ordem da lista define só a ordem de coleta — o round-robin intercala 1 artigo
  de cada fonte até o limite).
- **Remover/desativar**: apague o bloco, ou deixe `ativo: false` para manter
  histórico.
- **Encontrar RSS**: procure o ícone de feed na home do site (muitas vezes
  `https://site.com/rss`, `/feed`, `/rss.xml`); também dá para usar os canais de
  tópico (ex.: `…/news/middle_east/rss.xml`).
- **`tipo: html`** destina-se a páginas de seção sem RSS: indicar a pág. da
  seção (ex. `https://www.aljazeera.com/where/middle-east`) — o scraper varre links
  de notícia no domínio.
- **robots.txt é respeitado**: sites cujo robots nega bots aparecem no log como
  `robots.txt proíbe fetch da fonte X; pulando`. Não há bypass no projeto: troque
  a fonte por outra com RSS aberto ou negocie credenciamento com o veículo.
- **Limites** de volume (tudo em `limites:`): `max_artigos_por_fonte` (25),
  `max_artigos_total` (60/edição), `delay_segundos` (2,5 entre requests),
  `truncar_chars` (6000 por artigo p/ enviar ao modelo).

---

## 6. Controlando a classificação do JEV (categorias e critérios)

A seção `categorias:` do `config.yaml` alimenta diretamente a pergunta **Choice**
da Decisions API — uma opção por tema:

```yaml
categorias:
  conflitos_guerras:            # chave de identificação (id interno; usada no cache)
    nome: "Conflitos e Guerras"           # exibida na seção do PDF
    rotulo: "CONFLITOS"                   # kicker da seção no PDF
    criterio_jev: >-                      # descrição (em INGLÊS) que o JEV lê
      Active armed conflicts, wars, military invasions...
```

**Regras ao editar:**

1. **Chaves**: `snake_case`, únicas, sem espaços — os artigos são gravados no cache e
   rendem nos temas por essa chave.
2. **`criterio_jev` sempre em inglês**: aí é só texto que o JEV usa como descrição de
   opção. Quanto mais mutuamente exclusivo e coletivamente exaustivo (estilo MECE),
   mais confiança e menos artigos caindo em "Outros". Mantenha a categoria `outros`
   como última opção de escape — o modelo e o PDF esperam que ela exista.
3. **Ordem do dict = ordem das seções no PDF**.
4. **Limite**: a API aceita até 255 opções (mais que isso = erro 400 sem retry).
5. **Adicionar/remover/renomear = mexer só no `config.yaml`** — sem tocar no código.

**⚠️ Ao alterar critérios, limpe o cache de temas** — o cache (7 dias) guarda
classificações antigas por URL e **não detecta** que os critérios mudaram. Purgando
só a parte de temas (os resumos permanecem, poupando chamadas):

```powershell
.venv\Scripts\python.exe -c "import json,pathlib; p=pathlib.Path('data/cache.json'); c=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}; c={k:{kk:vv for kk,vv in r.items() if kk!='tema'} for k,r in c.items()}; c={k:v for k,v in c.items() if v}; p.write_text(json.dumps(c,ensure_ascii=False,indent=1),encoding='utf-8')"
```

O grau de confiança de cada artigo vem na seção do PDF (`confiança NN%`) — use-o para
saber se critérios estão disputando entre si: confiança baixa recorrente no mesmo tema
= criterio_jev dela precisa ficar mais explícito/diferente dos vizinhos.

---

## 7. Ajustando o PDF (corpo, cores, textos)

O template é 100% seu para mexer: `modules/pdf_template.py` (o `pdf_builder.py` só
traduz os dados do pipeline para o formato que o template espera).

**Mapa rápido dos pontos de edição:**

| O quê | Onde |
|---|---|
| Paleta (cores) | constantes no topo: `INK` (quase preto), `NAVY`, `ACCENT` (vermelho discreto), `PAPER` (fundo), `PALE` (blocos de apoio), `RULE` (fios/divisórias), `MUTED` (metadados) — em `colors.HexColor('#XXXXXX')` |
| Tipografia/tamanhos | função `estilos()` (Times/Helvetica, kickers, títulos, corpo) |
| Moldura da Capa (titulo/subtítulo/data/edição) | `metadata_capa()` |
| Bloco "Panorama" (parágrafos da camada editorial) | `panorama_box()` |
| Cada artigo (título, resumo, fonte, confiança, link) | `artigo_flowable()` |
| Cada seção temática (kicker + destaque + artigos) | `bloco_tematica()` |
| Cabeçalho/rodapé de página (edição, foliais) | `header_footer()` |
| Margens e montagem do documento | margens ~18 mm laterais, montagem da `story` e chamada final: `gerar_relatorio()`; textos fixos como "BRIEFING DIÁRIO" e "TEMAS EM FOCO" estão nesta função |
| Cada artigo numa página própria (KeepTogether) | `bloco_tematica()`/`gerar_relatorio()` — remover o KeepTogether de um artigo se quiser permitir quebras internas |

**Regenerar o PDF à mão, sem gastar API** (útil para maquetar offline): a última
edição já está salva em JSON (`output/dados_*.json`) — basta reler e chamar o
template:

```powershell
.venv\Scripts\python.exe -c "import json,glob; from modules.pdf_template import gerar_relatorio; d=json.load(open(sorted(glob.glob('output/dados_*.json'))[-1],encoding='utf-8')); gerar_relatorio(d, 'output/relatorio_teste.pdf')"
```

Edite o JSON (ou monte um à mão com o mesmo contrato — `data`, `edicao`,
`titulo_capa`, `subtitulo_capa`, `panorama_geral`, `tematicas[]` com
`nome/rotulo/destaque/artigos[]`, artigos com `titulo/resumo/fonte/data/confianca/link`)
e o PDF sai com as suas mudanças.

---

## 8. Agendamento diário (Windows Task Scheduler)

Crie um `rodar.ps1` junto do `main.py`:

```powershell
# rodar.ps1
Set-Location $PSScriptRoot
$OPENROUTER_API_KEY = (Get-Content -Raw .env 2>$null)  # ou defina via setx
& .\.venv\Scripts\python.exe main.py *>> rodar.log
```

E registre (ex.: 07:30):

```powershell
schtasks /Create /TN "VisaoGlobalBriefing" /SC DAILY /ST 07:30 ^
  /TR "powershell -ExecutionPolicy Bypass -File C:\caminho\pipeline_ri\rodar.ps1"
```

---

## 9. Segurança

- `client_secret*.json`, `gmail_token.json`, `.env`, `output/` e `data/` estão no
  `.gitignore` — nada de credenciais ou resultados pessoais sobe para o repositório.
- **Nunca** cole a chave OpenRouter ou o segredo OAuth em arquivos versionados.
- Se uma chave vazou (ex. apareceu num chat/print): **rotacione** imediatamente no
  painel da ferramenta (OpenRouter / Google Cloud Console) e gere nova credencial.

---

## 10. Testes de Qualidade (QA)

A suíte valida o artefato **PDF** do pipeline (integridade, seções críticas,
contagem de artigos) e o próprio relatório de testes. Padrão: rodada rápida e
mockada (sem rede); o run real do pipeline é opt-in.

```
.venv\Scripts\pip.exe install -r requirements.txt   # inclui pypdf/pytest/playwright
.venv\Scripts\playwright.exe install chromium        # navegador p/ fase visual (uma vez)
python run_tests.py                                  # fases 1 e 3 (mock + visual)
python run_tests.py --e2e                            # inclui o run REAL (--limit 2)
```

| Fase | O que faz | Artefato |
|---|---|---|
| 1 — Integridade (pypdf) | Gera um PDF via rota real do produto (`montar_dados` + template) com dados determinísticos e valida: PDF abre (≥4 páginas), capa com título da camada editorial, seções críticas ("Radar de tendências", "NARRATIVAS DIGITAIS", "Ficha Técnica da Edição"), e nº de artigos no PDF == nº no JSON de saída | `output/qa/report.html` |
| 2 — E2E (opt-in) | Roda `main.py --trends --youtube --limit 2 --no-email` de verdade e repete as mesmas asserções sobre o artefato do dia (requer OPENROUTER_API_KEY no ambiente; usa cache e faz chamadas) | `output/qa/report_e2e.html` |
| 3 — QA visual (Playwright) | Abre o `report.html` no Chromium headless, confere contagem `N passed` e ausência de falhas/erros, e tira a evidência em tela cheia | `output/qa/evidencia.png` |

Notas:
- A fase de mock não incrementa o contador de edições e não gasta API (o PDF
  de prova é construído com fixtures determinísticas).
- Para rodar tudo pelo pytest diretamente: `pytest tests -m "not e2e and not qa_report"`,
  depois `pytest tests/test_qa_report.py` (fase visual exige `report.html` já gerado).
- A evidência `evidencia.png` é gerada a cada execução — bom artefato para o
  portfólio/case study.

---

## 11. Solução de problemas

| Sintoma | Causa provável | Ação |
|---|---|---|
| `Error 400: redirect_uri_mismatch` no navegador | client Web sem o URI registrado | registrar `http://localhost:8080/` nas URIs de redirecionamento autorizados (ou usar client Desktop) |
| `Erro 403: access_denied` no consentimento | Gmail não está nos usuários de teste | Google Auth Platform → Público → Usuários de teste → adicionar o gmail alvo |
| `HttpError 403 ... accessNotConfigured` | Gmail API desabilitada no projeto | Biblioteca de APIs → Gmail API → Enable; aguardar ~1 min |
| Refresh token morre em 7 dias | app OAuth em "Testing" | Publicar app em **Production** (Google Auth Platform) |
| `punkt` (nltk) baixando na 1ª extração | newspaper3k primeira vez | normal; exige internet |
| HTTP 429 em modelos `:free` | cota do modelo gratuito | retry/backoff automático; reduza `--limit` ou troque para modelo pago |
| `400` sem retry na classificação | payload inválido (ex.: >255 opções) | revise `categorias` no config |
| `401` / `402` | chave inválida / sem crédito | confira `OPENROUTER_API_KEY` / saldo OpenRouter |
| Log `resumo inválido ... finish_reason=length` | teto de tokens menor que o raciocínio do modelo | suba `sumario.max_tokens` (seção 4) |
| PDF sai sem panorama/destaques na capa | camada editorial desativada ou falhou | rode com `editorial.motor: directo` para isolar o problema; o log traz o motivo |
| `robots.txt proíbe fetch da fonte X` | robots do site nega bots | use outra fonte ou deixe `ativo: false` |
| Rascunho some depois de dias | app em Testing (token expira em 7 dias) | Production ou refazer consentimento |
