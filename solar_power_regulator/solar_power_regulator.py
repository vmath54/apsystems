#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import logging.handlers
import signal
import sys
import json
import time
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from threading import RLock, Thread
from collections import deque
from datetime import datetime

from pymodbus.client import ModbusTcpClient
import paho.mqtt.client as mqtt

# =================================================================================
# --- CONFIGURATION DU DÉMON ---
# =================================================================================

# --- Paramètre lié à l'installation solaire ---
# Puissance nominale totale de l'installation solaire en Watts (somme des puissances max des micro-onduleurs). Utile pour l'algo Fast Drop
# C'est la somme des puissance max des micro onduleurs de l'installation
TOTAL_RATED_SOLAR_POWER = 2640

# --- Gestion horaire ---
# Format: [("HH:MM", "HH:MM"), ...]
# Permet de définir des tranches horaires pour activer la limitation d'injection.
# Laisser la liste vide pour une régulation 24h/24.
REGULATION_WINDOWS = [("06:00", "22:00")]

# --- Paramètres Modbus ---
# Adresse IP de l'ECU-R. Peut être surchargé par la ligne de commande.
MODBUS_ECU_IP = "192.168.1.120"
# Port TCP Modbus de l'ECU-R.
MODBUS_ECU_PORT = 502
# ID de l'esclave Modbus à adresser.
MODBUS_SLAVE_ID = 1
# Numéro du registre Modbus pour le contrôle de la limite de puissance.
MODBUS_POWER_LIMIT_REGISTER = 40189
# Nombre d'échecs d'écriture Modbus successifs avant de passer en erreur récurrente.
MODBUS_RECURRENT_ERROR_COUNT = 5

# --- Paramètres de l'algorithme (en "pour mille") ---
# Limite de production minimale autorisée - power_limit (10 = 1.0%).
MIN_POWER_LIMIT_PERMILLE = 10
# Limite de production maximale autorisée - power_limit (1000 = 100.0%).
MAX_POWER_LIMIT_PERMILLE = 1000
# Valeur de bug de l'ECU-R à corriger (300 = 30.0%).
BUGGY_LIMIT_PERMILLE = 300

# --- Algorithme de régulation par seuils ---
# Le tri `reverse=True` est essentiel pour que l'algorithme fonctionne correctement.
INJECTION_POWER_THRESHOLDS = sorted([
# Seuil d'injection (en W),  Incrément du power_limit,  délai avant prochaine mesure. Si délai = -1, alors c'est la valeur par défaut du shelly
    (-99999, 200, 5),   # importation supérieure à  600W  -> On augmente power_limit de 20%, la prochaine mesure sera dans 5s
    (-600,   100, 5),   # importation entre 200W et 600W  -> On augmente power_limit de 10%, la prochaine mesure sera dans 5s
    (-200,    50, 5),   # importation entre 100W et 200W  -> On augmente power_limit de 5%, la prochaine mesure sera dans 5s
    (-100,    20, 5),   # importation entre 30W et 100W   -> On augmente power_limit de 2%, la prochaine mesure sera dans 5s
    (-30,     10,-1),   # importation entre 0W et 30W     -> On augmente power_limit de 1%, la prochaine mesure sera la valeur par défaut du shelly
    (0,        0,-1),   # !!! c'est la plage recherchée : injection entre 0W et 30W -> on ne fait rien, la prochaine mesure sera la valeur par défaut du shelly
    (30,      -5,-1),   # injection entre 30W et 60W      -> On diminue power_limit de 0.5%, la prochaine mesure sera la valeur par défaut du shelly
    (60,     -10, 5),   # injection entre 60W et 130W     -> On diminue power_limit de 1%, la prochaine mesure sera dans 5s
    (130,    -50, 5),   # injection entre 100W et 250W    -> On diminue power_limit de 5%, la prochaine mesure sera dans 5s
    (250,   -100, 5),   # injection entre 250W et 600W    -> On diminue power_limit de 10%, la prochaine mesure sera dans 5s
    (600,   -200, 5),   # injection supérieure à 600W     -> On diminue power_limit de 20%, la prochaine mesure sera dans 5s
], key=lambda x: x[0], reverse=True)


