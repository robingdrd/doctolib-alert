#!/usr/bin/env python3
import urllib.request, urllib.error, json, smtplib, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, datetime
from collections import defaultdict
from pathlib import Path

# --- Configuration ---
MODE_TEST = False
VISIT_MOTIVE_IDS = "844309"
AGENDA_IDS = "379404"
PRACTICE_IDS = "356377"
PRATICIEN = "Maba DIARRA"
URL_DOCTOLIB = "https://www.doctolib.fr/psychotherapeute/paris/maba-diarra"
EMAIL_DESTINATAIRE = os.environ.get("EMAIL_DESTINATAIRE", "")
EMAIL_EXPEDITEUR = os.environ.get("EMAIL_EXPEDITEUR", "")
EMAIL_MOT_DE_PASSE = os.environ.get("EMAIL_MOT_DE_PASSE", "")
NTFY_TOPIC = "robin-doctolib-alert"
SEEN_SLOTS_FILE = Path("seen_slots.json")

JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_FR = ["janvier", "fevrier", "mars", "avril", "mai", "juin",
           "juillet", "aout", "septembre", "octobre", "novembre", "decembre"]


def format_date_fr(dt):
    jour = JOURS_FR[dt.weekday()].capitalize()
    mois = MOIS_FR[dt.month - 1]
    return f"{jour} {dt.day} {mois} {dt.year}"


def format_heure(dt):
    return f"{dt.hour:02d}h{dt.minute:02d}"


def load_seen_slots():
    if SEEN_SLOTS_FILE.exists():
        try:
            return set(json.loads(SEEN_SLOTS_FILE.read_text()))
        except (json.JSONDecodeError, TypeError):
            pass
    return set()


def save_seen_slots(slots):
    today = date.today().isoformat()
    # Garder uniquement les creneaux futurs (>= aujourd'hui)
    clean = sorted(s for s in slots if s[:10] >= today)
    SEEN_SLOTS_FILE.write_text(json.dumps(clean))


def _fetch_page(start_date_str):
    url = (f"https://www.doctolib.fr/availabilities.json?start_date={start_date_str}"
           f"&visit_motive_ids={VISIT_MOTIVE_IDS}&agenda_ids={AGENDA_IDS}"
           f"&practice_ids={PRACTICE_IDS}&telehealth=false")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Referer": URL_DOCTOLIB,
        "X-Requested-With": "XMLHttpRequest",
    }
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as r:
        return json.loads(r.read().decode())


def get_availabilities():
    # L'API retourne ~2 jours par page et next_slot s'arrête dès qu'il trouve des slots,
    # manquant les créneaux plus lointains. On scanne donc par tranches de 14 jours
    # sur 4 mois, et on suit next_slot uniquement quand la page est vide.
    from datetime import timedelta
    all_slots = []
    seen_starts = set()
    today = date.today()
    horizon = today + timedelta(days=120)

    start = today
    try:
        while start <= horizon:
            start_str = start.isoformat()
            if start_str in seen_starts:
                start += timedelta(days=14)
                continue
            seen_starts.add(start_str)
            data = _fetch_page(start_str)
            page_slots = [s for day in data.get("availabilities", []) for s in day.get("slots", [])]
            all_slots.extend(page_slots)

            next_slot = data.get("next_slot")
            if not page_slots and next_slot:
                # Pas de slots ici, sauter directement au prochain créneau connu
                next_date = date.fromisoformat(next_slot[:10])
                start = next_date
            else:
                start += timedelta(days=14)
    except Exception as e:
        print(f"Erreur : {e}")
        return None
    return {"slots": all_slots}


def build_html(slots_by_day, is_new=True):
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
    title = "Nouveau(x) creneau(x)" if is_new else "Creneaux disponibles"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:480px;margin:0 auto;padding:16px;">
<h2 style="color:#2d3748;margin-bottom:4px;">{title} chez {PRATICIEN}</h2>
<p style="color:#718096;margin-top:0;">{total} nouveau(x) creneau(x)</p>
<table style="width:100%;border-collapse:collapse;">{rows}</table>
<br>
<a href="{URL_DOCTOLIB}" style="display:inline-block;background:#107ACA;color:white;padding:14px 28px;
   text-decoration:none;border-radius:8px;font-size:17px;font-weight:bold;">
   Reserver sur Doctolib
</a>
<p style="color:#a0aec0;font-size:12px;margin-top:24px;">Alerte automatique doctolib-alert</p>
</body></html>"""


def build_ntfy_text(slots_by_day):
    lines = []
    for day_str in sorted(slots_by_day):
        dt_day = datetime.fromisoformat(day_str)
        lines.append(format_date_fr(dt_day))
        for h in sorted(slots_by_day[day_str]):
            lines.append(f"  - {format_heure(h)}")
    return "\n".join(lines)


def send_ntfy(total, slots_text):
    data = f"{total} nouveau(x) creneau(x) chez {PRATICIEN}\n\n{slots_text}"
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=data.encode("utf-8"),
        headers={
            "Title": f"Doctolib - {total} creneau(x) !",
            "Priority": "urgent",
            "Tags": "calendar",
            "Click": URL_DOCTOLIB,
        },
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        print("Notification ntfy envoyee !")
    except Exception as e:
        print(f"Erreur ntfy : {e}")


def send_email(html, total):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Nouveau(x) creneau(x) ({total}) - {PRATICIEN}"
    msg["From"] = EMAIL_EXPEDITEUR
    msg["To"] = EMAIL_DESTINATAIRE
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
        smtp.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, msg.as_string())
    print("Email envoye !")


def main():
    if MODE_TEST:
        print("[MODE TEST] Envoi d'un email + ntfy de test...")
        fake_slots = {"2026-06-09": [datetime(2026, 6, 9, 14, 0), datetime(2026, 6, 9, 16, 30)],
                      "2026-06-10": [datetime(2026, 6, 10, 9, 0)]}
        html = build_html(fake_slots)
        send_email(html, 3)
        send_ntfy(3, build_ntfy_text(fake_slots))
        return

    print(f"Verification des creneaux chez {PRATICIEN}...")
    data = get_availabilities()
    if not data:
        print("Impossible de recuperer les donnees Doctolib. Nouvel essai au prochain cycle.")
        return

    # Collecter tous les creneaux actuels (comme strings ISO)
    all_current = set()
    slots_by_day = defaultdict(list)
    for s in data.get("slots", []):
        all_current.add(s)
        try:
            dt = datetime.fromisoformat(s)
            slots_by_day[dt.strftime("%Y-%m-%d")].append(dt)
        except (ValueError, TypeError):
            continue

    if not all_current:
        print("Aucun creneau disponible.")
        save_seen_slots(set())
        return

    # Comparer avec les creneaux deja vus
    seen = load_seen_slots()
    new_slots = all_current - seen
    print(f"{len(all_current)} creneau(x) au total, {len(new_slots)} nouveau(x).")

    # Sauvegarder tous les creneaux actuels comme "vus"
    save_seen_slots(all_current)

    if not new_slots:
        print("Pas de nouveau creneau depuis la derniere verification.")
        return

    # Construire l'email uniquement avec les nouveaux creneaux
    new_by_day = defaultdict(list)
    for s in new_slots:
        try:
            dt = datetime.fromisoformat(s)
            new_by_day[dt.strftime("%Y-%m-%d")].append(dt)
        except (ValueError, TypeError):
            continue

    html = build_html(new_by_day, is_new=True)
    send_email(html, len(new_slots))
    send_ntfy(len(new_slots), build_ntfy_text(new_by_day))


if __name__ == "__main__":
    main()
