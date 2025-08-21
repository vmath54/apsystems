#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import sys
import json
import time

# --- Importation des bibliothèques tierces ---
# Essayez d'importer les bibliothèques requises et donnez des instructions si elles manquent.
try:
    import paho.mqtt.client as mqtt
    from pymodbus.client import ModbusTcpClient
    from pymodbus.exceptions import ModbusException
except ImportError as e:
    print(f"Erreur d'importation: {e}", file=sys.stderr)
    print("Veuillez installer les bibliothèques requises avec : pip install paho-mqtt pymodbus", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# --- SECTION DE CONFIGURATION ---
# Modifiez ces valeurs pour correspondre à votre environnement.
# =============================================================================

# Informations de connexion MQTT
# (IP/hostname, port, user, password, 1 si SSL/TLS sinon 0)
MQTT_CONN = ("localhost", 1883, "user", "password", 0)
MQTT_TOPIC = "solar_power_regulator/evt"

# Informations de connexion Modbus/TCP
# (IP/hostname, port, ID de l'esclave Modbus)
MODBUS_CONN = ("192.168.1.120", 502, 1)

# Numéro du registre Modbus pour le contrôle de la limite de puissance.
MODBUS_POWER_LIMIT_REGISTER = 40189
# Timeout en secondes pour la connexion Modbus
MODBUS_TIMEOUT = 5

# =============================================================================
# --- FIN DE LA SECTION DE CONFIGURATION ---
# =============================================================================

def setup_arg_parser():
    """
    Configure et parse les arguments de la ligne de commande.
    """
    parser = argparse.ArgumentParser(description="Envoie une consigne de limitation de puissance via Modbus et notifie via MQTT.")
    
    def check_power_limit_range(value):
        """Valide que la valeur de power_limit est dans la plage autorisée."""
        try:
            ivalue = int(value)
            if not 1 <= ivalue <= 100:
                raise argparse.ArgumentTypeError(f"La valeur {ivalue} est en dehors de la plage autorisée [1, 100].")
            return ivalue
        except ValueError:
            raise argparse.ArgumentTypeError(f"'{value}' n'est pas un nombre entier valide.")

    parser.add_argument(
        '-pl', '--power_limit',
        type=check_power_limit_range,
        required=True,
        help="Limite de puissance relative à appliquer (valeur numérique de 1 à 100)."
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
        client.loop_start()  # Gère la reconnexion en arrière-plan
        return client
    except Exception as e:
        print(f"Erreur critique: Impossible de se connecter au broker MQTT. {e}", file=sys.stderr)
        sys.exit(1)

def publish_mqtt_message(client, power_limit, value_written):
    """
    Construit et publie le message envoyé en MQTT.
    """
    payload = {
        "code": 9,
        "msg": f"write_maxlimit_Modbus. Ecriture Modbus de power_limit = {power_limit}% (valeur {value_written} écrite dans le registre {MODBUS_POWER_LIMIT_REGISTER})"
    }
    json_payload = json.dumps(payload)
    
    print(f"Publication du message sur MQTT topic '{MQTT_TOPIC}'...")
    result = client.publish(MQTT_TOPIC, json_payload)
    result.wait_for_publish()  # Attend la confirmation de la publication
    if result.is_published():
        print("Message MQTT publié avec succès.")
    else:
        print("Erreur: La publication du message MQTT a échoué.", file=sys.stderr)

def publish_mqtt_end_message(client):
    """
    Message de fin d'exécution
    """
    payload = {
        "code": 9,
        "msg" : "write_maxlimit_Modbus. Fin d'exécution de la procédure"
    }
    json_payload = json.dumps(payload)    
    result = client.publish(MQTT_TOPIC, json_payload)
    result.wait_for_publish()  # Attend la confirmation de la publication
    if result.is_published():
        print("Message MQTT publié avec succès.")
    else:
        print("Erreur: La publication du message MQTT a échoué.", file=sys.stderr)

def run_modbus_write(power_limit):
    """
    Exécute la requête d'écriture sur le registre Modbus.
    Retourne True en cas de succès, sinon quitte le programme.
    """
    host, port, slave_id = MODBUS_CONN
    value_to_write = power_limit * 10
    
    print("Exécution de la requête Modbus...")
    print(f"  -> Cible: {host}:{port}, Esclave: {slave_id}")
    print(f"  -> Registre: {MODBUS_POWER_LIMIT_REGISTER}, Valeur à écrire: {value_to_write} (pour power_limit={power_limit}%)")

    client = ModbusTcpClient(host=host, port=port, timeout=MODBUS_TIMEOUT)
    
    try:
        client.connect()
        # Écriture de la valeur dans un seul registre (holding register)
        # wr = client.write_register(address=MODBUS_POWER_LIMIT_REGISTER, value=value_to_write, slave=slave_id)
        values = client.convert_to_registers(value_to_write, client.DATATYPE.UINT16)
        wr = client.write_registers(MODBUS_POWER_LIMIT_REGISTER, values=values, slave=slave_id)

        # Vérification d'erreur
        if wr.isError():
            print(f"Erreur Modbus lors de l'écriture: {wr}", file=sys.stderr)
            sys.exit(1)

        print("Requête Modbus exécutée avec succès.")
        return True

    except ModbusException as e:
        print(f"Erreur de communication Modbus: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if client.is_socket_open():
            client.close()


def main():
    """
    Fonction principale du script.
    """
    args = setup_arg_parser()
    power_limit = args.power_limit

    # 1. Connexion au broker MQTT
    mqtt_client = setup_mqtt_client()
    start_time = time.time()
    
    try:
        # 2. Publication du message MQTT
        publish_mqtt_message(mqtt_client, power_limit, power_limit * 10)
        
        # 3. Exécution de la requête Modbus
        if run_modbus_write(power_limit):
            # Si on arrive ici, tout s'est bien passé
            print("-" * 50)
            print(f"Écriture Modbus réussie. power_limit = {power_limit}%")
            
        # 4. info de fin d'exécution de la requete modbus
        publish_mqtt_end_message(mqtt_client)

    finally:
        # 4. Déconnexion propre
        end_time = time.time()
        print("Déconnexion du client MQTT...")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        print(f"Opération terminée en {end_time - start_time:.2f} secondes.")


if __name__ == "__main__":
    main()