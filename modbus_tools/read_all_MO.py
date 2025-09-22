#!/usr/bin/env python3
"""
read_all_MO.py

lecture modbus de certains registres pour plusieurs micro onduleurs APSystems
teste avec des MO DS3
se limite aux infos les plus importantes (pour moi)
calcule les totaux de puissance
pas optimisé : fait une requete par registre à lire

syntaxe : 
  read_all_MO.py -h : pour de l'aide
  read_all_MO.py 192.168.1.120 -u 1,11,12 : interrogation de l'ECU a l'adresse IP 192.168.1.120, pour les MO d'ID modbus 1,11,12
  par défaut : DEFAULT_MODBUS_IP, DEFAULT_MODBUS_PORT, DEFAULT_MODBUS_DEVICES
"""

import argparse
import re
from enum import Enum
from datetime import datetime, timedelta
import time
import sys

# --------------------------------------------------------------------------- #
# import the various client implementations
# --------------------------------------------------------------------------- #
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

from pprint import pprint

DEFAULT_MODBUS_IP = "192.168.1.120"
DEFAULT_MODBUS_PORT = 502
DEFAULT_MODBUS_DEVICES = "1,11,12"

# nombre de secondes après le passage à la minute exacte modulo 5 mn : xh:0mn:{delta_s}, xh:5mn:{delta_s}, etc.
DELTA_SECONDS = 40

MOs = []   # liste des MO a interroger

INVERTER_STATUS_MAP = [
    "Undefined",
    "Off",
    "Sleeping",
    "Grid Monitoring",
    "Producing",
    "Producing (Throttled)",
    "Shutting Down",
    "Fault",
    "Standby",
]

