import argparse
import requests
import json
import sys

# --- Paramètres de test (vous pouvez les ajuster ici) ---
THRESHOLD_HIGH = -200 # Seuil haut d'injection (valeur négative, ex: -200W)
THRESHOLD_LOW = -10  # Seuil bas d'injection (valeur négative, ex: -10W)

def main():
    parser = argparse.ArgumentParser(description="Script de test pour le démon de régulation de puissance solaire.")
    parser.add_argument('daemon_ip', type=str, default="127.0.0.1", help="Adresse IP du démon (défaut 127.0.0.1")
    parser.add_argument("-p", "--daemon_port", type=int, default=8000, help="Port TCP du démon (défaut: 8000)")
    parser.add_argument("-ip", "--injection_power", type=int, required=True, help="Injection simulée du réseau en W (ex: +700 pour injection, -100 pour importation)")
    parser.add_argument("-sp", "--solar_power", type=int, default=-1, help="Production solaire simulée en W")

    args = parser.parse_args()

    daemon_url = f"http://{args.daemon_ip}:{args.daemon_port}/regulate"
    
    payload = {
        "injection-power": arg.injection_power,
        "solar-power": arg.solar_power,
    }

    print(f"Tentative d'envoi d'une requête POST à {daemon_url} avec les données: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(daemon_url, json=payload, timeout=10) # Timeout de 10 secondes
        response.raise_for_status() # Lève une exception pour les codes d'état HTTP 4xx/5xx

        print("\n--- Réponse du Démon ---")
        print(f"Statut HTTP: {response.status_code}")
        
        try:
            json_response = response.json()
            print("Contenu JSON de la réponse:")
            print(json.dumps(json_response, indent=2))

        except json.JSONDecodeError:
            print("Réponse du démon n'est pas un JSON valide.")
            print(f"Contenu brut: {response.text}")

    except requests.exceptions.ConnectionError as e:
        print(f"ERREUR DE CONNEXION: Impossible de se connecter au démon à {daemon_url}. Est-il en cours d'exécution ?")
        print(f"Détails de l'erreur: {e}")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"ERREUR DE DÉLAI: Le démon à {daemon_url} n'a pas répondu à temps (timeout de 10 secondes).")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ERREUR LORS DE LA REQUÊTE HTTP: {e}")
        print(f"Statut HTTP: {response.status_code}")
        print(f"Réponse: {response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"UNE ERREUR INATTENDUE S'EST PRODUITE: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()