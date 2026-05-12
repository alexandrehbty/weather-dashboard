import sys
import os
import time
import random
import matplotlib.pyplot as plt

# --- BLOC MAGIQUE POUR L'IMPORT ---
# Cela permet d'aller chercher 'algo.py' dans le dossier parent (..)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Maintenant on peut importer votre classe normalement
from algo import PortfolioBrain 

def run_simulation():
    brain = PortfolioBrain()
    
    # Stockage des données
    history = {
        "req_id": [],
        "latency": [],
        "timeout": [],
        "success": []
    }
    
    # --- SCÉNARIO DE TEST ---
    scenario = []
    
    # 1. Phase Calme (20 req)
    for _ in range(20): scenario.append((random.uniform(0.2, 0.4), True, 0.1))
        
    # 2. Phase Jitter/Instable (15 req)
    for _ in range(15): scenario.append((random.uniform(0.5, 1.5), True, 0.1))
        
    # 3. Phase Panne (5 req) - Latence de 5s qui causera un échec
    for _ in range(5): scenario.append((5.0, False, 0.1))
        
    # 4. Retour à la normale (15 req)
    for _ in range(15): scenario.append((random.uniform(0.2, 0.4), True, 0.1))
        
    # 5. Cold Start (Après 12 min d'inactivité)
    scenario.append((0.5, True, 720)) 
    
    # 6. Suite post-réveil
    for _ in range(10): scenario.append((random.uniform(0.2, 0.4), True, 0.1))

    print(f"Simulation de {len(scenario)} requêtes en cours...")
    
    # Initialisation du temps
    brain.last_request_time = time.time()

    for i, (latency, success, wait_time) in enumerate(scenario):
        # Simulation du temps qui passe (pour tester le TTL)
        if wait_time > 100:
            # On force l'horloge interne vers le passé pour simuler l'inactivité
            brain.last_request_time = time.time() - wait_time - 1
        
        # 1. L'algo décide du timeout AVANT la requête
        timeout_val = brain.get_timeout()
        
        # 2. On nourrit l'algo avec le résultat (APRÈS la requête)
        brain.update(latency, success)
        
        # Enregistrement
        history["req_id"].append(i)
        history["latency"].append(latency if success else None)
        history["timeout"].append(timeout_val)
        history["success"].append(success)

    return history

def plot_results(data):
    plt.figure(figsize=(12, 6))
    
    # Latence réelle (Points bleus)
    plt.plot(data["req_id"], data["latency"], 'bo-', label='Latence Réelle', alpha=0.5, markersize=4)
    
    # Timeout Calculé (Ligne rouge)
    plt.plot(data["req_id"], data["timeout"], 'r-', linewidth=2, label='Timeout Calculé (Votre Algo)')
    
    # Échecs (Croix rouges)
    failures_x = [i for i, s in zip(data["req_id"], data["success"]) if not s]
    failures_y = [data["timeout"][i] for i in failures_x]
    if failures_x:
        plt.scatter(failures_x, failures_y, color='red', marker='X', s=100, zorder=10, label='Timeout (Echec)')

    plt.title("Simulation : Adaptation dynamique du Timeout")
    plt.xlabel("Numéro de la requête")
    plt.ylabel("Temps (secondes)")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.5)
    
    # Sauvegarde dans le dossier simulation
    output_path = os.path.join(current_dir, 'resultat_graphique.png')
    plt.savefig(output_path)
    print(f"Graphique généré avec succès : {output_path}")

if __name__ == "__main__":
    data = run_simulation()
    plot_results(data)