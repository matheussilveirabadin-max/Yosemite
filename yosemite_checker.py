"""
Yosemite Campsite Availability Checker
======================================
Monitora cancelamentos em campgrounds do Yosemite via recreation.gov
e envia alerta por email (Gmail SMTP - gratuito).

Custo total: $0
- recreation.gov API: pública, sem autenticação
- Gmail SMTP: gratuito (App Password)
- GitHub Actions: gratuito (repo público)

Setup:
  pip install requests
  Configurar variáveis de ambiente (ver README abaixo)
"""

import os
import smtplib
import time
import json
import requests
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ─────────────────────────────────────────────
# CONFIGURAÇÃO — edite aqui ou use env vars
# ─────────────────────────────────────────────

# Campgrounds do Yosemite que deseja monitorar
# Comente/descomente conforme sua preferência
CAMPGROUNDS = {
    "Upper Pines":       232447,  # Valley — o mais popular
    "Lower Pines":       232450,  # Valley — próximo ao rio
    "North Pines":       232449,  # Valley — mais tranquilo
    # "Tuolumne Meadows": 232448,  # Subalpino — alta altitude
    # "Hodgdon Meadow":   232451,  # Entrada oeste (Big Oak Flat)
    # "Crane Flat":       232452,  # Entre Valley e Tuolumne
    # "Bridalveil Creek": 232454,  # Perto de Glacier Point
    # "Wawona":           232453,  # Sul — perto de Mariposa Grove
}

# Janela de datas para monitorar
CHECK_FROM   = os.environ.get("CHECK_FROM",   "2026-07-26")  # YYYY-MM-DD
CHECK_TO     = os.environ.get("CHECK_TO",     "2026-07-28")  # YYYY-MM-DD
MIN_NIGHTS   = int(os.environ.get("MIN_NIGHTS", "2"))         # mínimo de noites consecutivas

# Email — use variáveis de ambiente no GitHub Actions
EMAIL_FROM = os.environ.get("EMAIL_FROM")    # seu_email@gmail.com
EMAIL_PASS   = os.environ.get("EMAIL_PASS")    # Gmail App Password (não sua senha normal)
EMAIL_TO     = os.environ.get("EMAIL_TO")      # destino (pode ser o mesmo)

# Comportamento
ONLY_EMAIL_IF_FOUND = True   # True = só envia email se encontrar vaga (evita spam)
SLEEP_BETWEEN_REQS  = 1.2    # segundos entre requests (respeita ~1 req/s do rate limit)

# ─────────────────────────────────────────────
# CORE: Consulta a API do Recreation.gov
# ─────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

API_URL = "https://www.recreation.gov/api/camps/availability/campground/{camp_id}/month"


def fetch_month(camp_id: int, year: int, month: int) -> dict:
    """Busca disponibilidade de um campground para um mês específico."""
    start_date = f"{year}-{month:02d}-01T00:00:00.000Z"
    url = API_URL.format(camp_id=camp_id)

    resp = requests.get(url, params={"start_date": start_date}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def merge_months(camp_id: int, from_date: datetime, to_date: datetime) -> dict:
    """Consolida dados de múltiplos meses em um único dict de campsites."""
    merged: dict = {}

    # Identifica quais meses cobrir
    months = set()
    cur = from_date.replace(day=1)
    while cur <= to_date:
        months.add((cur.year, cur.month))
        cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)

    for (yr, mo) in sorted(months):
        try:
            data = fetch_month(camp_id, yr, mo)
            for site_id, site in data.get("campsites", {}).items():
                if site_id not in merged:
                    merged[site_id] = {
                        "site":           site.get("site", site_id),
                        "loop":           site.get("loop", ""),
                        "type":           site.get("campsite_type", ""),
                        "availabilities": {}
                    }
                merged[site_id]["availabilities"].update(site.get("availabilities", {}))
            time.sleep(SLEEP_BETWEEN_REQS)
        except Exception as e:
            print(f"  ⚠️  Erro ao buscar {yr}-{mo:02d}: {e}")

    return merged


