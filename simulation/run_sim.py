import os
import random
import sys
import matplotlib.pyplot as plt

# Permet d'importer algo.py depuis le dossier parent
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from algo import PortfolioBrain


def run_simulation(seed: int = 42):
    rng = random.Random(seed)

    # Horloge virtuelle injectée dans PortfolioBrain (compatible avec time.monotonic)
    sim_time = 0.0
    brain = PortfolioBrain(clock=lambda: sim_time)

    history = {
        "req_id": [],
        "latency": [],
        "timeout": [],
        "success": [],
    }

    # --- SCÉNARIO DE TEST ---
    scenario = []

    # 1. Phase Calme (20 req)
    for _ in range(20):
        scenario.append((rng.uniform(0.2, 0.4), True, 0.1))

    # 2. Phase Jitter/Instable (15 req)
    for _ in range(15):
        scenario.append((rng.uniform(0.5, 1.5), True, 0.1))

    # 3. Phase Panne (5 req) - Échecs consécutifs (backoff de Karn)
    for _ in range(5):
        scenario.append((5.0, False, 0.1))

    # 4. Retour à la normale (15 req)
    for _ in range(15):
        scenario.append((rng.uniform(0.2, 0.4), True, 0.1))

    # 5. Cold Start (après 12 min = 720 s d'inactivité > MEMORY_TTL)
    scenario.append((0.5, True, 720.0))

    # 6. Suite post-réveil (10 req)
    for _ in range(10):
        scenario.append((rng.uniform(0.2, 0.4), True, 0.1))

    print(f"Simulation de {len(scenario)} requêtes en cours...")

    for i, (latency, success, wait_time) in enumerate(scenario):
        # Fait avancer l'horloge virtuelle avant la requête
        sim_time += wait_time

        # 1. L'algo décide du timeout AVANT la requête
        timeout_val = brain.get_timeout()

        # 2. On nourrit l'algo avec le résultat APRÈS la requête
        brain.update(latency, success)

        history["req_id"].append(i)
        history["latency"].append(latency if success else None)
        history["timeout"].append(timeout_val)
        history["success"].append(success)

    return history


def plot_results(data):
    plt.figure(figsize=(12, 6))

    plt.plot(data["req_id"], data["latency"], "bo-", label="Latence Réelle", alpha=0.5, markersize=4)
    plt.plot(data["req_id"], data["timeout"], "r-", linewidth=2, label="Timeout Calculé (Jacobson/Karn)")

    failures_x = [i for i, s in zip(data["req_id"], data["success"]) if not s]
    failures_y = [data["timeout"][i] for i in failures_x]
    if failures_x:
        plt.scatter(failures_x, failures_y, color="red", marker="X", s=100, zorder=10, label="Timeout (Échec)")

    plt.title("Simulation : Adaptation dynamique du Timeout")
    plt.xlabel("Numéro de la requête")
    plt.ylabel("Temps (secondes)")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)

    output_path = os.path.join(current_dir, "resultat_graphique.png")
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()
    print(f"Graphique généré avec succès : {output_path}")


if __name__ == "__main__":
    data = run_simulation()
    plot_results(data)