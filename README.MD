Ce dépôt github contient différents utilitaires relatifs aux micro onduleurs (MO) APSystems.
Testés avec une passerelle ECU-R et des MO DS3 (880W).

A noter que les passerelles ECU-R dont le numéro de série commencent par 2160xxxxxxxx n'implémentent pas le modbus, et ne proposent pas d'interface web.
Ma passerelle a un numéro de série en 2162xxxxxxxx

Le dossier 'modbus_tools' contient des utilitaires écrits en python, qui permettent d'interroger l'ECU en protocole modbus - sunspec ; également de modifier certains registres.
Ces utilitaires ne sont pas optimisés ; à utiliser pour tests.

Le dossier 'solar_power_regulator' propose un système permettant de limiter l'injection dans le réseau.  
Il s'appuie sur un démon (en python) qui fonctionne sur un système debian ou dérivé, et d'un script javascript qui s'exécute sur un Shelly Pro EM.

