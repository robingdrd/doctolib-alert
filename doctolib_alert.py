#!/usr/bin/env python3
"""
Doctolib Alert - Surveillance des créneaux de Mme Maba DIARRA
Envoie un email dès qu'un créneau se libère après 17h00
"""

import urllib.request
import urllib.error
import json
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date

# ─────────────────────────────────────────────
# CONFIGURATION — modifie ces valeurs
# ─────────────────────────────────────────────

# IDs Doctolib (ne pas modifier)
VISIT_MOTIVE_IDS = "844309"
AGENDA_IDS       = "379404"
PRACTICE_IDS     = "356377"

# Filtre horaire : alerter uniquement pour les créneaux APRÈS cette heure
HEURE_MIN = 17  # 17 = après 17h00

# Email de destination (ton email perso sur Android)
EMAIL_DESTINATAIRE = os.environ.get("EMAIL_DESTINATAIRE", "ton.email@gmail.com")

# Email expéditeur Gmail (crée un Gmail dédié ou utilise le tien)
EMAIL_EXPEDITEUR  = os.environ.get("EMAIL_EXPEDITEUR", "expediteur@gmail.com")
EMAIL_MOT_DE_PASSE = os.environ.get("EMAIL_MOT_DE_PASSE", "")  # App Password Gmail

# ─────────────────────────────────────────────
# LOGIQUE PRINCIPALE
# ─────────────────────────────────────────────

def get_availabilities():
    """Interroge l'API Doctolib et retourne les créneaux disponibles."""
    today = date.today().isoformat()
    url = (
        f"https://www.doctolib.fr/availabilities.json"
        f"?visit_motive_ids={VISIT_MOTIVE_IDS}"
        f"&agenda_ids={AGENDA_IDS}"
        f"&practice_ids={PRACTICE_IDS}"
        f"&telehealth=false"
        f"&start_date={today}"
        f"&limit=30"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "fr-FR,fr;q=0.9",
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as e:
        print(f"[{now()}] Erreur HTTP {e.code} : {e.reason}")
        return None
    except Exception as e:
        print(f"[{now()}] Erreur réseau : {e}")
        return None


def filtrer_creneaux_apres_17h(data):
    """Extrait uniquement les créneaux après HEURE_MIN."""
    creneaux_trouves = []

    if not data or "availabilities" not in data:
        return creneaux_trouves

    for jour in data["availabilities"]:
        slots = jour.get("slots", [])
        for slot in slots:
            # slot ressemble à "2026-05-04T17:30:00.000+02:00"
            try:
                heure = int(slot[11:13])
                if heure >= HEURE_MIN:
                    creneaux_trouves.append(slot)
            except Exception:
                continue

    return creneaux_trouves


def formater_creneau(slot):
    """Transforme "2026-05-04T17:30:00.000+02:00" en "Lundi 4 mai 2026 à 17h30"."""
    try:
        dt = datetime.fromisoformat(slot[:19])
        jours = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
        mois  = ["","janvier","février","mars","avril","mai","juin",
                 "juillet","août","septembre","octobre","novembre","décembre"]
        return f"{jours[dt.weekday()]} {dt.day} {mois[dt.month]} {dt.year} à {dt.hour}h{dt.minute:02d}"
    except Exception:
        return slot


def envoyer_email(creneaux):
    """Envoie un email de notification avec les créneaux trouvés."""
    if not EMAIL_MOT_DE_PASSE:
        print(f"[{now()}] ⚠️  Pas de mot de passe email configuré — affichage console uniquement")
        print(f"[{now()}] 🎉 CRÉNEAUX TROUVÉS après {HEURE_MIN}h :")
        for c in creneaux:
            print(f"   → {formater_creneau(c)}")
        return

    nb = len(creneaux)
    liste = "\n".join(f"• {formater_creneau(c)}" for c in creneaux)

    sujet = f"🗓️ Doctolib — {nb} créneau{'x' if nb > 1 else ''} après {HEURE_MIN}h chez Maba DIARRA"

    corps_html = f"""
    <div style="font-family:sans-serif;max-width:500px;margin:auto;padding:20px;">
      <h2 style="color:#1a73e8;">🗓️ Nouveau créneau disponible !</h2>
      <p>Un créneau après <strong>{HEURE_MIN}h00</strong> vient de se libérer
         chez <strong>Mme Maba DIARRA</strong> (Psychothérapeute, Paris).</p>
      <div style="background:#f0f7ff;border-left:4px solid #1a73e8;padding:12px;margin:16px 0;border-radius:4px;">
        {"<br>".join(f"• {formater_creneau(c)}" for c in creneaux)}
      </div>
      <a href="https://www.doctolib.fr/psychotherapeute/paris/maba-diarra"
         style="display:inline-block;background:#1a73e8;color:white;padding:12px 24px;
                border-radius:6px;text-decoration:none;font-weight:bold;">
        → Réserver sur Doctolib
      </a>
      <p style="color:#888;font-size:12px;margin-top:20px;">
        Alerte automatique — {now()}
      </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"]    = EMAIL_EXPEDITEUR
    msg["To"]      = EMAIL_DESTINATAIRE
    msg.attach(MIMEText(liste, "plain", "utf-8"))
    msg.attach(MIMEText(corps_html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
            server.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, msg.as_string())
        print(f"[{now()}] ✅ Email envoyé ! {nb} créneau(x) trouvé(s)")
    except Exception as e:
        print(f"[{now()}] ❌ Erreur envoi email : {e}")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    print(f"[{now()}] 🔍 Vérification des créneaux chez Mme Maba DIARRA (après {HEURE_MIN}h)...")

    data = get_availabilities()

    if data is None:
        print(f"[{now()}] ⚠️  Impossible de récupérer les données Doctolib")
        return

    # Vérifier si Doctolib signale "pas de dispo"
    if data.get("total", 1) == 0:
        print(f"[{now()}] 😴 Aucune disponibilité du tout pour le moment")
        return

    creneaux = filtrer_creneaux_apres_17h(data)

    if creneaux:
        print(f"[{now()}] 🎉 {len(creneaux)} créneau(x) après {HEURE_MIN}h trouvé(s) !")
        envoyer_email(creneaux)
    else:
        print(f"[{now()}] 😴 Aucun créneau après {HEURE_MIN}h — prochaine vérification dans 5 min")


if __name__ == "__main__":
    main()
