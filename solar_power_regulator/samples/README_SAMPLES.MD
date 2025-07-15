# Exemple de fonctionnement de solar_power_regulator

Les paramètres du démon restent encore à affiner. Néammoins, les informations suivantes donnent une idée du fonctionnement du mécanisme.  
A la fois de solar_power_regulator, et aussi de la réaction de l'ECU et des MO APSystems.

Traces prises lors d'un après-midi assez ensoleillé, entre 16h10 et 18h10, avec un lave-linge en fonctionnement.  
Le seuil d'injection paramétré pour le système est 0 à 30W.  
Voici les fichiers cvs produits par solar_read_mqtt.py et un rendu graphique produit par un outil domotique (jeedom) qui exploite le topic `solar_power_regulator`.  
Il est possible bien sur de retraiter les fichiers csv avec un tableur pour affiner.

* solar_power_regulator_16h10-18h10_run.csv : les informations de production pendant la plage horaire
* solar_power_regulator_16h10-18h10_evt.csv : les évenements pendant cette plage horaire
* solar_power_regulator_16h10-18h10.png : le graphe pour la période
* solar_power_regulator_17h36-17h47.png : un zoom du graphe sur une période précise, où on constate des oscillations.

Concernant les graphiques, les couleurs sont les suivantes :
* bleu : l'injection en W. Positif si injection, négatif si importation
* orange : la production solaire en 
* vert : power_limit, en %

Les choses remarquables sont les suivantes :  
## algos FAST_RISE et FAST_DROP
* 16:38:35: la consommation de l'habitation passe subitement de 299W à 2318W ; probablement la résistance électrique du lave-linge.  
La première réaction du système est d'appliquer l'algo par seuil, avec un passage de power_limit de 9.5% à 29.5% ; le délai de la requete suivante est fixé à 5s
   * 16:38:40 : déclenchement de l'algo **FAST_RISE**. power_limit passe de 29.5% à 100.0% ; le délai est fixé à 10s
   * 16.39.01 : les MO donnent à peu près toute la puissance délivrée par les panneaux. Il a fallu environ 25 secondes pour y arriver  
   * jusque 16:49:36 : il y a importation de courant, la consommation de la maison étant supérieure à la production solaire. power_limit reste à 100.0%
* 16:49:41 : la consommation de l'habitation passe subitement de 2200W à 230W  
La première réaction du système est d'appliquer l'algo par seuil, avec un passage de power_limit de 100.0% à 80.0% ; le délai de la requete suivante est fixé à 5s
   * 16:49:46 : déclenchement de l'algo **FAST_DROP**. power_limit passe de 80.0% à 8.6% ; le délai est fixé à 10s
   * 16:49:56 : retour à l'algo par seuil. Le système continue à injecter, power_limit passe à 1.0% ; donc le plus bas autorisé.
   * power_limit reste à 1.0% jusque 16:50:12 ; la production solaire baisse de 1696W à 199W. Il a fallu environ 25 secondes pour y arriver
   * il y a ensuite quelques oscillations pour arriver à une valeur correcte d'injection.
   
**Globalement, on constate un délai d'une vingtaine de secondes pour que les MO puissent passer d'une production très faible à la production maximale, et inversement.**
   
## oscillations
Sur le graphe principal (16h10-18h10), on constate des oscillations de l'injection par moment.  
On va zoomer sur une de ces périodes ; ici, entre 17:41 et 17:44. Voir solar_power_regulator_17h36-17h47.png
* 17:42:12 : jusque la, la régulation est stable : l'injection est de 23W, le power_limit est fixé à 12.5% depuis 17:40:48
* 17:42:17 : la consommation de l'habitation passe subitement de 344W à 1121W ; la production solaire est 322W. pas suffisant pour déclencher l'algo FAST_DROP, on applique l'algo seuils, avec power_limit = 32.5%
* 17:42:22 : production solaire 438W, conso maison 302W, injection 138W. L'algo passe power_limit à 27.5%
* 17:42:27 : production solaire 748W, conso maison 302W, injection 452W. L'algo passe power_limit à 17.5%
* jusque 17:42:43 : la conso maison reste aux alentours de 300W. l'algo seuil baisse progressivement le power_limit de 32.5% à 1.5% ; la production solaire baisse pendant ce temps à 404W, puis 140W à 17:42:48
* 17:42:48 : la conso maison est 294W. On importe 154W, parce que power_limit est trop bas (1.5%). Il est passé à 6.5% par l'algo seuil.
* jusque 17:42:59 : l'algo seuil remonte power_limit par pas de 5%, puis pas de 1% à 17:43:26. La valeur de power_limit est de 8.5%, l'injection est de 26W
* il y a ensuite une stabilisation de l'injection au seuilk désiré, avec un power_limit entre 12.0% et 13.0%
   
