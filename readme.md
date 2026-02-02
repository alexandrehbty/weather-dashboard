# 🌦️ GeoMeteo — Architecture Résiliente & Algorithmique

![CI Status](https://github.com/TON_USERNAME/TON_REPO/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-Senior_Setup-green.svg)
![Algorithm](https://img.shields.io/badge/Algo-Jacobson%2FKarn-orange)
![Status](https://img.shields.io/badge/Status-Production_Ready-success)

> **Démonstration technique :** Conception d'un backend météo résilient ("Crash-Proof"), capable d'adapter ses timeouts en temps réel selon la congestion réseau. Optimisé pour les environnements contraints (Render Free Tier, 512Mo RAM).

🔗 **Démo Live :** [Insérer le lien de ton application Render ici]

---

## 🎯 Philosophie du Projet

Ce projet dépasse le simple wrapper d'API. C'est une **preuve de concept (PoC)** sur la fiabilité des systèmes distribués.
Le défi technique : **"Comment garantir une UX fluide et un Backend stable alors que l'infrastructure sous-jacente (Cloud Free Tier) et les API tierces sont imprévisibles ?"**

### Points forts techniques :
1.  **Intelligence Réseau (TCP-like) :** Algorithme adaptatif pour calculer les timeouts (fini les valeurs arbitraires).
2.  **Thread Safety & Concurrence :** Gestion des verrous (`threading.Lock`) pour supporter les workers Gunicorn.
3.  **UX Optimisée :** Autocomplétion avec Debounce, cartes interactives et feedback visuel immédiat.

---

## 🧠 Le "Cerveau" : Algorithme Jacobson/Karn (`geometeo_algo_2.py`)

C'est le cœur du système. Au lieu d'utiliser un timeout statique (ex: 5s), l'application écoute le réseau et apprend.

### Implémentation technique :
Le module `PortfolioBrain` implémente les standards **RFC 6298** (TCP) adaptés au niveau applicatif :

* **SRTT (Smoothed Round Trip Time) :** Moyenne glissante de la latence.
* **RTTVAR (Round Trip Time Variation) :** Calcul du Jitter (instabilité).
* **Algorithme de Karn :** En cas d'échec (timeout/erreur), on ignore la mesure et on applique un *Backoff Exponentiel* (doublement du timeout) pour laisser le réseau respirer.
* **Soft Decay (Gestion de l'inactivité) :** Si l'application n'est pas sollicitée pendant 10 minutes, l'algorithme augmente artificiellement la variance (`RTTVAR`) pour réagir prudemment au "réveil" (Cold Start).
* **Thread Safety :** Utilisation de `threading.Lock()` pour garantir l'intégrité des calculs statistiques dans un environnement multi-threadé (Gunicorn).

---

## 🛠️ Stack & Architecture

### Backend (Python/Flask)
* **Entry Point :** `app.py` (Architecture Flask Factory simplifiée).
* **Resilience HTTP :** `requests.Session` avec `HTTPAdapter` pour gérer les retries automatiques (Retry strategy : 2 essais, Backoff factor 0.4).
* **Sécurité :**
    * **HTTPS Enforced :** Appels API OpenWeather sécurisés.
    * **Rate Limiting :** Protection in-memory via `Flask-Limiter` pour éviter les abus.
    * **Headers HTTP :** HSTS, X-Frame-Options, CSP.
* **Caching Stratégique :** Cache LRU (Least Recently Used) en mémoire avec TTL court (120s) pour économiser les quotas API sans saturer la RAM.

### Frontend (Vanilla JS)
* **Single Page :** `index.html` servie par Flask (Jinja2).
* **Autocomplétion :** Moteur de recherche ville asynchrone avec **Debouncing** (300ms) pour limiter les appels réseau inutiles.
* **Cartographie :** Intégration Leaflet.js dynamique.
* **UX/UI :** Design Responsive, gestion des états de chargement (`aria-busy`), et accessibilité (a11y).

---

## 🚀 Installation & Démarrage Local

Prérequis : Python 3.9+

1.  **Cloner le dépôt**
    ```bash
    git clone [[https://github.com/votre-username/votre-repo.git](https://github.com/votre-username/votre-repo.git)]
    cd votre-repo
    ```

2.  **Créer l'environnement virtuel**
    ```bash
    # Mac/Linux
    python3 -m venv .venv
    source .venv/bin/activate

    # Windows
    python -m venv .venv
    .venv\Scripts\activate
    ```

3.  **Installer les dépendances**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration (.env)**
    Créez un fichier `.env` à la racine :
    ```ini
    API_KEY=votre_cle_api_openweather
    FLASK_DEBUG=1
    # Paramètres avancés (Defaults robustes inclus dans le code)
    CACHE_TTL_S=120
    ```

5.  **Lancer le serveur**
    ```bash
    python app.py
    ```
    Accédez à `http://localhost:5000`

---

## 🧪 Qualité & Tests (Quality Assurance)

Le projet intègre une suite de tests unitaires automatisés (`unittest`) couvrant l'algorithme de congestion et les endpoints API critiques.

**Rapport de couverture (Coverage Report) :**
```text
Name                  Stmts   Miss  Cover
-----------------------------------------
algo.py                  37      5    86% <-- Core Algorithm Logic
app.py                  221     64    71% <-- API Endpoints
tests\test_suite.py     112      1    99%
-----------------------------------------
TOTAL                   370     70    81% <-- Production Grade

---

## ⚙️ Déploiement (Production / Render)

Le projet est configuré pour un déploiement "Cloud Native".

* **Fichiers critiques :**
    * `app.py` : Le serveur web.
    * `requirements.txt` : Les dépendances (gunicorn, flask, requests...).
* **Start Command (Render) :**
    ```bash
    gunicorn app:app --workers 1 --threads 4 --timeout 60
    ```
    *Note : Utilisation des threads plutôt que des workers multiples pour économiser la RAM (512 Mo limit).*

---

## 📂 Structure du projet

/
├── .github/
│   └── workflows/
│       └── ci.yaml          # Pipeline d'Intégration Continue (GitHub Actions)
├── static/
│   ├── script.js            # Logique Frontend & Autocomplétion (Vanilla JS)
│   └── style.css            # Design "Dark Surface & Gold" (CSS3)
├── templates/
│   └── index.html           # Interface utilisateur (Jinja2 Template)
├── tests/
│   └── test_suite.py        # Tests unitaires (Jacobson/Karn & Endpoints)
├── algo.py                  # Le "Cerveau" (Algorithme Jacobson & Thread Safety)
├── app.py                   # Contrôleur Principal (Flask, Cache, Rate-Limiting)
├── Procfile                 # Configuration de déploiement (Gunicorn pour Render)
├── readme.md                # Documentation technique complète
├── requirements.txt         # Dépendances Python (verrouillées)
└── .gitignore               # Exclusion des fichiers temporaires (__pycache__, venv)