# ─────────────────────────────────────────────
# ANÁLISE: Janelas de disponibilidade
# ─────────────────────────────────────────────

def find_windows(campsites: dict, from_date: datetime, to_date: datetime, min_nights: int) -> list:
    """
    Retorna lista de sites com janelas de datas consecutivas disponíveis.
    Filtra pela janela definida e pelo mínimo de noites.
    """
    results = []

    for site_id, site in campsites.items():
        avail = site["availabilities"]

        # Coleta datas disponíveis na janela
        available_dates = []
        cur = from_date
        while cur <= to_date:
            key = cur.strftime("%Y-%m-%dT00:00:00Z")
            if avail.get(key) == "Available":
                available_dates.append(cur)
            cur += timedelta(days=1)

        if len(available_dates) < min_nights:
            continue

        # Agrupa em janelas consecutivas
        windows = []
        if available_dates:
            start = available_dates[0]
            end   = available_dates[0]
            for d in available_dates[1:]:
                if (d - end).days == 1:
                    end = d
                else:
                    nights = (end - start).days + 1
                    if nights >= min_nights:
                        windows.append((start, end, nights))
                    start = d
                    end   = d
            nights = (end - start).days + 1
            if nights >= min_nights:
                windows.append((start, end, nights))

        if windows:
            results.append({
                "site_id": site_id,
                "site":    site["site"],
                "loop":    site["loop"],
                "type":    site["type"],
                "windows": windows,
            })

    return results


# ─────────────────────────────────────────────
# NOTIFICAÇÃO: Email via Gmail SMTP (gratuito)
# ─────────────────────────────────────────────