def main() -> None:    
    argparser = argparse.ArgumentParser()
    argparser.add_argument("host", type=str, nargs='?', default = DEFAULT_MODBUS_IP, help=f"Modbus TCP address. default {DEFAULT_MODBUS_IP}")
    argparser.add_argument("-p", "--port", type=int, default = DEFAULT_MODBUS_PORT, help=f"Modbus TCP port. default {DEFAULT_MODBUS_PORT}")
    argparser.add_argument("-u", "--units", type=str, default = DEFAULT_MODBUS_DEVICES, help=f"List Modbus devices address. default {DEFAULT_MODBUS_DEVICES}")
    argparser.add_argument("-r", "--repeat", action="store_true", help="Répète la lecture toutes les 5 minutes à xx:x0:35s et xx:x5:35s.")
    args = argparser.parse_args()
    
    liste = ""
    for item in args.units.split(','):
        liste += f"{int(item)}, "
        MOs.append({"modbusid": int(item)})
    liste = re.sub(", $", "", liste)

    client: ModbusTcpClient = ModbusTcpClient(
        host=args.host,
        port=args.port,
        timeout=5,
    )

    registers = getRegisters(client)
    
    # Exécution immédiate de la fonction
    read_all_MOs(client, MOs, liste, registers)
    print_result(MOs, liste, registers)

    # Si l'option --repeat est présente, on entre dans la boucle de répétition
    if args.repeat:
        print(f"\nMode répétition activé. Déclenchement périodique à modulo 5ms +{DELTA_SECONDS}s...")
        try:
            while True:
                # Calcul du prochain instant d'exécution
                now = datetime.now()
                minute_de_base = (now.minute // 5) * 5
                
                prochain_instant = now.replace(minute=minute_de_base, second=DELTA_SECONDS, microsecond=0) + timedelta(minutes=5)

                instant_cette_periode = now.replace(minute=minute_de_base, second=DELTA_SECONDS, microsecond=0)
                if now < instant_cette_periode + timedelta(minutes=5):
                     prochain_instant = instant_cette_periode + timedelta(minutes=5)
                
                if now.minute % 5 == 0 and now.second < DELTA_SECONDS:
                    prochain_instant = now.replace(second=DELTA_SECONDS, microsecond=0)
                
                if now > instant_cette_periode and now < instant_cette_periode + timedelta(seconds=2):
                    prochain_instant = instant_cette_periode + timedelta(minutes=5)
                
                if prochain_instant <= now:
                    prochain_instant = prochain_instant + timedelta(minutes=5)

                temps_a_attendre = (prochain_instant - now).total_seconds()
                
                print(f"Prochaine lecture à {prochain_instant.strftime('%Y-%m-%d %H:%M:%S')}. En attente pendant {temps_a_attendre:.0f} secondes.")
                time.sleep(temps_a_attendre)
                
                read_all_MOs(client, MOs, liste, registers)

        except KeyboardInterrupt:
            print("\nArrêt du script par l'utilisateur.")
            sys.exit(0)


def read_all_MOs(client, MOs, liste, registers):
    client.connect()

    for one_MO in MOs:
        for k in registers.keys():
            one_MO[k] = None
        read_one_MO(client, one_MO, registers)
    client.close()
    
    
def read_one_MO(client: ModbusTcpClient, one_MO, registers):
    """Read registers."""
    error = False

    for k, v in registers.items():
        addr, data_type, length, factor, comment, unit = v
    
        if error:
            return
                
        slave = one_MO.get("modbusid")

        try:
            rr = client.read_holding_registers(address=addr, count=length, slave=slave)
        except ModbusException as exc:
            print(f"Erreur Modbus pour MO {slave} au registre {addr}: {exc!s}")
            error = True
            continue
        if rr.isError():
            print(f"Erreur de lecture pour MO {slave} au registre {addr}")
            error = True
            continue
        if isinstance(rr, ExceptionResponse):
            print(f"Exception de réponse pour MO {slave} au registre {addr}: {rr!s}")
            error = True
            continue
            
        value = client.convert_from_registers(rr.registers, data_type)
        one_MO[k] = value

def print_result(MOs, liste, registers):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n{timestamp}. liste des équipements scannes sur {DEFAULT_MODBUS_IP} : {liste}")
    print()    

    totaux = {"power_ac": 0, "energy_total": 0, "DC1_power": 0, "DC2_power": 0}

    print("", "-"*((16*(len(registers)+1)-1)))
    id = "ID"
    print(f"|{id:^15}", end='')
    for k, v in registers.items():
        addr, data_type, length, factor, comment, unit = v
        print(f"|{comment:^15}", end='')
    print("|")
    for one_MO in MOs:
        print(f"|{one_MO.get("modbusid"):^15}", end='')
        for k, v in registers.items():
            addr, data_type, length, factor, comment, unit = v
            value = one_MO.get(k)
            
            if value is None:
                valueS = "N/A"
                print(f"|{valueS:^15}", end='')
                continue

            if comment == "Status":
                value = INVERTER_STATUS_MAP[value]
            if factor != 0:
                value *= factor
            if (isinstance(value, int)):
                valueS = f"{value:d}"
            elif (isinstance(value, float)):
                if (factor == 0.001):
                    valueS = f"{value:.3f}"
                else:
                    valueS = f"{value:.0f}"
            else:
                valueS = value
            valueS += " " + unit
            print(f"|{valueS:^15}", end='')
            
            if k in totaux and value is not None and isinstance(value, (int, float)):
                totaux[k] += value
        print("|")
    print("", "-"*((16*(len(registers)+1)-1)))
    print(f"Total AC Power : {totaux.get("power_ac"):.0f} W")
    print(f"Total DC Power : {(totaux.get("DC1_power") + totaux.get("DC2_power")):.0f} W")
    print(f"Total Energy   : {totaux.get("energy_total"):.3f} kWh")
    
def getRegisters(client: ModbusTcpClient):
# key, data_type, length, factor, comment, unit
    registers = {
#        "version":            (40044, client.DATATYPE.STRING,  8,  0,    "Version",                           ""),
        "serialnumber":       (40052, client.DATATYPE.STRING,  16, 0,     "Serial Number",                     ""),
#        "modbusid":           (40068, client.DATATYPE.UINT16,  1,  0,    "Modbus ID",                         ""),
        "power_ac":           (40084, client.DATATYPE.UINT16,  1, 0.1,    "power",                            "W"),
        "energy_total":       (40094, client.DATATYPE.UINT32,  2, 0.001,  "Total Energy",                   "kWh"),
        "temperature":        (40103, client.DATATYPE.INT16,   1, 0.1,    "Temperature",                     "°C"),
        "status":             (40108, client.DATATYPE.INT16,   1, 0,      "Status",                            ""),
        "connected":          (40188, client.DATATYPE.UINT16,  1, 0,      "Is Connected",                      ""),
        "power_max_lim":      (40189, client.DATATYPE.UINT16,  1, 0.1,    "Power Max",                        "%"),
        "power_max_lim_ena":  (40193, client.DATATYPE.UINT16,  1, 0,      "Power Max Ena",                     ""),
        "DC1_power":          (40246, client.DATATYPE.FLOAT32, 2, 0,      "DC1 power",                        "W"),
        "DC2_power":          (40248, client.DATATYPE.FLOAT32, 2, 0,      "DC2 power",                        "W"),
    }
    return registers

if __name__ == "__main__":
    main()