# --- Algorithmes avancés ---
# Nombre de requêtes en importation successives avant de forcer la production à 100%.
CONSECUTIVE_IMPORT_COUNT_FOR_RESET = 15

# Algorithme pour réduire rapidement la limite de puissance si elle est inutilement haute.
# Activer l'algorithme "Fast Drop" pour une meilleure réactivité. Il faut que l'information de production solaire (solar_power) soit transmise par le shelly
FAST_DROP_ALGORITHM_ENABLE = True

# (injection_sup_a, nb_fois_consecutives, si_limite_actuelle_sup_a, delay_next_request)
FAST_DROP_THRESHOLDS = (30, 2, 500, 10)  # déclenchement si, 2 fois consécutivement, il y a  injection supérieure à 30W 3 et un power_limit > 50.0%. La requete suivante du shelly interviendra dans 10 secondes.

# Algorithme pour augmenter rapidement la limite de puissance en cas de forte consommation.
# Activer l'algorithme "Fast Rise" pour une meilleure réactivité.
FAST_RISE_ALGORITHM_ENABLE = True

# (injection_inf_a, nb_fois_consecutives, nouvelle_limite, delay_next_request)
FAST_RISE_THRESHOLDS = (-800, 2, 1000, 10)  # si 2 fois consécutivement, injection inférieure à -1100W (donc importation supérieure à 1100W), on passe power_limit à 100.0% (la valeur 1000). La requete suivante du shelly interviendra dans 10 secondes.

# le nombre de requetes en régulation par seuil minimum avant de pouvoir appliquer un algo 'FAST', plus violent
# L'objectif est de ne pas enchainer des FAST_DROP, FAST_RISE, ... successifs
FAST_COOLDOWN_NB = 5


# --- Gestion des états et Watchdog ---
# Toutes les 15mn, lecture modbus de power_limit pour contrôle.
PERIODIC_READ_INTERVAL_S = 900
# Si pas d'infos du shelly depuis 1h, power_limit = 100%.
WATCHDOG_TIMEOUT_S = 3600
# Intervalle pour les tâches de fond (tranches horaires, etc.).
PERIODIC_TASK_INTERVAL_S = 60

# --- Paramètres MQTT ---
# 0 : Désactiver l'envoi d'informations MQTT. 1 : MQTT activé, pour tout. 2 : MQTT activé, mais juste pour les évènements
MQTT_ENABLE = 1

# les infos de connexion MQTT
#    le serveur - le port TCP - le compte de connexion - le mot de passe. 1 si SSL ou TLS
MQTT_CONN = ("localhost", 1883, "user", "password", 0)

# le topic MQTT racine pour cette fonction. Il y aura ensuite 2 sous-topics : /run pour les infos courantes, /evt pour les évenement
MQTT_ROOT_TOPIC = "solar_power_regulator"

#les codes évenements MQTT
MQTT_EVT_CODE = {
1:"REGULATION_WINDOWS_IN",     # entrée dans une tranche de régulation
2:"REGULATION_WINDOWS_OUT",    # sortie d'une tranche de régulation
3:"MODBUS_ERROR_START",        # erreur modbus. Il ne doit pas y avoir d'autres messages MQTT "MODBUS_ERROR_START" tant qu'il n'y a pas eu de "MODBUS_ERROR_STOP"
4:"MODBUS_ERROR_END",          # fin d'erreur modbus. Le démon a pu lire ou écrire power_limit en modbus
5:"POWER_LIMIT_30.0",          # power_limit lu a la valeur 30.0%. Le démon a forcé la valeur 100.0%
6:"POWER_LIMIT_DIFF",          # power_limit lu est différent du power_limit mémorisé
7:"FAST_DROP",                 # le démon applique l'algo FAST_DROP
8:"FAST_RISE",                 # le démon applique l'algo FAST_RISE
}

# =================================================================================
# --- CLASSES ET LOGIQUE INTERNE ---
# =================================================================================

class ReturnCode:
    """Codes de retour standardisés pour les réponses de l'API."""
    OK = (0, "OK"); DIFFERENT_POWER_LIMIT = (1, "Power-limit value read on device is different from stored value"); MODBUS_FAILURE = (2, "Modbus communication failed"); MODBUS_RECURRENT_FAILURE = (3, "Modbus recurrent communication failure"); OTHER_ERROR = (9, "An other error occurred")

