import os
import functions_framework
from google.cloud import bigquery
import smtplib
from email.message import EmailMessage
from datetime import datetime

# --- CONFIGURAZIONI ---
EMAIL_INVIO = "meloniweb@gmail.com"
PASSWORD_APP = "ettilmazxyydvusy"  # Nota: usa Secret Manager per maggiore sicurezza
DESTINATARI = ["daniel.meloni@hrm.group", "meloniwebm@gmail.com"]
TABLE_LOG_ID = "analystack.analytics_517838177.pub_sub_alert"

def get_sql_query():
    """Legge la query SQL dal file locale nel repository."""
    sql_path = os.path.join(os.path.dirname(__file__), 'query', 'conteggio_tipi_click.sql')
    with open(sql_path, 'r') as f:
        return f.read()

@functions_framework.cloud_event
def send_email_alert(cloud_event):
    client = bigquery.Client()
    
    try:
        # 1. Recupero la query dal file .sql nel repo
        query_string = get_sql_query()
        
        # 2. Esecuzione query su BigQuery
        query_job = client.query(query_string)
        results = query_job.result()

        # 3. Analisi risultati e costruzione corpo mail
        testo_corpo = "⚠️TEST REPO⚠️ - Rilevato superamento soglia click:\n\n"
        count = 0
        for row in results:
            # Controllo soglie (adatta i nomi delle colonne se necessario)
            if row.click_boxe_home < 5 or row.click_risorsa < 5:
                if row.click_boxe_home < 5:
                    testo_corpo += f"- In data {row.event_date}: click_boxe_home = {row.click_boxe_home} click\n"
                if row.click_risorsa < 5:
                    testo_corpo += f"- In data {row.event_date}: click_risorsa = {row.click_risorsa} click\n"
                count += 1

        # 4. Invio Alert se sono stati trovati dati
        if count > 0:
            msg = EmailMessage()
            msg.set_content(testo_corpo)
            msg['Subject'] = f"ALERT GA4: {count} Soglie Superate"
            msg['From'] = "Alert BigQuery"
            msg['To'] = ", ".join(DESTINATARI)

            # Connessione SMTP Gmail
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(EMAIL_INVIO, PASSWORD_APP)
            server.send_message(msg)
            server.quit()
            print(f"Email inviata con successo per {count} righe.")

            # 5. Scrittura Log in BigQuery (Load Job per evitare errori di buffer)
            # Inseriamo direttamente lo stato finale desiderato
            rows_to_insert = [
                {
                    "data": datetime.now().strftime('%Y-%m-%d'),
                    "alert": "click_sotto_soglia",
                    "stato_di_invio": "inviato",
                    "fonte": "cloud_function_ok"
                }
            ]
            
            job_config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")
            job = client.load_table_from_json(rows_to_insert, TABLE_LOG_ID, job_config=job_config)
            job.result()  # Attende la conferma dell'inserimento
            print("Log salvato correttamente su BigQuery.")

        else:
            print("Nessun dato sotto soglia trovato. Nessun alert inviato.")
        
    except Exception as e:
        print(f"Errore durante l'esecuzione: {str(e)}")