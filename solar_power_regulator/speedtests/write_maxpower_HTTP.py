#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import sys
import json
import asyncio
import time
import paho.mqtt.client as mqtt
import requests
import aiohttp

# =============================================================================
# --- SECTION DE CONFIGURATION ---
# Modifiez ces valeurs pour correspondre à votre environnement.
# =============================================================================

# Cibles des requêtes HTTP (ECU)
DEVICES = ["704000162664", "704000585573", "704000587038"]
# DEVICES = ["704000162664"]

# Informations de connexion MQTT
# (IP/hostname, port, user, password, 1 si SSL/TLS sinon 0)
MQTT_CONN = ("localhost", 1883, "user", "password", 0)
MQTT_TOPIC = "solar_power_regulator/evt"

# Paramètres HTTP
HTTP_URL = "http://192.168.1.120/index.php/configuration/set_maxpower"
# Mettre à True pour que les requêtes HTTP soient sérialisées, à False pour paralléliser
HTTP_REQUEST_SERIALIZE = False
# Timeout en secondes pour les requêtes HTTP
HTTP_TIMEOUT = 10

# =============================================================================
# --- FIN DE LA SECTION DE CONFIGURATION ---
# =============================================================================

global_start_time = 0

def setup_arg_parser():
    """
    Configure et parse les arguments de la ligne de commande.
    """
    parser = argparse.ArgumentParser(description="Envoie une consigne de puissance max aux ECU et notifie via MQTT.")
    
    def check_maxpower_range(value):
        """Valide que la valeur de maxpower est dans la plage autorisée."""
        try:
            ivalue = int(value)
            if not 20 <= ivalue <= 500:
                raise argparse.ArgumentTypeError(f"La valeur {ivalue} est en dehors de la plage autorisée [20, 500].")
            return ivalue
        except ValueError:
            raise argparse.ArgumentTypeError(f"'{value}' n'est pas un nombre entier valide.")

    parser.add_argument(
        '-mp', '--maxpower',
        type=check_maxpower_range,
        required=True,
        help="Puissance maximale à définir pour chaque appareil (valeur numérique de 20 à 500)."
    )
    return parser.parse_args()

def setup_mqtt_client():
    """
    Initialise et connecte le client MQTT.
    Retourne l'instance du client en cas de succès, sinon quitte le programme.
    """
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    host, port, user, password, use_tls = MQTT_CONN
    
    if user and password:
        client.username_pw_set(user, password)
    
    if use_tls:
        client.tls_set()

    try:
        print(f"Connexion au broker MQTT à {host}:{port}...")
        client.connect(host, port, 60)
        client.loop_start() # Gère la reconnexion et le trafic en arrière-plan
        return client
    except Exception as e:
        print(f"Erreur critique: Impossible de se connecter au broker MQTT. {e}", file=sys.stderr)
        sys.exit(1)

def publish_mqtt_message(client, maxpower, num_devices):
    """
    Construit et publie le message de succès sur le topic MQTT.
    """
    payload = {
        "code": 9,
        "msg": f"write_maxpower_HTTP. Ecriture HTTP de maxpower = {maxpower}W pour {num_devices} devices"
    }
    json_payload = json.dumps(payload)
    
    print(f"Publication du message sur MQTT topic '{MQTT_TOPIC}'...")
    start_time_p = time.time()
    result = client.publish(MQTT_TOPIC, json_payload)
    result.wait_for_publish() # Attend la confirmation de la publication
    if result.is_published():
        print("Message MQTT publié avec succès.")
    else:
        print("Erreur: La publication du message MQTT a échoué.", file=sys.stderr)
    end_time_p = time.time()
    print(f"durée totale publish MQTT : {end_time_p - start_time_p:.2f} secondes.")

def publish_mqtt_end_message(client):
    """
    Message de fin d'exécution
    """
    payload = {
        "code": 9,
        "msg" : "write_maxpower_HTTP. Fin d'exécution de la procédure"
    }
    json_payload = json.dumps(payload)    
    result = client.publish(MQTT_TOPIC, json_payload)
    result.wait_for_publish()  # Attend la confirmation de la publication
    if result.is_published():
        print("Message MQTT publié avec succès.")
    else:
        print("Erreur: La publication du message MQTT a échoué.", file=sys.stderr)

def handle_http_error(device_id, maxpower, response_json):
    """
    Formate le message d'erreur pour une réponse HTTP invalide et quitte.
    """
    value = response_json.get('value', 'N/A')
    message = response_json.get('message', 'Aucun message')
    error_msg = (
        f"Erreur POST HTTP vers {device_id}, maxpower = {maxpower}. "
        f"value = {value}, msg = \"{message}\""
    )
    print(error_msg, file=sys.stderr)
    sys.exit(1)

