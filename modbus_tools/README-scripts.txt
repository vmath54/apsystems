Utilitaires pour interroger / modifier un ECU en protocole modbus
-----------------------------------------------------------------
Testés avec un ECU-R en version 2162xxxxxxxx, et des micro onduleurs (MO) DS3

Ces scripts ne sont pas optimisés pour une production : ils génèrent une requete modbus pour chaque registre à lire, ce qui n'est pas très efficace.
Ils sont à utiliser pour des tests de fonctionnement

Il est probable qu'ils fonctionnent avec d'autres MO APSystems, avec peutêtre quelques adaptations

read_MO.py
##########
Permet de lire les principaux registres exposés par un MO DS3
syntaxe :
  read_MO.py -h : pour de l'aide
  read_MO.py 192.168.1.120 -u 11 : interrogation de l'ECU a l'adresse IP 192.168.1.120, pour le MO d'ID modbus 11

write_MO.py
###########
Permet d'écrire certains registres du système. On écrit ces registres en spécifiant un équipement (ID modbus), mais les modifications sont globales à l'installation.

Les registres qu'on peut modifier sont (voir doc APSystems_modbus_registers.xlsx) :
- 9CFC - 40188 : 'Conn' ; valeur 0 ou 1. Permet d'activer (1) ou de désactiver (0) la production solaire. Par défaut à 1
- 9CFD - 40189 : 'WMaxLimPct ; valeur de 0 à 1000, qui correspond à 0% - 100% (facteur de 0.1). Permet de limiter la production solaire.
- 9D01 - 40193 : 'WMaxLim_Ena' ; valeur 0 ou 1. Permet d'activer (1) ou de désactiver (0) la limitation de production solaire. Par défaut à 1

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


------------------------ un exemple d'utilisation de ces scripts ----------------
########
>read_MO.py 192.168.1.120 -u 11
Manufacturer = APsystems
Model = DS3
Version = V5312
Serial Number = 704000587038
Modbus ID = 11
Type Inverter = 101
current = 0.79 A
voltage = 234.0 V
power = 182.0 W
frequency = 50.0 Hz
Power (Apparent) = 186.3 VA
Power (Reactive) = 40.0 VAR
Power Factor = 0.976 cos φ
Total Energy = 2.4210000000000003 kWh
Temperature = 28.0 °C
Status = 4
Is Connected = 1
Power Max = 30.0 %
Power Max Ena = 1
DC1 voltage = 33.405120849609375 V
DC2 voltage = 33.68735885620117 V
DC1 current = 3.1473000049591064 A
DC2 current = 2.924999952316284 A
DC1 power = 105.13594055175781 W
DC2 power = 98.5355224609375 W

########
>read_all_MO.py 192.168.1.120 -u 1,11,12
liste des équipements scannes : 1, 11, 12

 ---------------------------------------------------------------------------------------------------------------------------------------------------------------
|      ID       |     power     | Total Energy  |  Temperature  |    Status     | Is Connected  |   Power Max   | Power Max Ena |   DC1 power   |   DC2 power   |
|       1       |     155 W     |   2.532 kWh   |     30 °C     |  Producing    |      1        |     30 %      |      1        |     85 W      |     86 W      |
|      11       |     182 W     |   2.421 kWh   |     28 °C     |  Producing    |      1        |     30 %      |      1        |     105 W     |     99 W      |
|      12       |     188 W     |   2.394 kWh   |     30 °C     |  Producing    |      1        |     30 %      |      1        |     99 W      |     98 W      |
 ---------------------------------------------------------------------------------------------------------------------------------------------------------------
Total AC Power : 525 W
Total DC Power : 572 W
Total Energy   : 7.347 kWh

########
>write_MO.py 192.168.1.120 -r power_limit -v 25
device 1, write register "Power Max". addr : 40189, value : 250

########
>read_all_MO.py 192.168.1.120 -u 1,11,12
liste des équipements scannes : 1, 11, 12

 ---------------------------------------------------------------------------------------------------------------------------------------------------------------
|      ID       |     power     | Total Energy  |  Temperature  |    Status     | Is Connected  |   Power Max   | Power Max Ena |   DC1 power   |   DC2 power   |
|       1       |     155 W     |   2.532 kWh   |     30 °C     |  Producing    |      1        |     25 %      |      1        |     85 W      |     86 W      |
|      11       |     182 W     |   2.421 kWh   |     28 °C     |  Producing    |      1        |     25 %      |      1        |     105 W     |     99 W      |
|      12       |     188 W     |   2.394 kWh   |     30 °C     |  Producing    |      1        |     25 %      |      1        |     99 W      |     98 W      |
 ---------------------------------------------------------------------------------------------------------------------------------------------------------------
Total AC Power : 525 W
Total DC Power : 572 W
Total Energy   : 7.347 kWh

########
>write_MO.py 192.168.1.120 -r power_limit -v 30
device 1, write register "Power Max". addr : 40189, value : 300

########
>read_all_MO.py 192.168.1.120 -u 1,11,12
liste des équipements scannes : 1, 11, 12

 ---------------------------------------------------------------------------------------------------------------------------------------------------------------
|      ID       |     power     | Total Energy  |  Temperature  |    Status     | Is Connected  |   Power Max   | Power Max Ena |   DC1 power   |   DC2 power   |
|       1       |     155 W     |   2.532 kWh   |     30 °C     |  Producing    |      1        |     30 %      |      1        |     85 W      |     86 W      |
|      11       |     182 W     |   2.421 kWh   |     28 °C     |  Producing    |      1        |     30 %      |      1        |     105 W     |     99 W      |
|      12       |     188 W     |   2.394 kWh   |     30 °C     |  Producing    |      1        |     30 %      |      1        |     99 W      |     98 W      |
 ---------------------------------------------------------------------------------------------------------------------------------------------------------------
Total AC Power : 525 W
Total DC Power : 572 W
Total Energy   : 7.347 kWh
