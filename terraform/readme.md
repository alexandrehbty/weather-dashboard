# 🌍 GeoMeteo — Infrastructure as Code (Multi-Cloud) - ![Status](https://img.shields.io/badge/Status-Ready-orange)

Ce répertoire contient l'intégralité de la configuration **Terraform** permettant de déployer l'application GeoMeteo de manière agnostique sur les principaux fournisseurs Cloud du marché.

---

## 📂 Structure du Répertoire

L'infrastructure est organisée par fournisseur. Chaque dossier est autonome et contient sa propre logique de déploiement :

* **`alibaba/`** : Deployment sur Alibaba Cloud Elastic Container Instance (ECI).
* **`aws/`** : Utilisation de AWS App Runner (PaaS).
* **`azure/`** : Déploiement sur Azure Container Apps.
* **`gcp/`** : Utilisation de Google Cloud Run (Serverless).
* **`hetzner/`** : Provisionnement d'instances Cloud avec Cloud-Init (IaaS).
* **`oracle/`** : Déploiement sur Oracle Cloud Container Instances.
* **`ovh/`** : Instance Public Cloud via OpenStack (IaaS).
* **`scaleway/`** : Utilisation de Serverless Containers.

---

## 🛠️ Prérequis

Avant de commencer, assurez-vous d'avoir :
1.  **Terraform CLI** (v1.5.0+) installé.
2.  Des **identifiants valides** (clés d'accès, tokens) pour le fournisseur Cloud choisi.
3.  L'**image Docker** du projet publiée sur un registre (ex: GHCR).

---

## 🚀 Procédure de Déploiement

Pour déployer l'infrastructure sur n'importe quel fournisseur, suivez ces étapes standardisées :

### 1. Préparation des secrets
À la racine de ce dossier `terraform/`, vous trouverez un fichier modèle nommé `terraform.tfvars.example`.

1.  Entrez dans le dossier du fournisseur choisi :
    ```hcl
    cd terraform/aws  # Exemple pour AWS
    ```
2.  Copiez le modèle de configuration :
    ```hcl
    cp ../terraform.tfvars.example ./terraform.tfvars
    ```
3.  Ouvrez `terraform.tfvars` et renseignez vos informations réelles (Clé API OpenWeather, URL de l'image, etc.).

### 2. Initialisation
Préparez l'environnement Terraform et téléchargez les plugins nécessaires :
```hcl
terraform init
```

### 3. Planification (Vérification)
Pour visualisez les ressources qui vont être créées, utilisé ceci :
```hcl
terraform plan
```

### 4. Application (Déploiement)
Pour lancez la création réelle de l'infrastructure sur le Cloud :
```hcl
terraform apply
```
Tapez ``` yes ``` pour confirmer l'action quand cela vous sera demandé.

---

## 🏁 Résultats & Accès

Une fois le déploiement terminé, Terraform affichera l'URL ou l'IP publique de votre application via la section ```Outputs``` :
```hcl
app_url = "https://weather-dashboard-xxxx.cloud.run"
```
Il vous suffit de copier cette adresse dans votre navigateur pour accéder à votre instance GeoMeteo en direct.

---

## 🧹 Nettoyage (Destruction)

Pour supprimer toutes les ressources créées et éviter toute facturation inutile après vos tests :
```hcl
terraform destroy
```
Confirmez avec ```yes```.