def run_serial_requests(maxpower):
    """
    Exécute les requêtes HTTP de manière séquentielle.
    """
    print("Exécution des requêtes HTTP en mode SÉQUENTIEL...")
    headers = {'X-Requested-With': 'XMLHttpRequest'}
    
    for device_id in DEVICES:
        payload = {'id': device_id, 'maxpower': maxpower}
        start_time_h = time.time()
        try:
            # print(f"  -> Envoi de la requête pour le device {device_id}...")
            response = requests.post(HTTP_URL, data=payload, headers=headers, timeout=HTTP_TIMEOUT)
            response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP (4xx ou 5xx)
            
            end_time_h = time.time()
            print(f"requete HTTP pour {device_id}. début : {start_time_h - global_start_time:.2f}s, fin : {end_time_h - global_start_time:.2f}s, durée :  {end_time_h - start_time_h:.2f}s.")
            response_json = response.json()
            # print(f"   {response_json}")
            if response_json.get("value") != 0:
                handle_http_error(device_id, maxpower, response_json)

        except requests.exceptions.RequestException as e:
            print(f"Erreur critique de requête HTTP pour {device_id}: {e}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Erreur critique: La réponse du serveur pour {device_id} n'est pas un JSON valide.", file=sys.stderr)
            sys.exit(1)
                
    print("Toutes les requêtes séquentielles ont réussi.")

async def send_parallel_request(session, device_id, maxpower):
    """
    Fonction coroutine pour envoyer une seule requête HTTP de manière asynchrone.
    """
    payload = {'id': device_id, 'maxpower': maxpower}
    headers = {'X-Requested-With': 'XMLHttpRequest'}
    # print(f"  -> Préparation de la requête pour le device {device_id}...")
    try:
        start_time_h = time.time()
        async with session.post(HTTP_URL, data=payload, headers=headers, timeout=HTTP_TIMEOUT) as response:
            response.raise_for_status()
            # response_json = await response.json()  # ERREUR. message='Attempt to decode JSON with unexpected mimetype: text/html; charset=utf-8'
            response_text = await response.text()
            response_json = json.loads(response_text)
            
            end_time_h = time.time()
            print(f"requete HTTP pour {device_id}. début : {start_time_h - global_start_time:.2f}s, fin : {end_time_h - global_start_time:.2f}s, durée :  {end_time_h - start_time_h:.2f}s.")
            
            if response_json.get("value") != 0:
                # On ne quitte pas ici pour permettre aux autres de finir, l'erreur sera gérée dans la boucle principale.
                return {'error': True, 'device_id': device_id, 'maxpower': maxpower, 'response': response_json}
            
            return {'error': False, 'device_id': device_id}

    except Exception as e:
        # Capture toutes les exceptions (connexion, timeout, etc.)
        return {'error': True, 'device_id': device_id, 'maxpower': maxpower, 'response': str(e)}

async def run_parallel_requests(maxpower):
    """
    Exécute toutes les requêtes HTTP en parallèle en utilisant aiohttp.
    """
    print("Exécution des requêtes HTTP en mode PARALLÈLE...")
    async with aiohttp.ClientSession() as session:
        tasks = [send_parallel_request(session, device_id, maxpower) for device_id in DEVICES]
        results = await asyncio.gather(*tasks)
        
        # Vérifier les résultats après que toutes les tâches soient terminées
        has_error = False
        for res in results:
            if res.get('error'):
                has_error = True
                response_data = res.get('response')
                if isinstance(response_data, dict):
                    handle_http_error(res['device_id'], res['maxpower'], response_data)
                else:
                    # Gérer les erreurs de connexion/timeout
                    print(f"Erreur critique de requête HTTP pour {res['device_id']}: {response_data}", file=sys.stderr)
        
        if has_error:
            # Si handle_http_error a été appelé, le script aura déjà quitté.
            # Cette ligne est une sécurité supplémentaire.
            sys.exit(1)

    print("Toutes les requêtes parallèles ont réussi.")


def main():
    """
    Fonction principale du script.
    """
    args = setup_arg_parser()
    maxpower = args.maxpower
    num_devices = len(DEVICES)

    if not num_devices:
        print("Erreur: Le tableau DEVICES est vide. Aucune requête à envoyer.", file=sys.stderr)
        sys.exit(1)

    # 1. Connexion au broker MQTT
    mqtt_client = setup_mqtt_client()

    global global_start_time
    global_start_time = time.time()
    
    try:
        # 2. Publication du message MQTT. Très rapide
        publish_mqtt_message(mqtt_client, maxpower, num_devices)

        # 3. Exécution des requêtes HTTP
        if HTTP_REQUEST_SERIALIZE:
            run_serial_requests(maxpower)
        else:
            asyncio.run(run_parallel_requests(maxpower))
        
        # Si on arrive ici, tout s'est bien passé
        print("-" * 50)
        print(f"POST HTTP vers {num_devices} devices, maxpower = {maxpower}W")
        
        # 4. info de fin d'exécution des requetes HTTP
        publish_mqtt_end_message(mqtt_client)

        

    finally:
        end_time = time.time()
        # 4. Déconnexion propre
        print("Déconnexion du client MQTT...")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        print(f"Opération terminée en {end_time - global_start_time:.2f} secondes.")


if __name__ == "__main__":
    main()