class RegulationState:
    """Encapsule l'état dynamique de la régulation."""
    def __init__(self):
        self.current_power_limit_permille = -1
        self.last_modbus_read_time = 0
        self.consecutive_modbus_write_errors = 0
        self.last_shelly_request_time = time.time()
        self.watchdog_triggered = False
        self.was_in_regulation_window = self.is_in_regulation_window()
        self.consecutive_import_count = 0
        self.consecutive_high_injection_count = 0
        self.consecutive_deep_import_count = 0
        self.fast_cooldown = 0
        self.last_run_payload = ""

    def is_in_regulation_window(self):
        """Vérifie si l'heure actuelle est dans une des fenêtres de régulation."""
        if not REGULATION_WINDOWS: return True
        now = datetime.now().time()
        for start_str, end_str in REGULATION_WINDOWS:
            start_time, end_time = datetime.strptime(start_str, "%H:%M").time(), datetime.strptime(end_str, "%H:%M").time()
            if start_time <= end_time:
                if start_time <= now <= end_time: return True
            else:
                if start_time <= now or now <= end_time: return True
        return False

class ModbusController:
    """Gère la communication Modbus avec l'ECU-R."""
    def __init__(self, host, port, slave_id):
        self.host, self.port, self.slave_id, self.lock = host, port, slave_id, RLock()
    def _execute_transaction(self, action_func):
        with self.lock:
            try:
                client = ModbusTcpClient(self.host, port=self.port, timeout=10)
                if not client.connect(): return None, "CONNECTION_ERROR"
                result = action_func(client)
                return (result, "OK") if not result.isError() else (None, "MODBUS_EXECUTION_ERROR")
            except Exception: return None, "COMMUNICATION_ERROR"
            finally:
                if 'client' in locals() and client.is_socket_open(): client.close()
    def read_power_limit(self):
        """Lit la valeur brute du registre."""
        def action(client): return client.read_holding_registers(address=MODBUS_POWER_LIMIT_REGISTER, count=1, slave=self.slave_id)
        result, status = self._execute_transaction(action)
        return (result.registers[0], status) if status == "OK" else (None, status)
    def write_power_limit(self, value_permille):
        """Ecrit la valeur brute dans le registre."""
        def action(client): return client.write_registers(address=MODBUS_POWER_LIMIT_REGISTER, values=[value_permille], slave=self.slave_id)
        _, status = self._execute_transaction(action)
        return status

