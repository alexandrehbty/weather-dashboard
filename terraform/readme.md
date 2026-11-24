# GeoMeteo — Infrastructure Terraform (Multi-Cloud)

Ce dossier regroupe huit déclinaisons Terraform autonomes (Terraform `>= 1.5.0`) pour déployer **GeoMeteo** selon trois approches : **Serverless**, **Conteneurs managés** et **IaaS (VM + Cloud-Init)**.

> **Périmètre de validation :** l'application tourne en démonstration sur Render. Ces huit configurations sont vérifiées statiquement (`terraform fmt` et `terraform validate` sans backend distant) mais ne sont pas maintenues actives sur huit comptes Cloud payants.

## Comparatif des architectures

| Fournisseur | Service | Modèle | Accès | Secret `API_KEY` | Registre Docker |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `aws/` | App Runner | PaaS / Serverless | HTTPS | Secrets Manager + IAM | ECR Public (`public.ecr.aws/`) |
| `azure/` | Container Apps | Serverless | HTTPS | Secret natif | GHCR public |
| `gcp/` | Cloud Run v2 | Serverless | HTTPS | Secret Manager + IAM | Artifact Registry |
| `scaleway/` | Serverless Containers | Serverless | HTTPS | Secret natif | GHCR public |
| `alibaba/` | ECI | Conteneur managé | HTTP (`80`) | Variable d'environnement | GHCR public |
| `oracle/` | Container Instances | Conteneur managé | HTTP (`80`) | Variable d'environnement | GHCR public |
| `hetzner/` | VM `cx23` + Cloud-Init | IaaS | HTTP (`80`) | `/etc/geometeo.env` (`600`) | GHCR public |
| `ovh/` | OpenStack `d2-2` + Cloud-Init | IaaS | HTTP (`80`) | `/etc/geometeo.env` (`600`) | GHCR public |

## Choix d'architecture et compromis

* **Serverless vs IaaS :** les plateformes managées (`aws/`, `azure/`, `gcp/`, `scaleway/`) gèrent nativement le TLS, l'injection sécurisée des secrets et le *scale-to-zero* (hormis App Runner, maintenu à `min = 1`). Les déploiements IaaS (`hetzner/`, `ovh/`) et conteneurs simples (`alibaba/`, `oracle/`) exposent le port `80` en HTTP pur pour rester légers ; en production, un reverse proxy TLS ou un Load Balancer managé s'ajoute en frontal.
* **Sécurité et observabilité :** chaque module épingle son provider (`required_providers`), expose une sortie `app_url` homogène et sonde `/health` sur le port `80`. Sur Hetzner et OVHcloud, le port SSH (`22`) est fermé par défaut dans le pare-feu et ne s'ouvre que sur des CIDR explicites (`ssh_allowed_cidrs`).
* **Contraintes de registres :** l'image publiée sur `ghcr.io` est directement utilisable sur six fournisseurs. AWS App Runner impose un miroir Amazon ECR Public (contrôlé par validation dans `variables.tf`), et Google Cloud Run attend Artifact Registry (ou un *remote repository* pointant vers GHCR).
* **Garde-fous FinOps & état :** les services auto-scalables sont plafonnés à `2` instances maximum et dimensionnés au plus près de l'empreinte mémoire de GeoMeteo (`512 Mo` lorsque les paliers le permettent). L'état `terraform.tfstate` reste local (et ignoré par Git) dans ce cadre de démonstration ; en équipe, il basculerait sur un backend distant chiffré avec verrouillage (d'autant que le `user_data` des déploiements IaaS y est conservé).

## Validation locale (sans identifiants Cloud)

```bash
terraform fmt -check -recursive

for dir in alibaba aws azure gcp hetzner oracle ovh scaleway; do
  (cd "$dir" && terraform init -backend=false -input=false && terraform validate) || exit 1
done
```

## Déploiement rapide

Les variables d'authentification propres à chaque fournisseur sont documentées en en-tête de son `main.tf`. Les fichiers `terraform.tfvars` et `*.tfstate` sont exclus du dépôt via `.gitignore`.

```bash
cd scaleway                                        # Exemple
cp ../terraform.tfvars.example ./terraform.tfvars  # Décommenter la section utile
export TF_VAR_openweather_api_key="..."            # Évite d'écrire la clé sur disque
terraform init && terraform plan && terraform apply
```

## Nettoyage (éviter toute facturation)

Après un test de déploiement, exécutez la suppression depuis le même dossier (avec les mêmes identifiants Cloud chargés) pour détruire l'ensemble des ressources provisionnées :

```bash
terraform destroy
```

> Les options de rétention bloquantes sont désactivées dans ce cadre de test (`recovery_window_in_days = 0` sur AWS Secrets Manager, `deletion_protection = false` sur Cloud Run) afin de permettre une suppression immédiate et complète. Pensez tout de même à vérifier la console du fournisseur en cas d'interruption en cours de destruction.