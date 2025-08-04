#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# permet de lire et d'enregistrer les messages MQTT des topics solar_power_regulator/run et solar_power_regulator/run
# ces messages speuvent être envoyés par 
#  . le démon solar_power_regulator.py en fonctionnement normal
#  . le script shelly MQTT_speed.js pour faire des tests 
# il enregistre les messages dans solar_power_regulator_run.csv et solar_power_regulator_evt.csv

import argparse
import logging
import json
import csv
import os
from datetime import datetime
import paho.mqtt.client as mqtt

# =================================================================================
# --- CONFIGURATION ---
# =================================================================================

# --- Paramètres de connexion MQTT par défaut ---
# (IP/hostname, port, user, password, 1 si SSL/TLS sinon 0)
# Le user et le password peuvent être surchargés par les arguments de la ligne de commande.
MQTT_CONN = ("localhost", 1883, "user", "password", 0)

# --- Topic MQTT racine ---
MQTT_ROOT_TOPIC = "solar_power_regulator"

# --- Configuration CSV ---
# Séparateur de colonnes pour les fichiers CSV
CSV_SEP = ";"
# Fichier pour les données de fonctionnement (topic /run). Laisser vide pour désactiver.
# Peut être surchargé en ligne de commande
FILE_CSV_INFOS = "solar_power_regulator_run.csv"
# Fichier pour les événements (topic /evt). Laisser vide pour désactiver.
# Peut être surchargé en ligne de commande
FILE_CSV_EVT = "solar_power_regulator_evt.csv"

# =================================================================================
# --- LOGIQUE DU CLIENT ---
# =================================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def on_connect(client, userdata, flags, rc, properties):
    """Callback exécuté lors de la connexion au broker."""
    if rc == 0:
        logging.info("Connecté au broker MQTT.")
        run_topic = f"{MQTT_ROOT_TOPIC}/run"
        evt_topic = f"{MQTT_ROOT_TOPIC}/evt"
        client.subscribe([(run_topic, 0), (evt_topic, 0)])
        logging.info(f"Abonné aux topics '{run_topic}' et '{evt_topic}'")
    else:
        logging.error(f"Echec de la connexion MQTT, code de retour: {rc}")

def on_message(client, userdata, msg):
    """Callback exécuté à la réception d'un message."""
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        # Traitement du topic /run
        if msg.topic == f"{MQTT_ROOT_TOPIC}/run":
            payload['conso'] = payload.get('solar') - payload.get('injection')
            if userdata['file_infos']:
                row = [
                    timestamp,
                    payload.get('solar', ''),
                    payload.get('injection', ''),
                    payload.get('conso', ''),
                    payload.get('power_limit', ''),
                    payload.get('delay', '')
                ]
                write_csv_row(userdata['file_infos'], row)
            if userdata['verbose']:
                logging.info(f"[RUN] Solar: {payload.get('solar')}W, Injection: {payload.get('injection')}W, Conso: {payload.get('conso')}W, Limite: {payload.get('power_limit')}%")

        # Traitement du topic /evt
        elif msg.topic == f"{MQTT_ROOT_TOPIC}/evt":
            logging.info(f"[EVT] Code: {payload.get('code')}, Msg: {payload.get('msg')}")
            if userdata['file_evt']:
                row = [
                    timestamp,
                    payload.get('code', ''),
                    payload.get('msg', '')
                ]
                write_csv_row(userdata['file_evt'], row)
                #write_csv_row(userdata['file_infos'], row)

    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"Erreur lors du traitement du message MQTT: {e}")

def write_csv_row(filepath, row, first_line = False):
    """Ecrit une ligne dans un fichier CSV."""
    try:
        mode = 'w' if first_line else 'a'
        with open(filepath, mode, newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=CSV_SEP)
            writer.writerow(row)
    except IOError as e:
        logging.error(f"Impossible d'écrire dans le fichier {filepath}: {e}")

def prepare_csv_file(filepath, header):
    """Crée le fichier CSV avec son en-tête s'il n'existe pas."""
    if not os.path.exists(filepath):
        logging.info(f"Création du fichier CSV: {filepath}")
    write_csv_row(filepath, header, True)

def parse_arguments():
    """Analyse les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(description="Client MQTT pour le démon de régulation solaire.")
    parser.add_argument('--file_infos', default=FILE_CSV_INFOS, help=f"Fichier CSV pour les données de fonctionnement (défaut: {FILE_CSV_INFOS}).")
    parser.add_argument('--file_evt', default=FILE_CSV_EVT, help=f"Fichier CSV pour les événements (défaut: {FILE_CSV_EVT}).")
    parser.add_argument('-u', '--user', type=str, help="Compte de connexion MQTT. Surcharge la configuration.")
    parser.add_argument('-p', '--password', type=str, help="Mot de passe MQTT. Surcharge la configuration.")
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Affiche les données de production en stdout.")
    return parser.parse_args()

def main():
    """Point d'entrée principal du client MQTT."""
    args = parse_arguments()

    if args.file_infos:
        logging.info(f"Infos de production dans fichier {args.file_infos}")
        prepare_csv_file(args.file_infos, ['time', 'solar', 'injection', 'conso', 'power_limit', 'delay'])
    else:
        logging.info("Infos de production pas enregistrés")
    if args.file_evt:
        logging.info(f"Evenements dans fichier {args.file_evt}")
        prepare_csv_file(args.file_evt, ['time', 'code', 'message'])
    else:
        logging.info("Infos d'évenement pas enregistrés")
        
    if not args.verbose:
        logging.info("Seules les infos d'évenement seront affichés dans le terminal. Pour avoir également les infos de production, il faut passer en argument '-v' ou '--verbose'")

    userdata = {
        'file_infos': args.file_infos,
        'file_evt': args.file_evt,
        'verbose': args.verbose
    }

    # --- LOGIQUE DE SURCHARGE DES IDENTIFIANTS ---
    host, port, user, password, use_tls = MQTT_CONN
    
    # Surcharge avec les arguments de la ligne de commande s'ils sont fournis
    if args.user is not None:
        user = args.user
    if args.password is not None:
        password = args.password
    # ----------------------------------------------

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata=userdata)
    client.on_connect = on_connect
    client.on_message = on_message
    
    if user:
        client.username_pw_set(user, password)
    
    if use_tls == 1:
        client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS, cert_reqs=mqtt.ssl.CERT_NONE)

    try:
        logging.info(f"Connexion à {host}:{port}...")
        client.connect(host, port, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        logging.info("Arrêt du client MQTT.")
    except Exception as e:
        logging.error(f"Une erreur critique est survenue: {e}")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()