class MQTTController:
    """Gère la connexion et la publication des messages MQTT."""
    def __init__(self):
        self.client = None; self.is_connected = False; self.lock = RLock()
    def _connect(self):
        with self.lock:
            if self.is_connected: return
            try:
                host, port, user, password, use_tls = MQTT_CONN
                self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
                self.client.on_disconnect = lambda client, userdata, flags, rc, properties: self.on_disconnect()
                self.client.username_pw_set(user, password)
                if use_tls == 1:
                    self.client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS, cert_reqs=mqtt.ssl.CERT_NONE)
                self.client.connect(host, port, 60)
                self.client.loop_start()
                self.is_connected = True
                logging.info(f"Connexion MQTT à {host}:{port} établie.")
            except Exception as e:
                logging.error(f"Echec de la connexion MQTT: {e}")
                self.is_connected = False
    def on_disconnect(self):
        with self.lock: self.is_connected = False
        logging.warning("Connexion MQTT perdue. Tentative de reconnexion en cours...")
    def publish(self, topic_suffix, payload):
        if MQTT_ENABLE == 0: return
        with self.lock:
            if not self.is_connected: self._connect()
            if not self.is_connected: return
            try:
                topic = f"{MQTT_ROOT_TOPIC}/{topic_suffix}"
                self.client.publish(topic, json.dumps(payload), qos=0)
            except Exception as e:
                logging.error(f"Echec de la publication MQTT sur le topic {topic}: {e}"); self.is_connected = False

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Serveur HTTP qui gère chaque requête dans un thread séparé."""
    pass

class QuietRequestHandler(BaseHTTPRequestHandler):
    """RequestHandler qui supprime les logs HTTP standards."""
    def log_message(self, format, *args):
        return

class RequestHandler(QuietRequestHandler):
    """Gère les requêtes HTTP entrantes du Shelly."""
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            params = json.loads(post_data)
            injection_power = params['injection_power']
            solar_power = params['solar_power']
        except (json.JSONDecodeError, KeyError) as e:
            logging.error(f"Invalid JSON or missing key: {e}")
            self.send_json_response(400, {"message": str(e)})
            return

        with state_lock:
            state.last_shelly_request_time = time.time()
            if state.watchdog_triggered:
                logging.warning("Communication avec le Shelly rétablie.")
                state.watchdog_triggered = False

            return_code_tuple = ReturnCode.OK
            if state.current_power_limit_permille == -1:
                return_code_tuple, _ = handle_state_and_reads()

            if not state.is_in_regulation_window():
                self.send_response_and_exit(ReturnCode.OK, state.current_power_limit_permille, 0, PERIODIC_TASK_INTERVAL_S)
                return

            if return_code_tuple not in [ReturnCode.OK, ReturnCode.DIFFERENT_POWER_LIMIT]:
                self.send_response_and_exit(return_code_tuple, -1, 0, -1)
                return

            new_limit, increment, threshold_info, next_interval = calculate_new_limit(injection_power, solar_power)

            log_msg = f"Solar={solar_power}W, Injection={injection_power}W. Seuil=\"{threshold_info}\". "
            delay_str = "default" if next_interval == -1 else f"{next_interval}s"
            if increment != 0:
                log_msg += f"Incrément={increment/10.0:.1f}%. Limite: {state.current_power_limit_permille/10.0:.1f}% -> {new_limit/10.0:.1f}%. Delay={delay_str}."
            else:
                log_msg += f"Pas de changement. Limite: {new_limit/10.0:.1f}%. Delay={delay_str}."
            logging.debug(log_msg)

            if MQTT_ENABLE == 1:
                run_payload = {"solar": solar_power, "injection": injection_power, "power_limit": new_limit / 10.0, "delay": next_interval}
                if json.dumps(run_payload) != state.last_run_payload:
                    mqtt_controller.publish("run", run_payload); state.last_run_payload = json.dumps(run_payload)
            if new_limit != state.current_power_limit_permille:
                if perform_write(new_limit) != "OK":
                     self.send_response_and_exit(ReturnCode.MODBUS_FAILURE, state.current_power_limit_permille, 0, -1)
                     return

            self.send_response_and_exit(return_code_tuple, state.current_power_limit_permille, increment, next_interval)

    def send_json_response(self, http_code, data):
        self.send_response(http_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_response_and_exit(self, return_code_tuple, limit, increment, interval):
        response_payload = { "return_code": return_code_tuple[0], "message": return_code_tuple[1], "power_limit_value": limit, "power_limit_increment": increment, "sensor_read_interval": interval, }
        self.send_json_response(200, response_payload)

# --- Fonctions de service ---
state = RegulationState()
state_lock = RLock()
modbus_controller = None
mqtt_controller = MQTTController()

def handle_state_and_reads():
    """Effectue une lecture Modbus et met à jour l'état."""
    logging.debug("Vérification de l'état Modbus...")
    read_value, status = modbus_controller.read_power_limit()
    if status != "OK":
        if state.consecutive_modbus_write_errors == 0:
            mqtt_controller.publish("evt", {"code": 3, "msg": MQTT_EVT_CODE[3]})
        state.consecutive_modbus_write_errors += 1
        if state.consecutive_modbus_write_errors >= MODBUS_RECURRENT_ERROR_COUNT: return ReturnCode.MODBUS_RECURRENT_FAILURE, None
        return ReturnCode.MODBUS_FAILURE, None
    
    if state.consecutive_modbus_write_errors > 0:
        mqtt_controller.publish("evt", {"code": 4, "msg": MQTT_EVT_CODE[4]})
    state.last_modbus_read_time = time.time()
    if read_value == BUGGY_LIMIT_PERMILLE:
        logging.warning(f"Valeur lue de {BUGGY_LIMIT_PERMILLE/10.0:.1f}% détectée, correction à {MAX_POWER_LIMIT_PERMILLE/10.0:.1f}%.")
        mqtt_controller.publish("evt", {"code": 5, "msg": f"{MQTT_EVT_CODE[5]}. Passage forcé à 100.0%"})
        perform_write(MAX_POWER_LIMIT_PERMILLE)
        read_value = MAX_POWER_LIMIT_PERMILLE
        
    return_code = ReturnCode.OK
    if state.current_power_limit_permille != -1 and read_value != state.current_power_limit_permille:
        logging.warning(f"Divergence de power_limit. Mémorisé={state.current_power_limit_permille/10.0:.1f}%, Lu={read_value/10.0:.1f}%.")
        mqtt_controller.publish("evt", {"code": 6, "msg": f"{MQTT_EVT_CODE[6]}. Read={read_value/10.0:.1f}%, Mem={state.current_power_limit_permille/10.0:.1f}%"})
        return_code = ReturnCode.DIFFERENT_POWER_LIMIT

    state.current_power_limit_permille = read_value
    return return_code, read_value

