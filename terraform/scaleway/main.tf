#Scaleway
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = "~> 2.90"
    }
  }
}

# Authentification via variables d'environnement :
# export SCW_ACCESS_KEY="..."
# export SCW_SECRET_KEY="..."
# export SCW_DEFAULT_PROJECT_ID="..."
provider "scaleway" {
  region = var.region
  zone   = "${var.region}-1"
}

locals {
  common_tags = [
    "project:geometeo",
    "managed-by:terraform",
  ]
}

# 1. Namespace Serverless Containers
resource "scaleway_container_namespace" "weather_namespace" {
  name        = "weather-portfolio-ns"
  description = "Namespace Serverless dédié à l'application GeoMeteo"
  region      = var.region
  tags        = local.common_tags
}

# 2. Conteneur managé : Scaleway Serverless Containers (HTTPS forcé)
resource "scaleway_container" "weather_app" {
  name                   = "weather-dashboard-container"
  namespace_id           = scaleway_container_namespace.weather_namespace.id
  region                 = var.region
  description            = "Backend Flask GeoMeteo"
  image                  = var.image_url
  port                   = 80
  privacy                = "public"
  https_connections_only = true
  timeout                = 60
  tags                   = local.common_tags

  # Palier Scaleway cohérent : 512 MiB / 280 mvCPU (adapté au Free Tier mensuel)
  cpu_limit          = var.cpu_limit
  memory_limit_bytes = var.memory_limit_bytes

  # Scale-to-zero activé + plafond FinOps
  min_scale = var.min_scale
  max_scale = var.max_scale

  scaling_option {
    concurrent_requests_threshold = 50
  }

  # Injection sécurisée de la clé API (masquée par Scaleway après validation)
  secret_environment_variables = {
    API_KEY = var.openweather_api_key
  }

  startup_probe {
    http {
      path = "/health"
    }
    failure_threshold = 3
    interval          = "10s"
    timeout           = "3s"
  }

  liveness_probe {
    http {
      path = "/health"
    }
    failure_threshold = 3
    interval          = "20s"
    timeout           = "3s"
  }
}