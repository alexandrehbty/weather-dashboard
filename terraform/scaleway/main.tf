# 1. Déclaration du fournisseur Scaleway
terraform {
  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = "~> 2.0"
    }
  }
}

provider "scaleway" {
  region = var.region
  zone   = "${var.region}-1"
}

# 2. Le Namespace : L'espace logique pour tes conteneurs
resource "scaleway_container_namespace" "weather_namespace" {
  name        = "weather-portfolio-ns"
  description = "Namespace pour l'application météo du portfolio"
}

# 3. Le Conteneur : Scaleway Serverless Containers
resource "scaleway_container" "weather_app" {
  name           = "weather-dashboard-container"
  namespace_id   = scaleway_container_namespace.weather_namespace.id
  registry_image = var.image_url
  port           = 80
  
  # Ressources minimales pour optimiser les coûts
  cpu_limit    = 500  # 0.5 vCPU
  memory_limit = 1024 # 1 Go RAM

  # Paramètres d'échelle (Scale to Zero autorisé)
  min_scale = 0
  max_scale = 3

  # Injection de la variable d'environnement (Secret)
  # Scaleway permet d'injecter des secrets directement au niveau du conteneur
  secret_environment_variables = {
    API_KEY = var.openweather_api_key
  }
}