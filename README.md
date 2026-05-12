# 🌦️ GeoMeteo — Architecture Résiliente & Algorithmique

![CI Status](https://github.com/alexandrehbty/weather-dashboard/actions/workflows/ci.yaml/badge.svg)
![Coverage](https://img.shields.io/badge/Coverage-86%25-brightgreen.svg)
![E2E Tests](https://img.shields.io/badge/E2E%20Tests-Success%20100%25-green.svg)
![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)
![Algorithm](https://img.shields.io/badge/Algo-Jacobson%2FKarn-orange)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success)

> **Démonstration technique :** Conception d'un backend météo résilient ("Crash-Proof"), capable d'adapter ses timeouts en temps réel selon la congestion réseau. Optimisé pour les environnements contraints (Render Free Tier, 512Mo RAM).

🔗 **Démo Live :** https://weather-dashboard-c7gh.onrender.com/

---

## 🎯 Philosophie du Projet

Ce projet dépasse le simple wrapper d'API. C'est une **preuve de concept (PoC)** sur la fiabilité des systèmes distribués.
Le défi technique : **"Comment garantir une UX fluide et un Backend stable alors que l'infrastructure sous-jacente (Cloud Free Tier) et les API tierces sont imprévisibles ?"**

### Points forts techniques :
1.  **Intelligence Réseau (TCP-like) :** Algorithme adaptatif pour calculer les timeouts (fini les valeurs arbitraires).
2.  **Thread Safety & Concurrence :** Gestion des verrous (`threading.Lock`) pour supporter les workers Gunicorn.
3.  **UX Optimisée :** Autocomplétion avec Debounce, cartes interactives et feedback visuel immédiat.
4. **L'agnosticité Cloud (Vendor Lock-in) :** Permettre à l'application de pouvoir migrer d'un Cloud à l'autre en quelques minutes via Terraform.

---

## 🧠 Le "Cerveau" : Algorithme Jacobson/Karn (`algo.py`)

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

## 🌍 Infrastructure as Code (IaC) - Multi-Cloud

L'infrastructure du projet est entièrement codée via **Terraform**. Plutôt que de se limiter à un seul fournisseur, l'architecture a été pensée de manière modulaire pour être déployée sur **8 fournisseurs Cloud distincts**, démontrant une maîtrise des différents paradigmes d'hébergement.

### 1. Le paradigme "Serverless / CaaS" (Focus Produit)
Déploiement direct de l'image Docker avec délégation totale de l'infrastructure au Cloud Provider :
* ☁️ **Google Cloud (GCP) :** Cloud Run (v2) avec Google Secret Manager.
* ☁️ **AWS :** App Runner avec IAM Roles stricts et AWS Secrets Manager.
* ☁️ **Azure :** Container Apps protégé au sein d'un Resource Group avec Log Analytics Workspace.
* ☁️ **Scaleway :** Serverless Containers (Choix souverain européen).

### 2. Le paradigme "IaaS pur" (Focus SysAdmin / Bash)
Provisionnement de machines virtuelles nues et orchestration via des scripts `cloud-init` (User-Data) pour installer et configurer Docker au démarrage :
* 🇩🇪 **Hetzner :** Déploiement sur instances CX (Optimisation des coûts).
* 🇫🇷 **OVHcloud :** Interfaçage via le provider standard mondial **OpenStack**.

### 3. Le paradigme "Enterprise Networking" (Focus Réseau)
Construction de la plomberie réseau complète (VPC, Subnets, Internet Gateways, Route Tables) avant le déploiement du conteneur :
* 🏢 **Oracle Cloud (OCI) :** OCI Container Instances dans un Compartment dédié.
* 🇨🇳 **Alibaba Cloud :** Elastic Container Instance (ECI) avec VSwitch et Security Groups.

> 🔒 **Sécurité :** L'état Terraform (`.tfstate`) et les variables locales (`.tfvars`) sont rigoureusement exclus via `.gitignore`. Les clés API ne sont **jamais** écrites en clair dans le code IaC, mais injectées dynamiquement via les gestionnaires de secrets natifs des Clouds ou par la CI/CD.

---

## 🚀 Installation & Démarrage Local

Prérequis : Python 3.9+

1.  **Cloner le dépôt**
    ```bash
    git clone [https://github.com/alexandrehbty/weather-dashboard.git](https://github.com/alexandrehbty/weather-dashboard.git)
    cd weather-dashboard
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
    # Obtenez votre clé sur [https://home.openweathermap.org/api_keys](https://home.openweathermap.org/api_keys)
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
app.py                  221     47    79% <-- API Endpoints
tests\test_suite.py     121      1    99%
-----------------------------------------
TOTAL                   379     53    86% <-- Production Grade
```

---

## ⚙️ Déploiement (Production & Multi-Cloud)

Le projet est conçu avec une approche "Cloud Agnostic", permettant à la fois un déploiement rapide pour la démo et une infrastructure de niveau entreprise via l'IaC.

### 1. Déploiement sur Render (Démo Live)
Configuration utilisée pour la démonstration publique actuelle, optimisée pour les environnements contraints.

* **Fichiers critiques :**
    * `app.py` : Le serveur web.
    * `requirements.txt` : Les dépendances (gunicorn, flask, requests...).
* **Start Command (Render) :**
    ```bash
    gunicorn app:app --workers 1 --threads 4 --timeout 60
    ```
    *Note : Utilisation des threads plutôt que des workers multiples pour économiser la RAM (512 Mo limit).*

### 2. Infrastructure as Code (Terraform)
Le projet inclut une architecture modulaire complète prête à être déployée sur 8 fournisseurs Cloud différents. Tout le code d'infrastructure se trouve dans le dossier `terraform/`.

* ☁️ **CaaS / Serverless :** GCP (Cloud Run), AWS (App Runner), Azure (Container Apps), Scaleway.
* 🖥️ **IaaS (Compute brut) :** Hetzner, OVHcloud (via OpenStack).
* 🏢 **Enterprise Networking :** Oracle Cloud (OCI), Alibaba Cloud.

**Exemple de déploiement type (ex: AWS) :**
```bash
cd terraform/aws
terraform init
# Les secrets sont passés de manière sécurisée sans être stockés dans le code
terraform apply -var="image_url=votre_repo/image:latest"
```

---

## 📂 Structure du projet
```text
/
├── .github/
│   └── workflows/
│       └── ci.yaml          # Pipeline d'Intégration Continue (GitHub Actions)
├── e2e/                     # Tests de bout en bout (Playwright)
│   └── test_e2e_cold_start.py
├── static/
│   ├── script.js            # Logique Frontend & Autocomplétion (Vanilla JS)
│   └── style.css            # Design "Dark Surface & Gold" (CSS3)
├── templates/
│   └── index.html           # Interface utilisateur (Jinja2 Template)
├── terraform/               # Infrastructure as Code (8 Cloud Providers)
│   ├── aws/                 # Configuration AWS App Runner
│   ├── azure/               # Configuration Azure Container Apps
│   ├── gcp/                 # Configuration Google Cloud Run
│   └── ...                  # (Autres fournisseurs)
├── tests/
│   └── test_suite.py        # Tests unitaires (Jacobson/Karn & Endpoints)
├── algo.py                  # Le "Cerveau" (Algorithme Jacobson & Thread Safety)
├── app.py                   # Contrôleur Principal (Flask, Cache, Rate-Limiting)
├── Dockerfile               # Packaging de l'application en image Docker
├── Procfile                 # Configuration pour Render (Gunicorn)
├── README.md                # Documentation principale
├── requirements.txt         # Dépendances Python
└── .gitignore               # Exclusion des secrets et fichiers temporaires
```