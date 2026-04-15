#!/usr/bin/env python3
import urllib.request, urllib.error, json, smtplib, os, locale
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, datetime
from collections import defaultdict

# --- Configuration ---
MODE_TEST = True
VISIT_MOTIVE_IDS = "844309"
AGENDA_IDS = "379404"
PRACTICE_IDS = "356377"
PRATICIEN = "Maba DIARRA"
URL_DOCTOLIB = "https://www.doctolib.fr/psychotherapeute/paris/maba-diarra"
EMAIL_DESTINATAIRE = os.environ.get("EMAIL_DESTINATAIRE", "")
EMAIL_EXPEDITEUR = os.environ.get("EMAIL_EXPEDITEUR", "")
EMAIL_MOT_DE_PASSE = os.environ.get("EMAIL_MOT_DE_PASSE", "")

JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_FR = ["janvier", "fevrier", "mars", "avril", "mai", "juin",
           "juillet", "aout", "septembre", "octobre", "novembre", "decembre"]


def format_date_fr(dt):
    jour = JOURS_FR[dt.weekday()].capitalize()
    mois = MOIS_FR[dt.month - 1]
    return f"{jour} {dt.day} {mois} {dt.year}"


def format_heure(dt):
    return f"{dt.hour:02d}h{dt.minute:02d}"


def get_availabilities():
    url = (f"https://www.doctolib.fr/availabilities.json?start_date={date.today().isoformat()}"
           f"&visit_motive_ids={VISIT_MOTIVE_IDS}&agenda_ids={AGENDA_IDS}"
           f"&practice_ids={PRACTICE_IDS}&telehealth=false")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Referer": URL_DOCTOLIB,
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"Erreur : {e}")
        return None


def build_html(slots_by_day):
    rows = ""
    for day_str in sorted(slots_by_day):
        dt_day = datetime.fromisoformat(day_str)
        label = format_date_fr(dt_day)
        heures = "".join(
            f'<li style="padding:4px 0;font-size:16px;">{format_heure(h)}</li>'
            for h in sorted(slots_by_day[day_str])
        )
        rows += f"""
        <tr><td style="padding:12px 0 4px;font-weight:bold;font-size:17px;color:#2b6cb0;border-bottom:1px solid #e2e8f0;">
            {label}
        </td></tr>
        <tr><td><ul style="margin:4px 0 0 16px;padding:0;list-style:disc;">{heures}</ul></td></tr>"""

    total = sum(len(v) for v in slots_by_day.values())
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:480px;margin:0 auto;padding:16px;">
<h2 style="color:#2d3748;margin-bottom:4px;">Creneaux disponibles chez {PRATICIEN}</h2>
<p style="color:#718096;margin-top:0;">{total} creneau(x) trouve(s)</p>
<table style="width:100%;border-collapse:collapse;">{rows}</table>
<br>
<a href="{URL_DOCTOLIB}" style="display:inline-block;background:#107ACA;color:white;padding:14px 28px;
   text-decoration:none;border-radius:8px;font-size:17px;font-weight:bold;">
   Reserver sur Doctolib
</a>
<p style="color:#a0aec0;font-size:12px;margin-top:24px;">Alerte automatique doctolib-alert</p>
</body></html>"""


def send_email(html, total):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Creneaux disponibles ({total}) - {PRATICIEN}"
    msg["From"] = EMAIL_EXPEDITEUR
    msg["To"] = EMAIL_DESTINATAIRE
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
        smtp.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, msg.as_string())
    print("Email envoye !")


def main():
    if MODE_TEST:
        print("[MODE TEST] Envoi d'un email de test...")
        fake_slots = {"2026-06-09": [datetime(2026, 6, 9, 14, 0), datetime(2026, 6, 9, 16, 30)],
                      "2026-06-10": [datetime(2026, 6, 10, 9, 0)]}
        html = build_html(fake_slots)
        send_email(html, 3)
        return

    print(f"Verification des creneaux chez {PRATICIEN}...")
    data = get_availabilities()
    if not data:
        print("Impossible de recuperer les donnees Doctolib. Nouvel essai au prochain cycle.")
        return

    slots_by_day = defaultdict(list)
    for day in data.get("availabilities", []):
        for s in day.get("slots", []):
            try:
                dt = datetime.fromisoformat(s)
                slots_by_day[day["date"]].append(dt)
            except (ValueError, TypeError):
                continue

    if not slots_by_day:
        print("Aucun creneau disponible.")
        return

    total = sum(len(v) for v in slots_by_day.values())
    print(f"{total} creneau(x) trouve(s) !")
    html = build_html(slots_by_day)
    send_email(html, total)


if __name__ == "__main__":
    main()
