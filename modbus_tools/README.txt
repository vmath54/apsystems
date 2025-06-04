Utilitaires pour interroger / modifier un ECU en protocole modbus
-----------------------------------------------------------------
Testés avec un ECU-R en version 2162xxxxxxxx, et des micro onduleurs (MO) DS3

Ces scripts ne sont pas optimisés pour une production : ils génère une requete modbus pour chaque registre à lire, ce qui n'est pas très efficace.
Ils sont à utiliser pour des tests de fonctionnement

read_MO.py
##########
Permet de lire tous les registres exposés par un MO DS3
syntaxe :
  read_MO.py -h : pour de l'aide
  read_MO.py 192.168.1.120 -u 11 : interrogation de l'ECU a l'adresse IP 192.168.1.120, pour le MO d'ID modbus 11

write_MO.py
###########
Permet d'écrire certains registres du système. On écrit ces registres en spécifiant un équipement (ID modbus), mais les modifications sont globales à l'installation.

Les registres qu'on peut modifier sont (voir doc APSystems_modbus_registers.xlsx) :
- 9CFC - 40188 : 'Conn' ; valeur 0 ou 1. Permet d'activer (1) ou de désactiver (0) la production solaire. Par défaut à 1
- 9CFD - 40189 : 'WMaxLimPct ; valeur de 0 à 300, qui corespond à 0% - 30% (facteur de 10). Permet de limiter la production solaire. Par défaut à 300
- 9D01 - 40193 : 'WMaxLim_Ena' ; valeur 0 ou 1. Permet d'activer (1) ou de désactiver (0) la limitation de production solaire. Par défaut à 1

A noter que je ne comprends pas bien cete valeur de 300 (30%) qui correspond an fait au maximum de production pour le MO ...

syntaxe : 
  write_MO.py -h pour de l'aide
  write_MO.py 192.168.1.120 -u 1 -r power_limit -v 25 : connection de l'ECU a l'adresse IP 192.168.1.120. Ecriture dans le MO d'ID modbus 1, registre power_limit, valeur 25 (qui correspond en fait à l'écriture de la valeur 250 du registre 40189)

  l'attribut r (register) peut prendre 3 valeurs : 'connected', 'power_limit', 'power_limit_ena'

read_all_MO.py
##############
Permet d'interroger les valeurs essentielles (pour moi) de plusieurs MOs, et de les afficher en mode tableau
syntaxe : 
  read_all_MO.py -h : pour de l'aide
  read_all_MO.py 192.168.1.120 -u 1,11,12 : interrogation de l'ECU a l'adresse IP 192.168.1.120, pour les MO d'ID modbus 1,11,12


------------------------ un exemple d'utilisation de ces scripts (fin de journée, peu de production) ----------------
>read_MO.py 192.168.1.120 -u 11
Manufacturer = APsystems
Model = DS3
Version = V5312
Serial Number = 704000587038
Modbus ID = 11
Type Inverter = 101
current = 1.08 A
voltage = 239.0 V
power = 256.0 W
frequency = 50.0 Hz
Power (Apparent) = 259.7 VA
Power (Reactive) = 44.0 VAR
Power Factor = 0.985 cos φ
Total Energy = 1.3940000000000001 kWh
Temperature = 34.0 °C
Status = 4
Is Connected = 1
Power Max = 30.0 %
Power Max Ena = 1
DC1 voltage = 36.16704177856445 V
DC2 voltage = 35.88479995727539 V
DC1 current = 3.9195001125335693 A
DC2 current = 3.9195001125335693 A
DC1 power = 141.75672912597656 W
DC2 power = 140.65048217773438 W

>read_all_MO.py 192.168.1.120 -u 1,11,12
liste des équipements scannes : 1, 11, 12

 ---------------------------------------------------------------------------------------------------------------------------------------------------------------
|      ID       |     power     | Total Energy  |  Temperature  |    Status     | Is Connected  |   Power Max   | Power Max Ena |   DC1 power   |   DC2 power   |
|       1       |     123 W     |   1.303 kWh   |     29 °C     |  Producing    |      1        |     30 %      |      1        |     67 W      |     70 W      |
|      11       |     256 W     |   1.394 kWh   |     34 °C     |  Producing    |      1        |     30 %      |      1        |     142 W     |     141 W     |
|      12       |     270 W     |   1.357 kWh   |     37 °C     |  Producing    |      1        |     30 %      |      1        |     144 W     |     142 W     |
 ---------------------------------------------------------------------------------------------------------------------------------------------------------------

>write_MO.py 192.168.1.120 -r power_limit -v 25
device 1, write register "Power Max". addr : 40189, value : 250

>read_all_MO.py 192.168.1.120 -u 1,11,12
liste des équipements scannes : 1, 11, 12

 ---------------------------------------------------------------------------------------------------------------------------------------------------------------
|      ID       |     power     | Total Energy  |  Temperature  |    Status     | Is Connected  |   Power Max   | Power Max Ena |   DC1 power   |   DC2 power   |
|       1       |     123 W     |   1.303 kWh   |     29 °C     |  Producing    |      1        |     25 %      |      1        |     67 W      |     70 W      |
|      11       |     256 W     |   1.394 kWh   |     34 °C     |  Producing    |      1        |     25 %      |      1        |     142 W     |     141 W     |
|      12       |     270 W     |   1.357 kWh   |     37 °C     |  Producing    |      1        |     25 %      |      1        |     144 W     |     142 W     |
 ---------------------------------------------------------------------------------------------------------------------------------------------------------------

>write_MO.py 192.168.1.120 -r power_limit -v 30
device 1, write register "Power Max". addr : 40189, value : 300

E:\temp\solaire\VM>read_all_MO.py 192.168.1.120 -u 1,11,12
liste des équipements scannes : 1, 11, 12

 ---------------------------------------------------------------------------------------------------------------------------------------------------------------
|      ID       |     power     | Total Energy  |  Temperature  |    Status     | Is Connected  |   Power Max   | Power Max Ena |   DC1 power   |   DC2 power   |
|       1       |     123 W     |   1.303 kWh   |     29 °C     |  Producing    |      1        |     30 %      |      1        |     67 W      |     70 W      |
|      11       |     256 W     |   1.394 kWh   |     34 °C     |  Producing    |      1        |     30 %      |      1        |     142 W     |     141 W     |
|      12       |     270 W     |   1.357 kWh   |     37 °C     |  Producing    |      1        |     30 %      |      1        |     144 W     |     142 W     |
 ---------------------------------------------------------------------------------------------------------------------------------------------------------------