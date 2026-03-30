import yfinance as yf
import pandas as pd
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import subprocess
import pytz

# ------------------------------------------------------
# Funktionen Import von weiterem Skript
# ------------------------------------------------------
from core_magic_3 import (
    lade_aktien,
    lade_daten_aktie,
    berechne_indikatoren,
    lade_fundamentaldaten,
    klassifiziere_aktie,
    erklaere_kategorien
)

from signals_2 import (
    fundamental_analyse,
    RSI_signal, 
    macd_signal, 
    adx_signal, 
    stochastic_signal, 
    bollinger_signal,
    kombiniertes_signal,
    analyse_kaufsignal_perioden,
    lade_analystenbewertung,
    berechne_rating_bar,
    zeichne_rating_gauge
)

from streamlit_visualization_9 import (
    go_to,
    home_page,
    aktienseite,
    zeige_swingtrading_signal,
    zeige_swingtrading_signalauswertung,
    berechne_swingtrading_trefferquote
)

# ------------------------------------------------------
# Laden der Aktien aus Watchlist
# ------------------------------------------------------

def erstelle_uebersicht_email(aktienliste):
    ergebnisse = []
    max_period = "4y"

    Auswertung_Tage = 61
    Min_Veraenderung = 0.08 # 8%

    for aktie in aktienliste:
        name = aktie["name"]
        symbol = aktie["symbol"]
    # Beispiel: Daten laden (z.B. yfinance oder lokal)
        try:
            data_full = lade_daten_aktie(symbol, period=max_period)
            data_full = berechne_indikatoren(data_full)

            # Swingtrading-Signal berechnen
            signal, _, _ = kombiniertes_signal(data_full)  # deine Signal-Funktion
            
            trefferquote = berechne_swingtrading_trefferquote(
                data_full,
                Auswertung_Tage,
                Min_Veraenderung
            )
            ergebnisse.append({
                "Name": name,      # falls Name anders ist, hier anpassen
                "Symbol": symbol,    # oder z.B. ein Dict mit Namen/Symbol
                "Signal": signal,
                "Trefferquote": f"{trefferquote:.2f} %" if trefferquote is not None else "N/A"
                })
        except Exception as e:
            print(f"Fehler bei Aktie {symbol}: {e}")
            ergebnisse.append({
                "Name": name,
                "Symbol": symbol,
                "Signal": "Fehler beim Laden",
                "Trefferquote": "N/A"
            })

    return ergebnisse

def erzeuge_html_tabelle(ergebnisse):
    html = """
    <h2>🏷️ Swingtrading Signale Übersicht</h2>
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; font-family: Arial;">
        <thead style="background-color:#2E86C1; color: white;">
            <tr>
                <th>Aktie</th>
                <th>Symbol</th>
                <th>Swingtrading Signal</th>
                <th>Trefferquote (%)</th>
            </tr>
        </thead>
        <tbody>
    """
    for e in ergebnisse:
        farbe = "#098F3F" if "Kauf" in e["Signal"] or "Long" in e["Signal"] else "#D4EFDF"
        html += f"""
        <tr style="background-color:{farbe};">
            <td>{e['Name']}</td>
            <td>{e['Symbol']}</td>
            <td>{e['Signal']}</td>
            <td style="text-align:center;"><b>{e['Trefferquote']}</b></td>
        </tr>
        """
    html += "</tbody></table>"
    return html

def send_email(subject, html_body):
    sender = "mymichael.adolf@web.de"
    password = "H6PL52UHTMGTC4S2XHO7"
    #password = os.environ.get("LIJ22ZIUJO6SEDKQUDORE")  # Passwort besser über Secrets sichern
    recipient = "mymichael.adolf@web.de"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    # STARTTLS auf Port 587
    with smtplib.SMTP("smtp.web.de", 587) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

def main_email_report():
    aktienliste = lade_aktien()
    ergebnisse = erstelle_uebersicht_email(aktienliste)
    html = erzeuge_html_tabelle(ergebnisse)
    send_email("Kaufsignal Watchlist", html)

if __name__ == "__main__":
    main_email_report()