def build_html_email(all_results: dict, from_str: str, to_str: str, min_nights: int) -> str:
    """Monta o corpo HTML do email de alerta."""

    total_found = sum(len(v) for v in all_results.values())
    status_icon = "🏕️" if total_found > 0 else "❌"
    checked_at  = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    rows = ""
    for camp_name, sites in all_results.items():
        camp_id = CAMPGROUNDS[camp_name]
        booking_url = f"https://www.recreation.gov/camping/campgrounds/{camp_id}"

        if sites:
            for s in sites:
                for (start, end, nights) in s["windows"]:
                    rows += f"""
                    <tr style="background:#f0fdf4;">
                      <td style="padding:8px 12px;border-bottom:1px solid #d1fae5;">✅ {camp_name}</td>
                      <td style="padding:8px 12px;border-bottom:1px solid #d1fae5;">{s['site']} ({s['loop']})</td>
                      <td style="padding:8px 12px;border-bottom:1px solid #d1fae5;">{s['type']}</td>
                      <td style="padding:8px 12px;border-bottom:1px solid #d1fae5;">
                        {start.strftime('%b %d')} → {end.strftime('%b %d, %Y')}
                      </td>
                      <td style="padding:8px 12px;border-bottom:1px solid #d1fae5;">{nights} noites</td>
                      <td style="padding:8px 12px;border-bottom:1px solid #d1fae5;">
                        <a href="{booking_url}" style="background:#16a34a;color:#fff;padding:4px 10px;
                           border-radius:4px;text-decoration:none;font-weight:bold;">
                          Reservar →
                        </a>
                      </td>
                    </tr>"""
        else:
            rows += f"""
            <tr>
              <td colspan="6" style="padding:8px 12px;border-bottom:1px solid #e5e7eb;
                color:#6b7280;">❌ {camp_name} — sem disponibilidade</td>
            </tr>"""

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px;">
      <div style="background:#15803d;color:white;padding:20px;border-radius:8px 8px 0 0;">
        <h1 style="margin:0;font-size:22px;">{status_icon} Yosemite Campsite Alert</h1>
        <p style="margin:4px 0 0;">Janela: <b>{from_str} → {to_str}</b>
           | Mínimo: <b>{min_nights} noites</b>
           | Sites encontrados: <b>{total_found}</b></p>
        <p style="margin:4px 0 0;font-size:12px;opacity:0.8;">Verificado em: {checked_at}</p>
      </div>

      <table style="width:100%;border-collapse:collapse;margin-top:0;">
        <thead>
          <tr style="background:#166534;color:white;">
            <th style="padding:10px 12px;text-align:left;">Campground</th>
            <th style="padding:10px 12px;text-align:left;">Site</th>
            <th style="padding:10px 12px;text-align:left;">Tipo</th>
            <th style="padding:10px 12px;text-align:left;">Datas</th>
            <th style="padding:10px 12px;text-align:left;">Noites</th>
            <th style="padding:10px 12px;text-align:left;">Link</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>

      <div style="margin-top:16px;padding:12px;background:#f9fafb;border-radius:4px;
          font-size:12px;color:#6b7280;">
        ⚡ Reservas em parques populares somem em segundos após a abertura.
        Acesse o link imediatamente e conclua a reserva no site do Recreation.gov.<br>
        🤖 Este alerta foi gerado automaticamente — custo $0 (Gmail SMTP + GitHub Actions)
      </div>
    </body>
    </html>
    """


def send_email(subject: str, html_body: str):
    """Envia email via Gmail SMTP (gratuito com App Password)."""
    if not all([EMAIL_FROM, EMAIL_PASS, EMAIL_TO]):
        print("⚠️  Credenciais de email não configuradas. Pulando envio.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print(f"✅ Email enviado para {EMAIL_TO}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    from_dt = datetime.strptime(CHECK_FROM, "%Y-%m-%d")
    to_dt   = datetime.strptime(CHECK_TO,   "%Y-%m-%d")

    print(f"\n🏕️  Yosemite Campsite Checker")
    print(f"   Janela : {CHECK_FROM} → {CHECK_TO}")
    print(f"   Noites mínimas: {MIN_NIGHTS}")
    print(f"   Campgrounds: {list(CAMPGROUNDS.keys())}")
    print("-" * 50)

    all_results: dict = {}
    total_found = 0

    for camp_name, camp_id in CAMPGROUNDS.items():
        print(f"\n🔍 Verificando: {camp_name} (ID: {camp_id})")
        campsites = merge_months(camp_id, from_dt, to_dt)
        sites     = find_windows(campsites, from_dt, to_dt, MIN_NIGHTS)
        all_results[camp_name] = sites
        total_found += len(sites)

        if sites:
            print(f"  ✅ {len(sites)} site(s) com janela disponível:")
            for s in sites:
                for (start, end, nights) in s["windows"]:
                    print(f"     Site {s['site']} | {s['loop']} | "
                          f"{start.strftime('%Y-%m-%d')} → {end.strftime('%Y-%m-%d')} "
                          f"({nights} noites)")
        else:
            print(f"  ❌ Sem disponibilidade")

    print(f"\n{'─'*50}")
    print(f"Total de janelas encontradas: {total_found}")

    # Envio de email
    if total_found > 0 or not ONLY_EMAIL_IF_FOUND:
        subject = (
            f"🏕️ Yosemite: {total_found} vaga(s) disponível! "
            f"[{CHECK_FROM} → {CHECK_TO}]"
            if total_found > 0
            else f"❌ Yosemite: sem vagas [{CHECK_FROM} → {CHECK_TO}]"
        )
        html = build_html_email(all_results, CHECK_FROM, CHECK_TO, MIN_NIGHTS)
        send_email(subject, html)
    else:
        print("📭 Nenhuma vaga encontrada — email não enviado.")

    # Output JSON para debug/logs do GitHub Actions
    summary = {k: len(v) for k, v in all_results.items()}
    print(f"\nResumo JSON: {json.dumps(summary)}")


if __name__ == "__main__":
    main()
