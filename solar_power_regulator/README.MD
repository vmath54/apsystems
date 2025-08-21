# Solar Power Regulator

## 1. Présentation Générale

### Présentation général du projet

Ce projet permet de limiter l'injection d'énergie électrique d'une installation solaire vers le réseau public. Il est conçu pour les installations équipées de micro-onduleurs **APSystems** supervisés par une passerelle **ECU-R**.

Le système repose sur une architecture client-serveur :
* **Le Démon (`solar_power_regulator.py`)** : C'est le cerveau du système. Il tourne sur un serveur Linux (typiquement un Raspberry Pi ou une machine Armbian) sur le réseau local. Il héberge une API REST et communique en Modbus TCP avec la passerelle ECU-R pour ajuster la production des micro-onduleurs.
* **Le Client (`solar_power_regulator.js`)** : C'est un script léger qui s'exécute sur un appareil **Shelly Pro EM**. Le Shelly, équipé d'une pince ampèremétrique sur l'arrivée générale, mesure en temps réel l'injection ou la consommation sur le réseau. Il envoie ces mesures au démon, qui lui indique en retour à quelle fréquence envoyer la prochaine mesure.  
Il est également équipé d'une seconde pince ampèremétrique, qui mesure généralement le courant produit par l'installation solaire.
Si utilisé, ceci permet d'affiner l'algorithme de régulation, dans le cas de modification brutale de consommation ou de production.

L'objectif est de maintenir l'injection d'énergie vers le réseau dans une plage très faible (par exemple, entre 0 et 30W), en bridant la production solaire juste ce qu'il faut pour couvrir la consommation de la maison.  
Il y aura bien sûr des dépassements dans les 2 sens, lors de variation brutale de consommation de l'habitation, ou de variation brutale de production solaire. Les algos ont été développés pour limiter ces effets.

### Environnement de développement et d'essai

les scripts `solar_power_regulator.py` et `solar_power_regulator.js` ont été générés par une IA, et assez peu modifiés. Ce fichier README a également été généré initialement par une IA, puis profondément modifié ensuite.  
Il y a eu bien sûr de très nombreuses itérations liées à des modifications du cahier des charges, et à des 'oublis' récurrents du moteur d'IA lors de chaque itération.

Globalement, l'expérience est très positive : je suis informaticien, mais pas spécialiste en python ni en javascript, encore plus dédié à un shelly.  
Je suis très satisfait du résultat, que je peux maintenant adapter et paraméter à ma guise.

Il reste en ce moment en état "Proof Of Concept" : il fonctionne, il mérite des améliorations.   

La fréquence d'envoi par le Shelly des informations d'injection ou d'importation d'énergie électrique vers le démon entrainent une latence dans la régulation, dans le cas de variation très rapide. Ces variations très rapides sont fréquentes, surtout du côté consommation : fonctionnement d'un lave-vaisselle, ...  
Même une imprimante laser domestique, qui déclenche deux pics de consommation de 1200W après la mise sous tension. J'estime malgré tout que le fonctionnement est assez satisfaisant.

Il sera bien sûr nécessaire d'adapter les paramètres par rapport à son installation.  
Conseil : tester en mode `debug` pendant une certaine période pour les adapter au plus près.

Je vais nommer dans cette doc :
* **MO** : Micro-Onduleur
* **PV** : Panneau solaire
* **power_limit** : le **pourcentage** de limitation de production que l'on applique en une requête modbus à **tous** les MO par rapport à leur limite théorique.  
Ceci n'est pas tout à fait exact : côté modbus, la valeur lue ou écrite n'est pas en "pour cent", mais en **"pour mille"**. Aussi, lorsque dans ce document on parle d'un power_limit à une valeur de 50%, cela correspond en fait à la valeur 500 du registre modbus.  
Il est essentiel de bien comprendre cela pour paramétrer corectement le démon.  
Voir la section dédiée aux particularités du fonctionnement modbus APSystems, en fin de ce document.

