#!/usr/bin/env python3
import urllib.request, urllib.error, json, smtplib, os, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, datetime, timedelta
from collections import defaultdict
from pathlib import Path

# --- Configuration ---
MODE_TEST = False

PRATICIENS = [
    {
        "id": "diarra",
        "nom": "Maba DIARRA",
        "visit_motive_ids": "844309",
        "agenda_ids": "379404",
        "practice_ids": "356377",
        "url": "https://www.doctolib.fr/psychotherapeute/paris/maba-diarra",
    },
    {
        "id": "lamblin",
        "nom": "Benoit LAMBLIN",
        "visit_motive_ids": "878285",
        "agenda_ids": "148342",
        "practice_ids": "57418",
        "url": "https://www.doctolib.fr/orl-chirurgien-de-la-face-et-du-cou/paris/benoit-lamblin-paris",
    },
]

EMAIL_DESTINATAIRE = os.environ.get("EMAIL_DESTINATAIRE", "")
EMAIL_EXPEDITEUR = os.environ.get("EMAIL_EXPEDITEUR", "")
EMAIL_MOT_DE_PASSE = os.environ.get("EMAIL_MOT_DE_PASSE", "")
NTFY_TOPIC = "robin-doctolib-alert"

JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_FR = ["janvier", "fevrier", "mars", "avril", "mai", "juin",
           "juillet", "aout", "septembre", "octobre", "novembre", "decembre"]


def format_date_fr(dt):
    jour = JOURS_FR[dt.weekday()].capitalize()
    mois = MOIS_FR[dt.month - 1]
    return f"{jour} {dt.day} {mois} {dt.year}"


def format_heure(dt):
    return f"{dt.hour:02d}h{dt.minute:02d}"


def seen_slots_file(praticien):
    return Path(f"seen_slots_{praticien['id']}.json")


def load_seen_slots(praticien):
    f = seen_slots_file(praticien)
    if f.exists():
        try:
            return set(json.loads(f.read_text()))
        except (json.JSONDecodeError, TypeError):
            pass
    return set()


def save_seen_slots(praticien, slots):
    today = date.today().isoformat()
    # Garder uniquement les creneaux futurs (>= aujourd'hui)
    clean = sorted(s for s in slots if s[:10] >= today)
    seen_slots_file(praticien).write_text(json.dumps(clean))


def _fetch_page(praticien, start_date_str):
    url = (f"https://www.doctolib.fr/availabilities.json?start_date={start_date_str}"
           f"&visit_motive_ids={praticien['visit_motive_ids']}&agenda_ids={praticien['agenda_ids']}"
           f"&practice_ids={praticien['practice_ids']}&telehealth=false")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Referer": praticien["url"],
        "X-Requested-With": "XMLHttpRequest",
    }
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as r:
        return json.loads(r.read().decode())


def get_availabilities(praticien):
    # L'API renvoie ~2 jours par page. Quand la page contient des creneaux, on avance
    # juste apres le dernier jour renvoye (pas de saut fixe, sinon on saute des semaines
    # entieres avec des creneaux). Quand la page est vide, on suit next_slot pour sauter
    # au prochain creneau connu. Quand la page est vide ET next_slot est absent, l'agenda
    # ne contient plus aucune info sur le futur : on arrete le scan (continuer jour par
    # jour jusqu'a l'horizon ne ferait que spammer l'API pour rien).
    all_slots = []
    today = date.today()
    horizon = today + timedelta(days=365)

    start = today
    try:
        while start <= horizon:
            data = _fetch_page(praticien, start.isoformat())
            avail = data.get("availabilities", [])
            page_slots = [s for day in avail for s in day.get("slots", [])]
            all_slots.extend(page_slots)

            next_slot = data.get("next_slot")
            if page_slots:
                last_day = date.fromisoformat(avail[-1]["date"])
                start = last_day + timedelta(days=1)
            elif next_slot:
                start = date.fromisoformat(next_slot[:10])
            else:
                break
    except Exception as e:
        print(f"Erreur : {e}")
        return None
    return {"slots": all_slots}


def build_html(praticien, slots_by_day, is_new=True):
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
<h2 style="color:#2d3748;margin-bottom:4px;">{title} chez {praticien['nom']}</h2>
<p style="color:#718096;margin-top:0;">{total} nouveau(x) creneau(x)</p>
<table style="width:100%;border-collapse:collapse;">{rows}</table>
<br>
<a href="{praticien['url']}" style="display:inline-block;background:#107ACA;color:white;padding:14px 28px;
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


def send_ntfy(praticien, total, slots_text):
    data = f"{total} nouveau(x) creneau(x) chez {praticien['nom']}\n\n{slots_text}"
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=data.encode("utf-8"),
        headers={
            "Title": f"Doctolib - {total} creneau(x) !",
            "Priority": "urgent",
            "Tags": "calendar",
            "Click": praticien["url"],
        },
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        print("Notification ntfy envoyee !")
    except Exception as e:
        print(f"Erreur ntfy : {e}")


def send_email(praticien, html, total):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Nouveau(x) creneau(x) ({total}) - {praticien['nom']}"
    msg["From"] = EMAIL_EXPEDITEUR
    msg["To"] = EMAIL_DESTINATAIRE
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
        smtp.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, msg.as_string())
    print("Email envoye !")


def check_praticien(praticien):
    print(f"Verification des creneaux chez {praticien['nom']}...")
    data = get_availabilities(praticien)
    if not data:
        print(f"Impossible de recuperer les donnees Doctolib pour {praticien['nom']}. Nouvel essai au prochain cycle.")
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
        print(f"Aucun creneau disponible chez {praticien['nom']}.")
        save_seen_slots(praticien, set())
        return

    # Comparer avec les creneaux deja vus
    seen = load_seen_slots(praticien)
    new_slots = all_current - seen
    print(f"{praticien['nom']} : {len(all_current)} creneau(x) au total, {len(new_slots)} nouveau(x).")

    # Sauvegarder tous les creneaux actuels comme "vus"
    save_seen_slots(praticien, all_current)

    if not new_slots:
        print(f"Pas de nouveau creneau chez {praticien['nom']} depuis la derniere verification.")
        return

    # Construire l'email uniquement avec les nouveaux creneaux
    new_by_day = defaultdict(list)
    for s in new_slots:
        try:
            dt = datetime.fromisoformat(s)
            new_by_day[dt.strftime("%Y-%m-%d")].append(dt)
        except (ValueError, TypeError):
            continue

    html = build_html(praticien, new_by_day, is_new=True)
    send_email(praticien, html, len(new_slots))
    send_ntfy(praticien, len(new_slots), build_ntfy_text(new_by_day))


def main():
    if MODE_TEST:
        print("[MODE TEST] Envoi d'un email + ntfy de test pour chaque praticien...")
        for i, praticien in enumerate(PRATICIENS):
            fake_slots = {"2026-06-09": [datetime(2026, 6, 9, 14, 0), datetime(2026, 6, 9, 16, 30)],
                          "2026-06-10": [datetime(2026, 6, 10, 9, 0)]}
            html = build_html(praticien, fake_slots)
            send_email(praticien, html, 3)
            send_ntfy(praticien, 3, build_ntfy_text(fake_slots))
            if i < len(PRATICIENS) - 1:
                time.sleep(1)
        return

    for i, praticien in enumerate(PRATICIENS):
        try:
            check_praticien(praticien)
        except Exception as e:
            print(f"Erreur inattendue pour {praticien['nom']} : {e}")
        if i < len(PRATICIENS) - 1:
            time.sleep(1)


if __name__ == "__main__":
    main()
