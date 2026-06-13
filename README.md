# 🏕️ Yosemite Campsite Checker

Monitor cancelamentos em campgrounds do Yosemite via [Recreation.gov](https://recreation.gov)
e receba alertas por **email gratuito** (Gmail SMTP).

**Custo total: $0/mês**

---

## Como funciona

```
GitHub Actions (cron)
      │
      ▼
recreation.gov API  ──►  Compara disponibilidade
(pública, sem auth)        na sua janela de datas
                                │
                     vaga encontrada?
                      │              │
                     SIM            NÃO
                      │              │
               Gmail SMTP        sem email
               (gratuito)
```

---

## Setup em 5 minutos

### 1. Clone e configure o script

Edite as linhas de configuração em `yosemite_checker.py`:

```python
CAMPGROUNDS = {
    "Upper Pines":  232447,   # descomente os que quiser monitorar
    "Lower Pines":  232450,
    "North Pines":  232449,
}

CHECK_FROM  = "2025-08-01"  # início da janela
CHECK_TO    = "2025-08-15"  # fim da janela
MIN_NIGHTS  = 2              # mínimo de noites consecutivas
```

### 2. Gere um Gmail App Password

> ⚠️ Use App Password, não sua senha do Gmail

1. Acesse: [myaccount.google.com](https://myaccount.google.com)
2. Segurança → Verificação em duas etapas → Senhas de app
3. Selecione "Outro" → gere → copie os 16 caracteres

### 3. Publique no GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/SEU_USUARIO/yosemite-checker
git push -u origin main
```

> ⚠️ Mantenha o repo **público** para ter minutos gratuitos ilimitados no GitHub Actions

### 4. Configure Secrets e Variables no GitHub

Vá em **Settings → Secrets and variables → Actions**

**Secrets** (valores sensíveis):
| Secret | Valor |
|--------|-------|
| `EMAIL_FROM` | seu_email@gmail.com |
| `EMAIL_PASS` | App Password de 16 caracteres |
| `EMAIL_TO` | email destino (pode ser o mesmo) |

**Variables** (configurações):
| Variable | Exemplo |
|----------|---------|
| `CHECK_FROM` | 2025-08-01 |
| `CHECK_TO` | 2025-08-15 |
| `MIN_NIGHTS` | 2 |

### 5. Workflow do GitHub Actions

O workflow ja esta versionado em `.github/workflows/check.yml`.

### 6. Ative o workflow

- Vá em **Actions** no seu repo
- Clique em **"Yosemite Campsite Checker"**
- Clique em **"Run workflow"** para testar manualmente

---

## Campgrounds disponíveis no Yosemite

| Campground | ID | Localização |
|---|---|---|
| Upper Pines | 232447 | Valley — mais popular |
| Lower Pines | 232450 | Valley — à beira do rio |
| North Pines | 232449 | Valley — mais tranquilo |
| Tuolumne Meadows | 232448 | Subalpino, alta altitude |
| Hodgdon Meadow | 232451 | Entrada oeste |
| Crane Flat | 232452 | Entre Valley e Tuolumne |
| Bridalveil Creek | 232454 | Perto de Glacier Point |
| Wawona | 232453 | Sul, perto de Mariposa Grove |

---

## Comparativo de custo

| Solução | Custo/mês | Frequência | Notificação |
|---------|-----------|------------|-------------|
| **Este script** | **$0** | 15 min | Email |
| Campnab pay-per-use | $10–20/uso | 5–60 min | SMS |
| Campnab membership | $10–50/mês | 5–60 min | SMS |

---

## Teste local

```bash
pip install requests

# Com email
EMAIL_FROM=seu@gmail.com \
EMAIL_PASS=xxxx_xxxx_xxxx \
EMAIL_TO=destino@gmail.com \
CHECK_FROM=2025-08-01 \
CHECK_TO=2025-08-10 \
MIN_NIGHTS=2 \
python yosemite_checker.py

# Sem email (só logs no terminal)
CHECK_FROM=2025-08-01 CHECK_TO=2025-08-10 MIN_NIGHTS=2 python yosemite_checker.py
```

---

## Notas importantes

- A API do Recreation.gov é **pública e gratuita**, sem necessidade de chave
- Spots em parques populares somem em **segundos** — aja rápido ao receber o alerta
- Este script **não faz reservas** — você ainda precisa completar no site
- GitHub Actions em repos públicos tem **minutos ilimitados gratuitos**
- Se o repo ficar inativo por 60 dias, o GitHub pode pausar o cron — basta reativar manualmente
