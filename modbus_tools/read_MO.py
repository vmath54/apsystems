#!/usr/bin/env python3
"""
read_MO.py

lecture modbus de registres de micro onduleurs APSystems
teste avec des MO DS3
pas optimisé : fait une requete par registre à lire

syntaxe : 
  read_MO.py -h : pour de l'aide
  read_MO.py 192.168.1.120 -u 11 : interrogation de l'ECU a l'adresse IP 192.168.1.120, pour le MO d'ID modbus 11
"""

import argparse
from enum import Enum
from time import sleep

# --------------------------------------------------------------------------- #
# import the various client implementations
# --------------------------------------------------------------------------- #
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

from pprint import pprint

DEFAULT_MODBUS_IP = "192.168.1.120"
DEFAULT_MODBUS_PORT = 502

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("host", type=str, nargs='?', default = DEFAULT_MODBUS_IP, help=f"Modbus TCP address. default {DEFAULT_MODBUS_IP}")
    argparser.add_argument("-p", "--port", type=int, default = DEFAULT_MODBUS_PORT, help=f"Modbus TCP port. default {DEFAULT_MODBUS_PORT}")
    argparser.add_argument("-u", "--unit", type=int, default=1, help="Modbus device address. default 1")
    args = argparser.parse_args()

    print(f"Interrogation modbus de {DEFAULT_MODBUS_IP} pour le device {args.unit}")
    print("-" * 50)    
    
    client: ModbusTcpClient = ModbusTcpClient(
        host=args.host,
        port=args.port,
        timeout=5,
    )
    registers = getRegisters
    client.connect()
    read_registers(client, args.unit)
    client.close()

def read_registers(client: ModbusTcpClient, slave) -> None:
    """Read registers."""
    error = False

    for k, v in getRegisters(client).items():
        addr, data_type, length, factor, comment, unit = v
    
        if error:
            error = False
            client.close()
            sleep(0.1)
            client.connect()
            sleep(1)
        
        try:
            rr = client.read_holding_registers(address=addr, count=length, slave=slave)
        except ModbusException as exc:
            print(f"Modbus exception: {exc!s}")
            error = True
            continue
        if rr.isError():
            print(f"Error")
            error = True
            continue
        if isinstance(rr, ExceptionResponse):
            print(f"Response exception: {rr!s}")
            error = True
            continue
            
        value = client.convert_from_registers(rr.registers, data_type)
        if factor != 0:
            value *= factor
        #    value = round(value, int(log10(factor) * -1))
        print(f"{comment} = {value} {unit}")

def getRegisters(client: ModbusTcpClient):
# key, data_type, length, factor, comment, unit
    registers = {
        "manufacturer":       (40004, client.DATATYPE.STRING,  16, 0,    "Manufacturer",                      ""),
        "model":              (40020, client.DATATYPE.STRING,  16, 0,    "Model",                             ""),
        "version":            (40044, client.DATATYPE.STRING,  8,  0,    "Version",                           ""),
        "serialnumber":       (40052, client.DATATYPE.STRING,  16, 0,    "Serial Number",                     ""),
        "modbusid":           (40068, client.DATATYPE.UINT16,  1,  0,    "Modbus ID",                         ""),
        "type_inverter":      (40070, client.DATATYPE.UINT16,  1,  0,    "Type Inverter",                     ""),  # 101 : single phase, 103 : three phases
        "current":            (40072, client.DATATYPE.UINT16,  1, 0.01,  "current",                          "A"),
        "voltage":            (40080, client.DATATYPE.UINT16,  1, 0.1,   "voltage",                          "V"),
        "power_ac":           (40084, client.DATATYPE.UINT16,  1, 0.1,   "power",                            "W"),
        "frequency":          (40086, client.DATATYPE.UINT16,  1, 0.01,  "frequency",                       "Hz"),
        "power_apparent":     (40088, client.DATATYPE.UINT16,  1, 0.1,   "Power (Apparent)",                "VA"),
        "power_reactive":     (40090, client.DATATYPE.UINT16,  1, 0.1,   "Power (Reactive)",               "VAR"),
        "power_factor":       (40092, client.DATATYPE.UINT16,  1, 0.001, "Power Factor",                 "cos φ"),
        "energy_total":       (40094, client.DATATYPE.UINT32,  2, 0.001, "Total Energy",                   "kWh"),
        "temperature":        (40103, client.DATATYPE.INT16,   1, 0.1,   "Temperature",                     "°C"),
        "status":             (40108, client.DATATYPE.INT16,   1, 0,     "Status",                            ""),
        "connected":          (40188, client.DATATYPE.UINT16,  1, 0,     "Is Connected",                      ""),
        "power_max_lim":      (40189, client.DATATYPE.UINT16,  1, 0.1,   "Power Max",                        "%"),
        "power_max_lim_ena":  (40193, client.DATATYPE.UINT16,  1, 0,     "Power Max Ena",                     ""),

#        "var_pct_mod":        (40205, client.DATATYPE.UINT16,  1, 0,     "VArPct_Mod",                        ""),
#        "var_pct_ena":        (40206, client.DATATYPE.UINT16,  1, 0,     "VArPct_Ena",                        ""),

        "DC1 voltage":        (40214, client.DATATYPE.FLOAT32, 2, 0,     "DC1 voltage",                      "V"),        
        "DC2 voltage":        (40216, client.DATATYPE.FLOAT32, 2, 0,     "DC2 voltage",                      "V"),        
        "DC1 current":        (40230, client.DATATYPE.FLOAT32, 2, 0,     "DC1 current",                      "A"),        
        "DC2 current":        (40232, client.DATATYPE.FLOAT32, 2, 0,     "DC2 current",                      "A"),        
        "DC1 power":          (40246, client.DATATYPE.FLOAT32, 2, 0,     "DC1 power",                        "W"),        
        "DC2 power":          (40248, client.DATATYPE.FLOAT32, 2, 0,     "DC2 power",                        "W"),        
    }
    return registers

if __name__ == "__main__":
    main()