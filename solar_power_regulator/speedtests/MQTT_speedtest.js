// envoi rapide de messages MQTT, pour tests
// vers le topic solar_power_regulator/run
// les infos d'injection d'énergie et de production solaires sont envoyées, dans un format compatible avec solar_read_mqtt.py

const DEBUG = 0;

// --- Configuration MQTT ---
const mqttConfig = Shelly.getComponentConfig("MQTT"); // Get mqtt config
const mqttTopic = "solar_power_regulator/run";

// --- Configuration des capteurs ---
const GRID_SENSOR_ID = "em1:0";      // Capteur mesurant l'échange avec le réseau
const SOLAR_SENSOR_ID = "em1:1";     // Capteur mesurant la production solaire (laisser vide "" si non utilisé)
const GRID_REVERSE_MEASURE = true;   // Mettre à true pour que l'injection soit positive.

// --- autre Conf ---
const  intervalTimer = 500;         // intervalle des mesures ; en millisecondes

function logDebug(message) {
  if (DEBUG === 1) {
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

function timerHandler(user_data)
{
  let injectionPower = getPower(GRID_SENSOR_ID);
  if (GRID_REVERSE_MEASURE) {
    injectionPower *= -1;
  }
  
  let solarPower = getPower(SOLAR_SENSOR_ID);
  
  let payload = {
    "solar": parseInt(solarPower),
    "injection": parseInt(injectionPower),
    "power_limit" : -1
  }
  
  payload2publish = JSON.stringify(payload);
  logDebug(payload2publish);
  MQTT.publish(mqttTopic, payload2publish , 0, false);
}

logDebug("--- Start ---. topic MQTT = " + mqttTopic);
Timer.set(intervalTimer, true, timerHandler, null);