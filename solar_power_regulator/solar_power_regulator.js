// solar_power_regulator.js
// envoie de manière régulière en POST HTTP les informations d'import/export d'électricité vers le réseau, et éventuellement les infos de production solaire au démon solar_power_regulator.py
//
// les infos envoyées dans le POST HTTP (format JSON) sont : { "injection_power": <valeur_injection_enWatts>, "solar_power": <valeur_production_enWatts> }
//      <valeur_injection_enWatts> est positive si injection, négative si importation
//      <valeur_production_enWatts> est positive ou nulle si cette info est transmise, ou -1 si pas disponible
//
// les infos retournées lors de cet appel POST sont également en format JSON : 
//     {  "return_code": <return_code>, "message": <message>, ""power_limit_value": <power_limit>, "power_limit_increment": <increment>, "sensor_read_interval": <interval }
//        return_code. 0 : le traitement s'est bien déroulé, power_limit a été calculé et écrit
//                     1 : Comme 0, mais le power_limit lu était différent du power_limit mémorisé. C'est un warning
//                     2 : Une erreur de communication modbus a eu lieu, en lecture ou en écriture. power_limit n'a pas pu être écrit
//                     3 : Erreur récurrente de communication modbus. Par exemple, 5 erreurs consécutives
//                     9 : Autre erreur
//        power_limit_value : la nouvelle valeur de power_limit calculée par le démon. Par exemple, 20.5.
//        power_limit_increment : valeur de l'incrément (positif) ou du décrément (négatif) appliqué au power-limit, en pourcentage. Par exemple, -0.5 siginfie un décrément de 0.5% du power_limit.
//                                Si valeur -1, il y a eu une erreur, power_limit n'a pas pu être calculé ou écrit
//        sensor_read_interval : le délai demandé par le démon pour recevoir la prochaine mesure. Si la valeur est -1, alors le script shelly applique le délai par défaut DEFAULT_REQUEST_INTERVAL_S
//
// IPORTANT : seule la valeur de sensor_read_interval est interprêtée par ce script. LEs autres valeurs servent au debug (CONFIG.DEBUG = 1)


const CONFIG = {
  DEBUG: 0,
  MODBUS_DAEMON_URL: "http://192.168.1.147:8000/regulate",

  // --- Configuration des capteurs ---
  GRID_SENSOR_ID: "em1:0",      // Capteur mesurant l'échange avec le réseau
  SOLAR_SENSOR_ID: "em1:1",     // Capteur mesurant la production solaire (laisser vide "" si non utilisé)
  GRID_REVERSE_MEASURE: true,   // Si nécessaire, mettre à true pour que la valeur d'injection trasmise soit positive

  // --- Configuration des intervalles ---
  DEFAULT_REQUEST_INTERVAL_S: 5,  // Intervalle par défaut (en secondes) entre les requêtes au démon
  PAUSE_ON_ERROR_S: 60,           // Pause (en secondes) en cas d'erreur de communication avec le démon

  // --- Configuration du mode nuit ---
  //     Permet de réduite fortement le nombre de requetes la nuit
  NIGHT_MODE_ENABLE: true,        // Activer la pause nocturne
  NIGHT_MODE_START_H: 22,         // Heure de début de la pause (22h)
  NIGHT_MODE_END_H: 6,            // Heure de fin de la pause (6h)
  NIGHT_MODE_INTERVAL_S: 900,     // Intervalle des requêtes pendant la nuit (15 minutes)
};

// --- Variables d'état ---
let requestTimer = null;

function logDebug(message) {
  if (CONFIG.DEBUG === 1) {
    console.log(message);
  }
}

function getPower(sensorId) {
  if (!sensorId) return null;
  let status = Shelly.getComponentStatus(sensorId);
  if (status && typeof status.act_power !== 'undefined') {
    return status.act_power;
  }
  logDebug("Erreur: Impossible de lire le statut pour le capteur " + sensorId);
  return null;
}

function regulate() {
  if (CONFIG.NIGHT_MODE_ENABLE) {
    const currentHour = new Date().getHours();
    if (currentHour >= CONFIG.NIGHT_MODE_START_H || currentHour < CONFIG.NIGHT_MODE_END_H) {
      logDebug("Mode nuit actif. Prochaine vérification dans " + CONFIG.NIGHT_MODE_INTERVAL_S + "s.");
      rescheduleRequest(CONFIG.NIGHT_MODE_INTERVAL_S);
      return;
    }
  }

  let injectionPower = getPower(CONFIG.GRID_SENSOR_ID);
  if (injectionPower === null) {
    rescheduleRequest(CONFIG.PAUSE_ON_ERROR_S);
    return;
  }

  if (CONFIG.GRID_REVERSE_MEASURE) {
    injectionPower *= -1;
  }

  let solarPower = getPower(CONFIG.SOLAR_SENSOR_ID) || -1;

  const payload = {
    "injection_power": parseInt(injectionPower),
    "solar_power": parseInt(solarPower),
  };

  const requestParams = {
    method: "POST",
    url: CONFIG.MODBUS_DAEMON_URL,
    headers: {"Content-Type": "application/json"},
    body: payload,
    timeout: 5,
  };

  logDebug("Envoi des données: " + JSON.stringify(payload));
  
  Shelly.call("http.request", requestParams, 
    function (response, error_code, error_message) {
      let nextDelay = CONFIG.DEFAULT_REQUEST_INTERVAL_S;
      if (error_code !== 0) {
        logDebug("Erreur HTTP: " + error_code + ": " + error_message);
        nextDelay = CONFIG.PAUSE_ON_ERROR_S;
      } else {
        try {
          const responseBody = JSON.parse(response.body);
          logDebug("Réponse reçue: " + JSON.stringify(responseBody));
          if (responseBody.sensor_read_interval && responseBody.sensor_read_interval > 0) {
            nextDelay = responseBody.sensor_read_interval;
          }
        } catch (e) {
          logDebug("Erreur parsing JSON: " + e.toString());
          nextDelay = CONFIG.PAUSE_ON_ERROR_S;
        }
      }
      rescheduleRequest(nextDelay);
    }
  );
}

function rescheduleRequest(delayS) {
  // if (requestTimer) Timer.clear(requestTimer);   // a priori, ne sert à rien : on cree un Timer à chaque cycle
  requestTimer = Timer.set(delayS * 1000, false, regulate);
  logDebug("Prochaine requête programmée dans " + delayS + " secondes.");
}

logDebug("Script de régulation solaire démarré.");
regulate();