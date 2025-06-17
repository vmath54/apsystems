################# Retour d'expérience sur des essais modbus avec du matériel APSystems ###################

Ce retour d'expérience fait suite à une série d'essais de lecture/écriture modbus faite avec un ECU-R et des micro-onduleurs (MO) DS3 880W, sur plusieurs jours.

Ce qu'il faut savoir en préalable : 
- les MO fonctionnent en interne grace au courant électrique fournie par les panneaux solaires (PV) et pas à l'aide du courant électrique de l'habitation.
- l'ECU communique avec les MO à l'aide de signaux radio, en protocole zigbee.
- lorsque les PV ne produisent plus rien (la nuit, par exemple), il n'y a plus de communication entre l'ECU et les MO puisquent ceux-ci ne sont plus alimentés électriquement.

En ce qui concerne le modbus :

On interroge l'ECU en protocole modbus, pas les MO
Lorsqu'on lance une commande modbus vers un ECU, on précise l'ID d'un esclave ; cet ID qu'on paramètre (de 1 à 32, je crois) correspond à un MO précis dans l'installation.
PAS DE CONFUSION : l'ECU ne communique pas en modbus avec le MO, et on ne peut pas communiquer directement avec les MO

lecture des paramètres de production
------------------------------------

La lecture des paramètres de production fonctionne bien en modbus.

Avec un bémol : l'ECU interroge les MO toutes les 5 mn. L'ECU connait l'heure exacte (NTP) ; il interroge aux minutes précises, plus une trentaine de minutes.
Par exemple, on a les infos vers h + 30s, h + 5mn + 30s, h + 10mn + 30s, ...
Si on souhaite récupérer les informations pour traitement, il est conseillé d'utiliser un cron comme celui-ci :
1,6,11,16,21,26,31,36,41,46,51,56 * * * *
C'est ce qui permettra d'avoir des informations les plus fraiches, sans avoir à faire une interrogation par minute, qui est inutile, et qui peut destabiliser l'ECU.

paramètres en lecture/écriture
------------------------------

Quelques registres sont accessibles en lecture/écriture. Ils permettent d'arrêter, de redémarrer ou de limiter la production.

une chose importante, qui n'est pas évidente au départ : lorsqu'on modifie l'un de ces registres, on pourrait croire qu'on le modifie pour un MO précis, mais non ; quelque soit l'ID utilisé, ca modifie la valeur de tous les MO de l'installation.

Voici les registres modifiables :

- 40188 (9CFC) : Conn. Permet d'arrêter (valeur 0) ou de relancer (valeur 1) la production
- 40189 (9CFD) : WMaxLimPct. Permet de limiter la puissance maxi du MO.
- 40193 (9D01) : WMaxLim_Ena. Permet d'activer (valeur 1) ou de désactiver (valeur 0) la limitation de puissance maxi

Pour mieux comprendre les valeurs de WMaxLimPct : ca correspond à un pourcentage relative à la puissance maxi du MO. Mais il faut lui appliquer un coefficient multiplicatif de 0.1, donc il faut diviser la valeur par 10. Par exemple, WMaxLimPct à 500 correspond à une puissance limitée à 50% de la puissance maxi du MO.
Pour un DS3 de puissance maxi de 880W, une valeur de WMaxLimPct à 500 limite la production du MO à 440W.

Dans la suite de ce texte, je nommerais power_limit la valeur de WMaxLimPct divisée par 10 ; ça sera donc le réel pourcentage de limitation du MO.
Et je nommerais power_limit_ena le registre WMaxLim_Ena

ATTENTION : la lecture de ces 2 registres est très déroutante dans l'installation APSystems.

Coté écriture, c'est simple :
- si power_limit_ena est à 1 : lorsqu'on modifie la valeur de power_limit, la puissance maxi de tous les MO de l'installation s'adapte à cette valeur. C'est quasi-immédiat, ça fonctionne très bien.
- si on passe power_limit_ena à 0, la puissance maxi des MO revient à la puissance maxi possible ; donc à 100%, quelque soit la valeur de power_limit lue
- si on passe power_limit_ena à 1, la puissance maxi des MO prend la valeur de power_limit lue
- lorsque power_limit_ena a la valeur 0, une modification de power_limit ne change rien : la production restera au maximum.

Coté lecture, c'est beaucoup plus bizarre :
- lorsqu'on met en marche pour la première fois l'installation, la lecture donne power_limit_ena = 1 et power_limit = 30% ; alors que l'installation fonctionne à 100%
- si on arrête électriquement l'ECU et qu'on le redémarre, la lecture donne toujours power_limit_ena = 1 et power_limit = 30%, quelque soit la valeur d'avant. En réalité, les MO ont conservé l'ancienne valeur de power_limit ; il n'y a donc pas nécessairement correspondance entre la valeur affichée et la valeur réellement prise en compte par le MO.
- même phénomène lorsqu'on passe d'un jour à l'autre ; donc lorsque les MO s'arrêtent de fonctionner au coucher du soleil, et repartent au lever.

On peut donc facilement faire de mauvaises interprêtations, car la lecture des ces infos ne correspond pas nécessairement à celle mémorisée et prise en compte par les MO.

Ce que j'en déduis, pour les registres en lecture/écriture
----------------------------------------------------------

Je n'ai pas creusé le fonctionnement du registre Conn, qui permet d'arrêter la production ; je ne serais pas surpris que l'ECU se contente d'envoyer un power_limit à 0% lorsqu'on le passe à 0 ; et la valeur affichée de power_limit lue lorsqu'on le passe à 1 (ou 100% si power_limit_ena est à 0)

- ces paramètres sont globaux à l'installation, ils sont mémorisés dans l'ECU (certain)
- ils fonctionnent bien, en écriture
- il n'y a pas de retour d'information des MO vers l'ECU concernant ces paramètres
- l'ECU se contente de mémoriser ces infos, quand elles sont écrites en modbus. Il ne restitue en lecture que l'état de sa mémoire, pas l'état réel de l'installation
- je suppose que les MO ne recoivent et ne mémorisent que le paramètre power_lim. Il est envoyé à chaque changement d'un des 3 registres en modbus, et uniquement à ce moment.
- quand l'ECU n'a pas d'info (redémarrage, le matin, ...), par défaut, il indique en lecture power_limit = 30%, power_limit_ena = 1, Conn = 1 ; alors que la valeur power_limit ne correspond pas nécessairement à celle mémorisée par les MO (celle de la veille), et que les MO ne gèrent pas les 2 autres (certain)
- le registre power_limit_ena, en écriture, n'est utilisé que lors d'un changement par commande modbus :
   . si 0, l'ECU envoie un ordre de limitation de puissance à 100%, quelque soit la valeur de power_limit lue
   . si 1, l'ECU envoie un ordre de limitation de puissance égale à la valeur power_lim qu'il a en mémoire (donc la valeur lue). 
- je suppose que le registre Conn fonctionne de la même manière ; pas testé.

Conseil 
-------

Si vous souhaitez pouvoir moduler la puissance de production de votre installation en modbus, il suffit de n'intervenir que sur la valeur de power_limit : on peut faire varier celle-ci de 0 à 100%, il n'y a donc pas besoin d'intervenir sur les 2 autres registres, qui apportent un niveau de complexité supplémentaire.