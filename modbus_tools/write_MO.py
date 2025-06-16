#!/usr/bin/env python3
"""
write_MO.py

ecriture modbus de registres de micro onduleurs APSystems
teste avec des MO DS3

syntaxe : 
  write_MO.py -h pour de l'aide
  write_MO.py 192.168.1.120 -u 1 -r power_limit -v 25 : connection de l'ECU a l'adresse IP 192.168.1.120. Ecriture dans le MO d'ID modbus 1, registre power_limit, valeur 25 (qui correspond en fait à l'écriture de la valeur 250 du registre 40189)
  Les registres que l'on peut ecrire sont :
    . connected : registre 40188, booléen (0/1). Si 0, les MO ne produisent plus ; si 1, les MO produisent
    . power_limit_ena : registre 40193, booléen (0/1). Si 0, la limitation de puissance est désactivée ; si 1, la limite est active
    . power_limit : registre 40189. Valeur de 0 à 100, c'est une limitation de puissance relative à la puissance max du MO. 
                    par exemple, pour un DS3 ayant une puissancec max de 880W, un power_limit à 25 limitera la puissance du MO à 220W
                    En realité, il y a un facteur 10 : si -v 25, alors la valeur 250 sera écrite dnas le registre 40189
                    
A noter : pour ces 3 registres, la modification est globale à l'installation. On spécifie un équipement (unit), mais la valeur écrite est globale                   
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

def main() -> None:
    
    argparser = argparse.ArgumentParser()
    argparser.add_argument("host", type=str, help="Modbus TCP address")
    argparser.add_argument("-p", "--port", type=int, default = 502, help="Modbus TCP port. default 502")
    argparser.add_argument("-u", "--unit", type=int, default=1, help="Modbus device address. Default = 1")
    argparser.add_argument("-r", "--register", type=str, required=True, choices=['connected', 'power_limit', 'power_limit_ena'], help="register to write : 'connected', 'power_limit' or 'power_limit_ena'")
    argparser.add_argument("-v", "--value", type=int, required=True, help="value to write : 0 or 1 for 'connected' or 'power_limit_ena', 0 to 30 for 'power_limit'")
    args = argparser.parse_args()
    # pprint(list(ModbusTcpClient.DATATYPE)); exit()  # retourne une liste de f"{data}: {data.value}"
    
    if (args.register == 'connected') or (args.register == 'power_limit_ena'):
        if (args.value != 0) and (args.value != 1):
            print(f"### ERREUR. Le registre '{args.register}' ne peut prendre que la valeur 0 ou 1")
            exit()
    if (args.register == 'power_limit'):
        if(args.value < 0) or (args.value > 100):
            print("### ERREUR. Le registre 'power_limit' ne peut prendre qu'une valeur entre 0 et 100")
            exit()
        else:
            args.value *= 10  # facteur 10 pour le registre power_limit
    
    client: ModbusTcpClient = ModbusTcpClient(
        host=args.host,
        port=args.port,
        timeout=5,
    )
    registers = getRegisters(client)
    if args.register not in registers:
        print(f"###ERREUR. La cle de registre {args.register} n'est pas connue")
        exit()
    
    client.connect()
    write_register(client, args.unit, registers[args.register], args.value)
    client.close()
    
def write_register(client: ModbusTcpClient, unit, register, value) -> None:
    print(f"device {unit}, write register \"{register[2]}\". addr : {register[0]}, value : {value}")

    try:
        value2write = client.convert_to_registers(value, register[1])
        wr = client.write_registers(address=register[0], values=value2write, slave=unit)
    except ModbusException as exc:
        print(f"Modbus exception: {exc!s}")
        error = True
    if wr.isError():
            print(f"Error")
            error = True
    if isinstance(wr, ExceptionResponse):
        print(f"Response exception: {wr!s}")
        error = True
 
def getRegisters(client: ModbusTcpClient):
    registers = {
        "connected":            (40188, client.DATATYPE.UINT16, "Is Connected"),
        "power_limit":          (40189, client.DATATYPE.UINT16, "Power Max"),
        "power_limit_ena":      (40193, client.DATATYPE.UINT16, "Power Max Enable"),
    }
    return registers
    
if __name__ == "__main__":
    main()