def calculate_new_limit(injection_power, solar_power):
    """Calcule la nouvelle limite de puissance en appliquant les différents algorithmes."""
    last_limit = state.current_power_limit_permille
    if last_limit == -1: return -1, 0, "État inconnu", -1

    # Gestion du cooldown
    if state.fast_cooldown > 0: state.fast_cooldown -=1

    # --- ALGO 1: FAST RISE ---
    if FAST_RISE_ALGORITHM_ENABLE:
        rise_thresh, rise_count, rise_limit, drop_next_delay = FAST_RISE_THRESHOLDS
        if injection_power < rise_thresh:
            state.consecutive_deep_import_count += 1
        else:
            state.consecutive_deep_import_count = 0

        if state.consecutive_deep_import_count >= rise_count and state.fast_cooldown == 0:
            if last_limit < rise_limit:
                logging.info(f"FAST RISE: Importation forte détectée. Passage de {last_limit/10.0:.1f}% à {rise_limit/10.0:.1f}%.")
                state.fast_cooldown = FAST_COOLDOWN_NB
                state.consecutive_deep_import_count = 0
                mqtt_controller.publish("evt", {"code": 8, "msg": f"{MQTT_EVT_CODE[8]}. De {last_limit/10.0:.1f}% à {rise_limit/10.0:.1f}%. Solar={solar_power}W, Injection={injection_power}W"})
                return rise_limit, rise_limit - last_limit, "Importation très forte", drop_next_delay

    # --- ALGO 2: FAST DROP ---
    if FAST_DROP_ALGORITHM_ENABLE:
        drop_thresh, drop_count, drop_limit_thresh, drop_next_delay = FAST_DROP_THRESHOLDS
        if injection_power > drop_thresh:
            state.consecutive_high_injection_count += 1
        else:
            state.consecutive_high_injection_count = 0

        if (state.consecutive_high_injection_count >= drop_count and last_limit > drop_limit_thresh and solar_power > 0 and state.fast_cooldown == 0):
            estimated_limit = int(((solar_power - injection_power) / TOTAL_RATED_SOLAR_POWER) * 1000)
            if estimated_limit < last_limit:
                logging.info(f"FAST DROP: Injection haute détectée. Ajustement rapide de {last_limit/10.0:.1f}% à {estimated_limit/10.0:.1f}%.")
                new_limit = estimated_limit
                state.fast_cooldown = FAST_COOLDOWN_NB
                state.consecutive_high_injection_count = 0
                mqtt_controller.publish("evt", {"code": 7, "msg": f"{MQTT_EVT_CODE[7]}. De {last_limit/10.0:.1f}% à {new_limit/10.0:.1f}%. Solar={solar_power}W, Injection={injection_power}W"})
                return new_limit, new_limit - last_limit, "Injection haute", drop_next_delay

    # --- ALGO 3: IMPORT LOCK ---
    if injection_power < 0:
        state.consecutive_import_count += 1
        if state.consecutive_import_count >= CONSECUTIVE_IMPORT_COUNT_FOR_RESET:
            if last_limit < MAX_POWER_LIMIT_PERMILLE:
                logging.info(f"Importation continue détectée. Passage à 100%.")
            state.consecutive_import_count = 0
            return MAX_POWER_LIMIT_PERMILLE, MAX_POWER_LIMIT_PERMILLE - last_limit, "Importation continue", -1
    else:
        state.consecutive_import_count = 0

    # --- ALGO 4: Logique principale par seuils ---
    for i, (threshold, increment, interval) in enumerate(INJECTION_POWER_THRESHOLDS):
        if injection_power >= threshold:
            lower_bound_str, upper_bound_str = f"{threshold}W", f"<{INJECTION_POWER_THRESHOLDS[i-1][0]}W" if i > 0 else ""
            threshold_info = f"{lower_bound_str}..{upper_bound_str}" if upper_bound_str else f">{lower_bound_str}"

            if increment == 0: return last_limit, 0, threshold_info, interval

            new_limit = last_limit + increment
            new_limit = max(MIN_POWER_LIMIT_PERMILLE, min(new_limit, MAX_POWER_LIMIT_PERMILLE))

            if last_limit == MAX_POWER_LIMIT_PERMILLE and new_limit == MAX_POWER_LIMIT_PERMILLE: interval = -1
            if round(new_limit) == BUGGY_LIMIT_PERMILLE: new_limit += 5 if increment > 0 else -5

            return new_limit, new_limit - last_limit, threshold_info, interval

    return last_limit, 0, "Hors plage", -1