Chez moi :  
* les MO sont des **DS3**, qui peuvent gérer chacun 2 PV. Chaque MO peut fournir au maximum 880W.  
Les PV ont une puissance en Wc (Watts crête) de 450W. Vu la latitude de mon habitation, l'inclinaison des panneaux et leur orientation, les PV limitent rarement la puissance des panneaux ; en clair, la production de chaque MO atteint rarement 880W.
* Il y a un MO côté Est et deux MO côté Ouest. La **puissance maximum théorique de production solaire est donc de 2640W**. Le MO côté Est produit surtout en matinée, les deux côté Ouest en après-midi. Le pic de production global se situe vers 14h.

---

## 2. Communication entre le script Shelly et le Démon

Le Shelly envoie périodiquement les informations d'injection/importation d'énergie avec le réseau et de production solaire via une requete HTTP - REST.  
Cete requête comporte des informations en format JSON, et recoit en retour des réponses en format JSON.

### informations transmises en JSON par le script shelly
| nom                   | type   | Description |
| --------------------- | ------ | ----------- |
| **`injection_power`**     | entier | &nbsp;C'est la puissance d'injection actuelle, en Watts. Valeur **positive si injection**, **négative si importation** |
| **`solar_power`**        | entier | &nbsp;C'est la puissance actuelle de production solaire, en Watts. Si la valeur est -1, cette puissance n'est pas mesurée par le Shelly ; sinon, c'est une valeur positive ou nulle |

### paramètres en retour du démon
| nom                   | type   | Description |
| --------------------- | ------ | ----------- |
| **`return_code`** | &nbsp;&nbsp;entier | &nbsp;C'est un code retour de fonctionnement du démon |
| **`message`** | &nbsp;&nbsp;string | &nbsp; C'est un message indicatif |
| **`power_limit_increment`** | &nbsp;&nbsp;float | &nbsp;C'est la valeur de l'incrément (positif) ou du décrément (négatif) appliqué au `power-limit`, en poucentage. Par exemple, -0.5 siginfie un décrément de 0.5% du `power_limit`. Si valeur -1, il y a eu une erreur, `power_limit` n'a pas pu être calculé ou écrit |
| **`power_limit_value`** | &nbsp;&nbsp;float | &nbsp; C'est la nouvelle valeur de `power_limit` calculée par le démon. Par exemple, 20.5 |
| **`sensor_read_interval`** | &nbsp;&nbsp;int | &nbsp; C'est le délai demandé par le démon pour recevoir la nouvelle mesure (donc nouvelle requête REST). Si la valeur est -1, alors le script shelly applique le délai par défaut |

Concernant le code retour, ses valeurs sont les suivantes :  

| valeur | Signification |
| ------ | ------------- |
| 0      | le traitement s'est bien déroulé, power_limit a été calculé et écrit |
| 1      | Comme 0, mais le power_limit lu était différent du power_limit mémorisé. C'est un warning |
| 2      | Une erreur de communication modbus a eu lieu, en lecture ou en écriture. power_limit n'a pas pu être écrit |
| 3      | Erreur récurrente de communication modbus. Par exemple, 5 erreurs consécutives |
| 9      | Autre erreur |

A noter que le script Shelly ne traite que l'info `sensor_read_interval`, pour adapter sa fréquence d'envoi des informations vers le démon.  
Les autres infos ne sont utilisées que pour écrire dans la log, en mode debug.

---

## 3. Le Script Shelly (`solar_power_regulator.js`)

Ce script permet d'envoyer au démon les informations relatives à l'importation ou exportation d'énergie électrique avec le réseau, et optionnellement la production solaire.

### Algo

* Lire périodiquement la puissance mesurée par les pinces ampèremétriques.
* Envoyer les données de puissance (injection réseau et production solaire) au démon Python via une requête HTTP POST.
* Se mettre en pause la nuit pour éviter les communications inutiles.
* Adapter dynamiquement sa fréquence de communication en fonction des instructions reçues du démon (`sensor_read_interval`)

### Configuration

La configuration se fait directement au début du script :

