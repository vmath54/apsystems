# Mesures de temps de réponse du système ECU-R et DS3 lors de changement de paramètres de puissance max

On peut influer sur la puissance maxi des micro-onduleurs (MO) APSystems de deux façons : par modbus ou par requête http.  
* **en modbus** : via l'écriture du registre **40189**, appelé ici **power_limit** : cette valeur est exprimée en millième de la puissance maxi des MOs.  
L'écriture de ce registre est prise en compte par tous les MOs de l'installation.
* **en http** : via l'URL http://<adresse_IP>/index.php/configuration/set_maxpower. La valeur donne la puissance maximum possible pour pour chaque panneau solaire d'un MO.   
L'écriture http concerne un seul MO ; il faut donc générer autant de requetes http que de MO dans l'installation.

Les mesures faites ici permettent d'évaluer :  
* la durée d'une requete modbus ou des requetes http
* le temps de réponse entre l'envoi de la commande, et la réalisation de celle-ci

Pour réaliser ces mesures, j'ai utilisé ces scripts :
* **MQTT_speedtest.js** : un script shelly qui envoie toutes les 500 ms en MQTT les informations de production solaire.
* **write_maxlimit_Modbus.py** : un script python qui génère une requete modbus pour écrire le registre power_limit ; il envoie également en MQTT les infos de début et de fin de requete modbus.
* **write_maxpower_HTTP.py** : un script python qui génère les requetes http pour limiter la puissance maxi des MOs ; les requetes sont envoyées en parallèle (threads). Le script envoie également en MQTT les infos de début et de fin des requetes http.
* **solar_read_mqtt.py** : un script python qui est en écoute sur les topics MQTT précédents, et qui écrit les infos dans des fichiers CSV avec un timestamp.

Pour exploiter les infos des fichiers CSV, j'ai utilisé le fichier excel **solar_read_mqtt.xlsm** : ce fichier permet d'importer un fichier **solar_power_regulator_run.csv** avec les bons réglages, et de calculer le temps (en millisecondes) entre 2 messages MQTT.

Mon installation comprend 1 DS3 880W coté Est, et 2 DS3 880W  coté Ouest. Les mesures ont été effectuées lors d'une journée sans nuage, vers 14h : c'est le moment ou le MO Est et les MO Ouest sont à peut près ensoleillés de la même manière ; la production maxi dans ces conditions est d'environ 70% de la capacité des MOs.

La procédure utilisée pour ces mesures est décrite dans le fichier **procedure.txt**.  
Les fichiers résultats (solar_power_regulator_run.csv renommé) sont :
* **HTTP_pas_xxx.csv** : les fichiers concernant les requetes http
* **modbus_pas_xxx.csv** : les fichiers concernant les requetes modbus

Une analyse de ces fichiers se trouve dans **resultats_http.txt** et **resultats_modbus.txt** ; les choses remarquables sont les suivantes :  

## temps moyen d'une requete modbus ou http
C'est une mesure de temps prise juste avant la requete et juste après.
* requete modbus : durée stable, environ 165ms
* requetes http : durée stable, un peu au dessus de 5s.

## début de réaction des MOs suite à une requete
C'est une mesure de temps prise juste avant la requete, jusqu'au début de réaction mesurée.
* requete modbus : en moyenne 2s
* requete http : en moyenne légèrement au dessus de 10s

## temps de réaction global des MOs
C'est une mesure de temps prise juste avant la requete, jusqu'a la valeur demandée. La réaction des MOs varie en fonction de l'importance de la variation

#### modbus
* variations importantes, supérieures à 20% : de 15s à 20s ; une fois beaucoup plus (39s)
* variations de 20% : de 8s à 10s ; une fois plus (15s)
* variations de 10% : de 6s à 10s
* variations de 5% : de 3s à 6s ; une fois 11s
* variations de 2% : de 3s à 7s  

Lorsque une mesure est plus longue que les autres, c'est le début de réaction qui est plus lent. Peut-être que l'ECU traite d'autres choses pendant ce temps ?

#### http
* variations importantes, supérieures à 20% : de 20s à 25s
* variations de 20% : de 14s à 24s
* variations de 10% : de 15s à 25s ; une fois 32s
* variations de 5% : de 12s à 18s
* variations de 2% : de 10s à 17s ; une fois 26s

## conclusion
Le temps de réaction des MOs suite à une modification de puissance maximale est important ; beaucoup plus en http qu'en modbus (différence supérieure à 7s).  
Il n'est pas possible de mettre au point un dispositif "zéro injection" parfait avec les requetes modbus ou http à cause de cette latence : lors de variation brutale de consommation (par exemple, une charge de 2000W qui commute d'un coup), il y aura obligatoirement un délai d'au moins 20s à 30s pour stabiliser le mécanisme.  
L'option http ne peut pas être retenue pour cet usage.   