def perform_write(limit_to_write):
    """Wrapper pour l'écriture Modbus."""
    if limit_to_write == BUGGY_LIMIT_PERMILLE: limit_to_write +=1   # ca ne devrait pas arriver
    if limit_to_write < MIN_POWER_LIMIT_PERMILLE: limit_to_write = MIN_POWER_LIMIT_PERMILLE # ca ne devrait pas arriver
    status = modbus_controller.write_power_limit(limit_to_write)
    if status == "OK":
        if state.consecutive_modbus_write_errors > 0:
            mqtt_controller.publish("evt", {"code": 4, "msg": MQTT_EVT_CODE[4]})
        state.current_power_limit_permille = limit_to_write
        state.consecutive_modbus_write_errors = 0
    else:
        if state.consecutive_modbus_write_errors == 0:
            mqtt_controller.publish("evt", {"code": 3, "msg": MQTT_EVT_CODE[3]})
        state.consecutive_modbus_write_errors += 1
    return status

def daemonize():
    """Détache le processus du terminal (mode démon)."""
    try:
        if os.fork() > 0: sys.exit(0)
    except OSError as e: sys.exit(f"fork #1 failed: {e}\n")
    os.chdir("/"); os.setsid(); os.umask(0)
    try:
        if os.fork() > 0: sys.exit(0)
    except OSError as e: sys.exit(f"fork #2 failed: {e}\n")
    sys.stdout.flush(); sys.stderr.flush()
    with open(os.devnull, 'r') as si, open(os.devnull, 'a+') as so, open(os.devnull, 'a+') as se:
        os.dup2(si.fileno(), sys.stdin.fileno()); os.dup2(so.fileno(), sys.stdout.fileno()); os.dup2(se.fileno(), sys.stderr.fileno())