| Paramètre                    | Description |
| ---------------------------- | ----------- |
| `DEBUG`                      | Affiche les logs détaillés dans la console du Shelly si mis à `1` |
| `MODBUS_DAEMON_URL`          | Adresse IP et port du serveur où tourne le démon Python |
| `GRID_SENSOR_ID`             | ID du capteur Shelly mesurant l'échange avec le réseau (ex: `"em1:0"`) |
| `SOLAR_SENSOR_ID`            | ID du capteur Shelly mesurant la production solaire (ex: `"em1:1"`). Laisser vide si non utilisé |
| `GRID_REVERSE_MEASURE`       | Mettre à `true` si une injection est mesurée comme une valeur négative (cas standard) |
| `DEFAULT_REQUEST_INTERVAL_S` | Intervalle par défaut (en secondes) entre deux requêtes si le démon ne donne pas d'instruction |
| `PAUSE_ON_ERROR_S`           | Temps d'attente (en secondes) avant de réessayer si une communication avec le démon échoue |
| `NIGHT_MODE_ENABLE`          | Active (`true`) ou désactive (`false`) la mise en pause nocturne |
| `NIGHT_MODE_START_H`         | Heure de début du mode nuit (ex: `22` pour 22h00) |
| `NIGHT_MODE_END_H`           | Heure de fin du mode nuit (ex: `6` pour 06h00) |
| `NIGHT_MODE_INTERVAL_S`      | Fréquence des requêtes pendant la nuit (ex: `900` pour une requête toutes les 15 minutes) |

---

## 4. Le Démon Python (`solar_power_regulator.py`)

C'est le cœur du système, où toute la logique de régulation est implémentée.

### Rôle

* Recevoir les données du Shelly via son API REST.
* Maintenir un état de la limite de production actuelle (`power_limit`).
* Appliquer plusieurs algorithmes pour calculer la nouvelle limite de puissance optimale.
* Envoyer la commande de mise à jour de la limite à l'ECU-R via Modbus TCP.
* Optionnellement, envoyer en MQTT les informations de production, et les informations d'évenement
* Gérer des tâches de fond autonomes (watchdog, tranches horaires, vérifications périodiques).

### librairies python à installer
* pymodbus
* paho.mqtt

### Algorithmes de Régulation

Pour limiter les accès modbus, le démon ne lit la valeur de `power_limit` qu'au démarrage, ou en début de tranche horaire, ou ensuite de manière régulière (toutes les 15mn par exemple).  
Il suppose que la valeur actuelle de `power_limit` est celle qu'il a écrit précédemment. Il faut donc éviter de modifier ce registre par ailleurs.  

Le démon utilise une combinaison de stratégies pour une régulation fine et réactive ; l'idée est surtout de de viser la plage idéale, sinon de favoriser très temporairement l'injection en cas de grosse variation.  
Habituellement, il applique l'algo par défaut : la "régulation par seuils". Cet algorithme est très efficace s'il n'y a pas de variations brusques de consommation et/ou de production.  
En cas de changements brutaux de consommation, il peut appliquer ponctuellement l'algo "Fast Rise" pour augmenter rapidement `power_limit` (en général, vers 100.0%), ou inversement l'algo "Fast Drop" pour réduite rapidement la valeur de `power_limit`.  
Un contrôle de type "`watchdog`" vérifie que le shelly envoie régulièrement des requêtes avec les informations désirées. Si ce n'est pas le cas, le démon passe `power_limit` à 100.0% afin de ne pas brider la production solaire s'il n'a plus d'infos sur l'injection / importation.

