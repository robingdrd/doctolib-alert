#!/usr/bin/env python3
import urllib.request, urllib.error, json, smtplib, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date

VISIT_MOTIVE_IDS = "844309"
AGENDA_IDS = "379404"
PRACTICE_IDS = "356377"
EMAIL_DESTINATAIRE = os.environ.get("EMAIL_DESTINATAIRE", "")
EMAIL_EXPEDITEUR = os.environ.get("EMAIL_EXPEDITEUR", "")
EMAIL_MOT_DE_PASSE = os.environ.get("EMAIL_MOT_DE_PASSE", "")

def get_availabilities():
    url = ("https://www.doctolib.fr/availabilities.json?start_date=" + date.today().isoformat() +
           "&visit_motive_ids=" + VISIT_MOTIVE_IDS + "&agenda_ids=" + AGENDA_IDS +
           "&practice_ids=" + PRACTICE_IDS + "&telehealth=false")
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
               "Accept": "application/json", "Accept-Language": "fr-FR,fr;q=0.9",
               "Referer": "https://www.doctolib.fr/psychotherapeute/paris/maba-diarra",
               "X-Requested-With": "XMLHttpRequest"}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("Erreur : " + str(e))
        return None

def main():
    print("Verification des creneaux...")
    data = get_availabilities()
    if not data:
        raise Exception("Impossible de recuperer les donnees Doctolib")
    slots = [s for j in data.get("availabilities", []) for s in j.get("slots", [])]
    if not slots:
        print("Aucun creneau disponible.")
        return
    print(str(len(slots)) + " creneau(x) trouve(s) !")
    msg = MIMEMultipart()
    msg["Subject"] = "Creneau Doctolib disponible - Maba DIARRA"
    msg["From"] = EMAIL_EXPEDITEUR
    msg["To"] = EMAIL_DESTINATAIRE
    msg.attach(MIMEText("\n".join(["- " + s for s in slots[:15]]) +
               "\n\nReserver : https://www.doctolib.fr/psychotherapeute/paris/maba-diarra", "plain", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
        smtp.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, msg.as_string())
    print("Email envoye !")

if __name__ == "__main__":
    main()
