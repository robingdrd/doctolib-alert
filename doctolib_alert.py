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


# MISE A JOUR: passer a False apres le test
MODE_TEST = False


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