1.  **Défaut : Régulation par Seuils** : L'algorithme principal se base sur une table de seuils (`INJECTION_POWER_THRESHOLDS`). En fonction de la puissance d'injection mesurée, il applique un incrément (positif ou négatif) à `power_limit` et définit la fréquence de la prochaine mesure (`sensor_read_interval`).  
Paramètre concerné : **`INJECTION_POWER_THRESHOLDS`**  
La plage d'injection cible est celle qui a une valeur d'incrément nulle.
2.  **"Fast Rise"** : En cas de forte et soudaine consommation (ex: démarrage d'un four), l'algorithme détecte une importation massive. Il force alors très rapidement `power_limit` à une valeur haute paramétrable (100% par exemple) pour répondre à la demande sans attendre les paliers progressifs.  
Paramètres concernés : **`FAST_RISE_ALGORITHM_ENABLE`** et  **`FAST_RISE_THRESHOLDS`**
3.  **"Fast Drop"** : En cas de forte et soudaine baisse de consommation (ex: arrêt d'un four), si la limite de puissance est restée inutilement haute (ex: 90%), le système  ajuste alors rapidement la limite à une valeur théorique calculée en fonction de la puissance maximale de l'installation (`TOTAL_RATED_POWER_W`), la valeur actuelle d'injection (`injection_power`), et la valeur de la production solaire actuelle (`solar_power`).  
L'algo Fast Drop ne fonctionne que si l'info de production solaire est fournie par le Shelly.  
Paramètres concernés : **`FAST_DROP_ALGORITHM_ENABLE`**, **`FAST_DROP_THRESHOLDS`** et **`TOTAL_RATED_SOLAR_POWER`**
6.  **Tâches de Fond** : Un thread s'exécute en permanence toutes les minutes pour :
    * Gérer les **tranches horaires** : il libère la production à 100% en dehors des heures de régulation.  
	Paramètre concerné : **`REGULATION_WINDOWS`**
    * Effectuer une **lecture de contrôle** modbus de `power_limit` toutes les 15 minutes (paramétrable) pour s'assurer que la limite n'a pas été modifiée manuellement.  
	Paramètre concerné : **`PERIODIC_READ_INTERVAL_S`**
7.  **Watchdog** : Si le démon ne reçoit aucune nouvelle du Shelly pendant une longue période (1 heure, paramétrable), il considère que le client est défaillant et libère la production à 100% par sécurité.  
Paramètre concerné : **`WATCHDOG_TIMEOUT_S`**

### MQTT

Le démon a la possibilité d'envoyer des informations vers un serveur MQTT.  
Le topic par défaut est `/solar_power_regulator` ; il peut écrire dans 2 sous-topics :  
* **`run`** : ce topic reçoit les infos de production, en format JSON. Par ex :  
`{"solar": 661, "injection": 259, "power_limit": 11.1, "delay": 3}`
* **`evt`** : ce topic reçoit les infos d'évenement, en format JSON. Par ex :  
`{"code": 7, "msg": "FAST_DROP. De 90.0% à 30.1%. Solar=663W, Injection=269W"}`

les messages d'évenement gérés sont les suivants :  
```
1:"REGULATION_WINDOWS_IN",     # entrée dans une tranche de régulation
2:"REGULATION_WINDOWS_OUT",    # sortie d'une tranche de régulation
3:"MODBUS_ERROR_START",        # erreur modbus.
4:"MODBUS_ERROR_END",          # fin d'erreur modbus
5:"POWER_LIMIT_30.0",          # power_limit lu a la valeur 30.0%. Le démon force la valeur 100.0%
6:"POWER_LIMIT_DIFF",          # power_limit lu est différent du power_limit mémorisé
7:"FAST_DROP",                 # le démon applique l'algo FAST_DROP
8:"FAST_RISE",                 # le démon applique l'algo FAST_RISE
```

### paramètres de configuration dans le code

| Paramètre                    | Description |
| ---------------------------- | ----------- |
| `TOTAL_RATED_SOLAR_POWER` | Puissance nominale totale de l'installation solaire en Watts (somme des puissances max des micro-onduleurs). Utilisé par l'algo "Fast Drop" |
| `REGULATION_WINDOWS`         | tranches horaires pour activer la limitation d'injection. Voir commentaires dans le code pour plus d'info |
| `MODBUS_ECU_IP`              | Adresse IP de l'ECU-R. Peut être surchargé par la ligne de commande |
| `MODBUS_ECU_PORT`            | Port TCP Modbus de l'ECU-R. Défaut 502. Peut être surchargé par la ligne de commande, argument `--modbus-port` |
| `MODBUS_SLAVE_ID`            | ID de l'esclave Modbus à adresser. Défaut 1. Peut être surchargé par la ligne de commande, argument `--modbus-slave` |
| `MODBUS_POWER_LIMIT_REGISTER` | Le registre modbus correcpondant à power_limit. Valeur = 40189 |
| `MODBUS_RECURRENT_ERROR_COUNT` | Nombre d'échecs d'écriture Modbus successifs avant de passer en erreur récurrente |
| `MIN_POWER_LIMIT_PERMILLE` | Valeur minimum de power_limit que l'algo peut fixer. Par exemple, 10 = 1% |
| `MAX_POWER_LIMIT_PERMILLE` | Valeur maximum de power_limit que l'algo peut fixer. Conseil : 1000 = 100.0% |
| `BUGGY_LIMIT_PERMILLE` | Valeur de `power_limit`non fiable. Laisser à 300. Cette valeur n'est jamais écrite par l'algo ; si cette valeur est lue, l'algo écrit et mémorise 1000, donc 100.0% |
| `INJECTION_POWER_THRESHOLDS` | Décrit les différents seuils pour l'algo de régulation par seuils. La plage souhaité est celle ayant un incrément à 0 |
| `CONSECUTIVE_IMPORT_COUNT_FOR_RESET` | Nombre de requêtes en importation successives avant de forcer la production à 100.0% |
| `FAST_DROP_ALGORITHM_ENABLE` | Active l'algo Fast DROP. Ne fonctionne que si 'info de production solaire (solar_power) est transmise par le shelly |
| `FAST_DROP_THRESHOLDS`| Permet de régler l'algo Fast DROP. Voir commentaires dans le code |
| `FAST_RISE_ALGORITHM_ENABLE` | Active l'algo Fast RISE |
| `FAST_RISE_THRESHOLDS` | Permet de régler l'algo Fast RISE. Voir commentaires dans le code |
| `FAST_COOLDOWN_NB` | Nombre de requetes 'normales' avant de pouvoir enclencher un algo 'FAST'. Objectif : ne pas enchainer des FAST_DROP, FAST_RISE, ... successifs |
| `MQTT_ENABLE` | 0 : Désactiver l'envoi d'informations MQTT. 1 : MQTT activé, pour tout. 2 : MQTT activé, mais juste pour les évènements|
| `MQTT_CONN` | Les infos de connexion MQTT. Voir commentaires dans le code |
| `MQTT_ROOT_TOPIC` | le topic MQTT racine |
| `PERIODIC_READ_INTERVAL_S` | En secondes. Intervalle pour effectuer une lecture modbus de controle du registre power_limit |
| `WATCHDOG_TIMEOUT_S` | En secondes. Si pas d'infos du shelly pendant le temps désigné, power_limit est passé à 100.0% |
| `PERIODIC_TASK_INTERVAL_S` | En secondes. Intervalle pour les tâches de fond (tranches horaires, etc.) |

### arguments de la ligne de commande

| Argument                       | Description                                                     |
| ------------------------------ | --------------------------------------------------------------- |
| `ecu_ip`                       | (Optionnel) Adresse IP de l'ECU-R. Surcharge la valeur du script. |
| `--modbus-port`                | Port Modbus TCP de l'ECU-R (défaut: 502).                         |
| `--modbus-slave`               | ID de l'esclave Modbus (défaut: 1).                               |
| `--http-host`                  | Adresse IP d'écoute du serveur HTTP (défaut: 0.0.0.0).            |
| `--http-port`                  | Port d'écoute du serveur HTTP (défaut: 8000).                     |
| `-nd`, `--no-daemon`           | Mode console. Ne se détache pas du terminal. Les logs sont écrits en stdout. Utiliser ce mode si gestion par systemd. |
| `-ll`, `--loglevel`            | Niveau de log (`debug`, `info`, `warn`, `err`).                   |
| `-lf`, `--logfile`             | (Exclusif avec -sf) Chemin vers un fichier pour les logs.         |
| `-sf`, `--syslog-facility`     | (Exclusif avec -lf) Active le logging vers syslog avec la facility donnée. |

---  
# <p align="center">**ANNEXES**</p>  

---

# annexe 1. Mise en oeuvre

## côté Shelly

C'est simple.  
Il suffit de créer un script (nommé ici "solar_power_regulator.js", d'y copier le contenu du fichier solar_power_regulator.js, et de régler les paramètres en tête du fichier.  
Lors des premiers essais, il peut être intéressant de mettre l'option DEBUG à 1.  
L'option DEBUG à 1 permet de loguer dans la console web les échanges entre le shelly et le démon.

Lorsque le fonctionnement sera stabilisé, l'option DEBUG pourra être remise à 0, et le script pourra être mis dans l'état "Run on startup"

## côté démon

Dans mon cas, il fonctionne sur un serveur odroid C4 (armbian) ; il n'y a à priori pas d'obstacle pour qu'il puisse fonctionner sur un système debian ou dérivé (Raspberry, ...).  
La  consommation CPU est négligeable.  
Déposer `solar_power_regulator.py` dans le dossier `/opt`, puis adapter les paramètres en tête du code.  
Si un firewall protège les accès réseau de votre serveur, il **faut** que le shelly puisse accéder au port http du démon (8000 par défaut, ou paramètre --http-port).  
### premiers essais 

Je conseille de faire les premiers tests en mode console : arguments "-nd" (ou ```--no-daemon```) et "--lf debug" (ou ```--loglevel debug```) pour avoir le maximum d'informations sur le fonctionnement (en stdout), sans installation préalable.  
Ceci vous permettra d'affiner des paramètres, ou de régler certaines anomalies.  
Exemple de démarrage en mode console :  
```/opt/solar_power_regulator/solar_power_regulator.py -nd  -ll debug 192.168.1.120```  
Il suffit de faire un Ctrl-C pour arrêter le fonctionnement du script.

On peut suivre l'évolution du niveau d'injection ou d'importation directement sur l'interface web du shelly. Les scripts python contenu dans le dossier modbus_tools du dépot GITHUB peuvent aider à suivre le comportement du système solaire.  

**ATTENTION** : les infos en lecture modbus (scripts read_MO.py ou read_all_MO.py) ne sont pas en temps réel : l'ECU ne raffraichi qu'une fois toutes les 5mn !!  

### installation définitive
Lorsque les essais semblent concluants, il faut procéder à l'installation du démon.  
Voici ce que j'ai fait, à adapter selon la configuration.

#### Lancement en Service (systemd)
Créer un compte dédié à ce service nommé "solar" ; ceci permet de limiter les risques de sécurité  
```sudo useradd -c "compte solar" -m -s /bin/bash solar```

Déposer le fichier solar_power_regulator.service dans /etc/systemd/system/ ; l'adapter si besoin  
* L'option `--no-daemon` peut sembler étrange, mais c'est normal : c'est le mécanisme systemd qui se charge d'exécuter en mode démon
* Si vous utilisez le syslog, il faut préciser dans la ligne de commande l'option `--loglevel debug` : c'est côté syslog que l'on choisira le niveau de log désiré

Il faut ensuite activer le service :  
```bash
sudo systemctl daemon-reload
sudo systemctl enable solar_power_regulator.service
sudo systemctl start solar_power_regulator.service
```
On peut ensuite gérer l'arrêt ou le lancement du démon ou la consultation de l'état à l'aide de la commande `service`:
* `sudo service solar start`
* `sudo service solar stop`
* `sudo service solar status`

#### paramétrage des logs
Mon système utilise rsyslog pour la système de log, comme la plupart des systèmes debian, je crois.  
On va créer le fichier /etc/rsyslog.d/solar_power_regulator.conf comme indiqué, puis redémarrer rsyslog :
```bash
sudo  cat /etc/rsyslog.d/solar_power_regulator.conf
if $programname == 'solar_regulator' then {
#    if prifilt("*.debug") then {
    if prifilt("*.info") then {
        action(type="omfile" file="/var/log/solar.log")
    }
    stop
}

sudo service rsyslog restart
```
Ici, les logs vont être écrites en niveau `info` ; pour avoir les logs en niveau `debug`, il suffit de décommenter la 2ème ligne, de commenter la 3ème, et de redémarrer le service rsyslog 

Il faut maintenant gérer la rotation du fichier de log. On va créer le fichier `/etc/logrotate.d/solar-regulator` comme indiqué, puis redémarrer le service logrotate :
```bash
# cat /etc/logrotate.d/solar-regulator
/var/log/solar_regulator.log {
    daily
    rotate 7
    missingok
    dateext
    copytruncate
    compress

sudo service logrotate restart
```

# Annexe 2. Utilitaires proposés

Deux utilitaires sont proposés pour faciliter la mise en oeuvre du système : 

## solar_power_regulator_test.py

C'est un programme python qui peut envoyer au démon un message REST comportant les informations JSON attendues ; donc simuler le fonctionnement du Shelly.  
Bien entendu, il ne faut pas l'utiliser pendant que le script Shelly fonctionne !!!

## solar_read_mqtt.py

C'est un programme python qui se connecte à un serveur MQTT et qui s'abonne aux topics `solar_power_regulator/run` et `solar_power_regulator/evt`.  
Il peut écrire des fichiers .csv contenant les informations recueillies. On peut ensuite analyser ces informations à l'aide d'un tableur.  
Il écrit en stdout les messages lus dans le topic `evt` ; optionnellement, il peut également écrire en stdout les messages lus dans le topic `run`.

## solar_read_mqtt.xlsm

C'est une feuille de calcul excel, qui permet de simplifier l'importation dans excel d'un fichier csv écrit par solar_read_mqtt.py (par exemple, solar_power_regulator_run.csv).  
Il ajoute en plus une colonne 'delta_ms' qui indique la différence en milli secondes avec l'enregistrement précédent.


# Annexe 3. Particularités du fonctionnement modbus APSystems relative à la modulation de production

Pour comprendre les algorithmes mis en oeuvre ici, il est important de bien appréhender les spécificités du fonctionnement de l'environnement APSystems relative à la modulation de production, en modbus.

On utilise ici le registre modbus **40189** lors des requêtes avec l'ECU-R. Ce registre en lecture/écriture permet de limiter la production solaire de **tous** les micro-onduleurs (MO) de l'installation.  
On va appeler ce registre `**power_limit**`. La valeur donne le **pourcentage** de limitation de production que l'on peut appliquer à chaque MO par rapport à sa limite théorique.  
En réalité, côté modbus, la valeur lue ou écrite n'est pas en "pour cent", mais en **"pour mille"**. Aussi, lorsque dans ce document on parle d'un `power_limit` à une valeur de 50%, cela correspond en fait à la valeur 500 du registre modbus.  
Il est essentiel de bien comprendre cela pour comprendre le paramètrage du démon.

Ce qu'il faut comprendre également : cette valeur `power_limit` est fixée **globalement** pour l'installation (l'ECU-R), même si côté modbus, on l'écrit pour un MO donné. En clair, si on écrit la valeur 50.0% pour un MO spécifique, **chaque MO** de l'installation va réduire sa puissance maximum de 50%.  
Lorsqu'on a une installation comme la mienne, ceci bride effectivement à coup sûr la production globale à 50% de la totalité. Mais dans mon cas, avec un MO exposé Est et 2 exposés Ouest, en fin d'après-midi, ce sont surtout les MO côté Ouest qui vont se trouver bridés.  
Un exemple : il est possible qu'à 16h, avec des MO non bridés (`power_limit` = 100.0%), le MO côté Est n'arrive plus à délivrer 50% de sa capacité, à cause de l'orientation de ses PV, alors que les MO côté Ouest arrivent à délivrer 80% de leur capacité. Si on passe le `power_limit` à 50.0%, ceci n'aura aucun impact sur le MO côté Est, alors qu'il impactera fortement les MO côté Ouest.

Les particularités relatives à `power_limit` :
* en écriture : la réaction est fiable : les MO réagissent rapidement, de manière précise
* en lecture, c'est beaucoup plus aléatoire, voire vraiment étrange

## écriture de power_limit

L'ECU répercute directement la valeur écrite en modbus vers les MO, et ceux-ci réagissent très rapidement. C'est simple, ça marche bien

## lecture du power_limit

C'est beaucoup plus étrange.  
Ce qu'il est important de savoir, c'est que l'ECU ne va pas lire l'état des MO, pour le power_limit ; il se contente de retourner une valeur qu'il conserve en mémoire.  
Mais l'ECU perd cette valeur :
* lors de son démarrage (arrêt électrique, ...)
* chaque nuit, lorsque les panneaux ont arrêté de produire le soir puis redémarrent le matin
* et parfois en journée ...  

Lorsque l'ECU ne connais pas l'état réel des MO, il retourne la valeur 300 (donc 30.0%). Donc, lorsque l'interrogation modbus retourne la valeur 300, on ne peut rien déduire de la valeur du `power_limit` en cours.  
 