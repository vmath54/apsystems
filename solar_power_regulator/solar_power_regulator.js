// solar_power_regulator.js
// VERSION 2.1 - Correction pour compatibilité avec le démon V2

const CONFIG = {
  DEBUG: 1,
  MODBUS_DAEMON_URL: "http://192.168.1.147:8000/regulate",

  // --- Configuration des capteurs ---
  GRID_SENSOR_ID: "em1:0",      // Capteur mesurant l'échange avec le réseau
  SOLAR_SENSOR_ID: "em1:1",     // Capteur mesurant la production solaire (laisser vide "" si non utilisé)
  GRID_REVERSE_MEASURE: true,   // Mettre à true pour que l'injection soit positive.

  // --- Configuration des intervalles ---
  DEFAULT_REQUEST_INTERVAL_S: 5,  // Intervalle par défaut (en secondes) entre les requêtes au démon
  PAUSE_ON_ERROR_S: 60,           // Pause (en secondes) en cas d'erreur de communication avec le démon

  // --- Configuration du mode nuit ---
  NIGHT_MODE_ENABLE: true,        // Activer la pause nocturne
  NIGHT_MODE_START_H: 22,         // Heure de début de la pause (22h)
  NIGHT_MODE_END_H: 6,            // Heure de fin de la pause (6h)
  NIGHT_MODE_INTERVAL_S: 900,     // Intervalle des requêtes pendant la nuit (15 minutes)
};

// --- Variables d'état ---
let requestTimer = null;
let nextRequestDelayS = CONFIG.DEFAULT_REQUEST_INTERVAL_S;

function logDebug(message) {
  if (CONFIG.DEBUG === 1) {
    console.log("[Regulator] " + message);
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
    "delay_request": nextRequestDelayS,
  };

  const requestParams = {
    url: CONFIG.MODBUS_DAEMON_URL,
    body: payload,
    timeout: 10,
  };

  logDebug("Envoi des données: " + JSON.stringify(payload));
  
  Shelly.call("HTTP.POST", requestParams, function (response, error_code, error_message) {
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
  });
}

function rescheduleRequest(delayS) {
  if (requestTimer) Timer.clear(requestTimer);
  nextRequestDelayS = delayS;
  requestTimer = Timer.set(delayS * 1000, false, regulate);
  logDebug("Prochaine requête programmée dans " + delayS + " secondes.");
}

logDebug("Script de régulation solaire v2.1 démarré.");
regulate();