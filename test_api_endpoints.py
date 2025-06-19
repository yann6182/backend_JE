"""
Script pour tester tous les endpoints de l'API DPGF
"""
import requests
import sys
import json
from pathlib import Path

API_BASE_URL = "http://localhost:8000/api/v1"

def test_endpoint(url, method="GET", data=None, files=None):
    """Test un endpoint API et affiche le résultat"""
    print(f"\n--- Test de {method} {url} ---")
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data, files=files)
        elif method == "DELETE":
            response = requests.delete(url)
        else:
            print(f"Méthode {method} non supportée")
            return
        
        status = response.status_code
        print(f"Statut: {status}")
        
        if status >= 400:
            print(f"Erreur: {response.text}")
        else:
            if len(response.text) > 1000:
                print("Réponse (tronquée):", response.text[:1000] + "...")
            else:
                try:
                    # Tenter de formater la réponse JSON
                    formatted_json = json.dumps(response.json(), indent=2, ensure_ascii=False)
                    print("Réponse:", formatted_json)
                except:
                    print("Réponse:", response.text)
            
    except requests.exceptions.ConnectionError:
        print(f"Erreur de connexion: impossible de se connecter à {url}")
        print("Le serveur API est-il en cours d'exécution?")
    except Exception as e:
        print(f"Erreur lors du test de l'endpoint: {e}")

def test_all_endpoints():
    """Test tous les endpoints API connus"""
    
    # --- CLIENTS ---
    test_endpoint(f"{API_BASE_URL}/clients")
    
    # --- DPGF ---
    test_endpoint(f"{API_BASE_URL}/dpgf")
    
    # Si nous avons au moins un DPGF
    try:
        response = requests.get(f"{API_BASE_URL}/dpgf")
        if response.status_code == 200 and response.json():
            dpgf_id = response.json()[0]["id_dpgf"]
            print(f"\n--- Tests avec DPGF ID={dpgf_id} ---")
            
            test_endpoint(f"{API_BASE_URL}/dpgf/{dpgf_id}")
            test_endpoint(f"{API_BASE_URL}/dpgf/{dpgf_id}/structure")
    except Exception:
        print("Impossible de tester les endpoints nécessitant un ID de DPGF")
    
    # --- LOTS ---
    test_endpoint(f"{API_BASE_URL}/lots")
    
    # --- SECTIONS ---
    test_endpoint(f"{API_BASE_URL}/sections")
    
    # --- ÉLÉMENTS D'OUVRAGE ---
    test_endpoint(f"{API_BASE_URL}/element_ouvrages")
    test_endpoint(f"{API_BASE_URL}/element_ouvrages/with_sections")
    test_endpoint(f"{API_BASE_URL}/element_ouvrages/complete")

if __name__ == "__main__":
    print("Test de tous les endpoints API...")
    test_all_endpoints()
    print("\nTests terminés.")