def setup_logging(args):
    """Configure le logging vers la console, un fichier ou syslog."""
    level_map = {'debug': logging.DEBUG, 'info': logging.INFO, 'warn': logging.WARNING, 'err': logging.ERROR}
    log_level = level_map.get(args.loglevel.lower(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    logging.getLogger("pymodbus").setLevel(logging.WARNING)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    syslog_formatter = logging.Formatter('solar_regulator[%(process)d]: %(levelname)s %(message)s')
    handler = None
    if args.syslog_facility:
        handler = logging.handlers.SysLogHandler(address='/dev/log', facility=args.syslog_facility); handler.setFormatter(syslog_formatter)
    elif args.logfile:
        handler = logging.FileHandler(args.logfile); handler.setFormatter(formatter)
    else:
        handler = logging.StreamHandler(sys.stdout); handler.setFormatter(formatter)
    if root_logger.hasHandlers(): root_logger.handlers.clear()
    if handler: root_logger.addHandler(handler)

def parse_arguments():
    """Analyse les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(description="Démon de régulation d'injection solaire.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('ecu_ip', type=str, nargs='?', default=None, help=f"Adresse IP de l'ECU-R (défaut: {MODBUS_ECU_IP}).")
    parser.add_argument('--modbus-port', type=int, default=MODBUS_ECU_PORT)
    parser.add_argument('--modbus-slave', type=int, default=MODBUS_SLAVE_ID)
    parser.add_argument('--http-host', type=str, default='0.0.0.0')
    parser.add_argument('--http-port', type=int, default=8000)
    parser.add_argument('-nd', '--no-daemon', action='store_true', help="Mode console (ne pas se détacher du terminal).")
    parser.add_argument('-ll', '--loglevel', type=str, default='info', choices=['debug', 'info', 'warn', 'err'])
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument('-lf', '--logfile', type=str, help="Écrire les logs dans un fichier.")
    log_group.add_argument('-sf', '--syslog-facility', type=str, choices=[f'local{i}' for i in range(8)], help="Activer le logging vers syslog.")
    return parser.parse_args()

def periodic_task_thread():
    """Tâche de fond pour les actions non déclenchées par HTTP."""
    handle_periodic_tasks()
    while True:
        time.sleep(PERIODIC_TASK_INTERVAL_S)
        handle_periodic_tasks()

def handle_periodic_tasks():
    """Logique exécutée périodiquement par le thread de fond."""
    with state_lock:
        is_currently_in_window = state.is_in_regulation_window()
        if is_currently_in_window != state.was_in_regulation_window:
            in_out_str = 'Entrée en' if is_currently_in_window else 'Sortie de la'
            evt_code = 1 if is_currently_in_window else 2
            logging.info(f"Changement de tranche horaire. {in_out_str} régulation. Passage à 100%.")
            mqtt_controller.publish("evt", {"code": evt_code, "msg": MQTT_EVT_CODE[evt_code]})
            perform_write(MAX_POWER_LIMIT_PERMILLE)
            state.was_in_regulation_window = is_currently_in_window

        if is_currently_in_window and time.time() - state.last_modbus_read_time > PERIODIC_READ_INTERVAL_S:
            logging.info("Lecture périodique du power_limit...")
            handle_state_and_reads()

def watchdog_thread():
    """Surveille la communication avec le Shelly et réagit en cas de silence prolongé."""
    while True:
        with state_lock:
            if not state.watchdog_triggered and (time.time() - state.last_shelly_request_time > WATCHDOG_TIMEOUT_S):
                logging.warning(f"WATCHDOG: Aucune requête du Shelly depuis {WATCHDOG_TIMEOUT_S}s. Production à 100%.")
                if modbus_controller:
                    perform_write(MAX_POWER_LIMIT_PERMILLE)
                state.watchdog_triggered = True
        time.sleep(60)

def main():
    """Point d'entrée principal."""
    global modbus_controller
    args = parse_arguments()
    if not args.no_daemon: daemonize()
    setup_logging(args)
    ecu_ip = args.ecu_ip if args.ecu_ip else MODBUS_ECU_IP
    modbus_controller = ModbusController(ecu_ip, args.modbus_port, args.modbus_slave)

    Thread(target=watchdog_thread, daemon=True).start()
    Thread(target=periodic_task_thread, daemon=True).start()

    server_address = (args.http_host, args.http_port)
    try:
        httpd = ThreadingHTTPServer(server_address, RequestHandler)
    except OSError as e:
        logging.error(f"Impossible de démarrer le serveur HTTP sur {args.http_host}:{args.http_port}. Erreur: {e}")
        sys.exit(1)

    def shutdown_handler(signum, frame):
        logging.info("Signal d'arrêt reçu..."); Thread(target=httpd.shutdown).start()
    signal.signal(signal.SIGTERM, shutdown_handler); signal.signal(signal.SIGINT, shutdown_handler)

    logging.info(f"Démon démarré sur http://{args.http_host}:{args.http_port}")
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
    if mqtt_controller.client:
        mqtt_controller.client.loop_stop()
        mqtt_controller.client.disconnect()
    logging.info("Démon arrêté.")

if __name__ == "__main__":
    main()