#!/usr/bin/env python3
import urllib.request
import urllib.error
import json
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date

VISIT_MOTIVE_IDS = "844309"
AGENDA_IDS       = "379404"
PRACTICE_IDS     = "356377"

EMAIL_DESTINATAIRE = os.environ.get("EMAIL_DESTINATAIRE", "")
EMAIL_EXPEDITEUR   = os.environ.get("EMAIL_EXPEDITEUR", "")
EMAIL_MOT_DE_PASSE = os.environ.get("EMAIL_MOT_DE_PASSE", "")

HEURE_MIN = 17

def get_availabilities():
    today = date.today().isoformat()
    url = (
        "https://www.doctolib.fr/availabilities.json"
        "?start_date=" + today +
        "&visit_motive_ids=" + VISIT_MOTIVE_IDS +
        "&agenda_ids=" + AGENDA_IDS +
        "&practice_ids=" + PRACTICE_IDS +
        "&telehealth=false"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Referer": "https://www.doctolib.fr/psychotherapeute/paris/maba-diarra",
        "X-Requested-With": "XMLHttpRequest",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print("Erreur HTTP " + str(e.code) + " : " + e.reason)
        return None
    except Exception as e:
        print("Erreur : " + str(e))
        return None

def filtrer_creneaux(data):
    creneaux = []
    if not data or "availabilities" not in data:
        return creneaux
    for jour in data["availabilities"]:
        for slot in jour.get("slots", []):
            try:
                dt = datetime.fromisoformat(slot.replace("Z", "+00:00"))
                if dt.hour >= HEURE_MIN:
                    creneaux.append(slot)
            except Exception:
                pass
    return creneaux

def envoyer_email(creneaux):
    liste = "\n".join(["- " + c for c in creneaux[:10]])
    url_rdv = "https://www.doctolib.fr/psychotherapeute/paris/maba-diarra"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Creneau Doctolib apres 17h - Maba DIARRA"
    msg["From"]    = EMAIL_EXPEDITEUR
    msg["To"]      = EMAIL_DESTINATAIRE
    texte = "Creneaux disponibles apres 17h :\n\n" + liste + "\n\nReserver : " + url_rdv
    msg.attach(MIMEText(texte, "plain", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
        smtp.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, msg.as_string())
    print("Email envoye : " + str(len(creneaux)) + " creneau(x)")

def main():
    print("Verification des creneaux apres " + str(HEURE_MIN) + "h...")
    data = get_availabilities()
    if data is None:
        print("Impossible de recuperer les donnees Doctolib")
        return
    creneaux = filtrer_creneaux(data)
    if creneaux:
        print(str(len(creneaux)) + " creneau(x) trouve(s) !")
        envoyer_email(creneaux)
    else:
        print("Aucun creneau apres 17h pour le moment.")

if __name__ == "__main__":
    main()
