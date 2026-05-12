# 1. Configuration du fournisseur Google
provider "google" {
  project = var.project_id
  region  = var.region
}

# 2. Gestion sécurisée des Secrets (Google Secret Manager)
resource "google_secret_manager_secret" "weather_api_key" {
  secret_id = "WEATHER_API_KEY_PORTFOLIO"
  
  replication {
    auto {}
  }
}

# Injection de la valeur de la clé dans le secret
resource "google_secret_manager_secret_version" "weather_key_version" {
  secret      = google_secret_manager_secret.weather_api_key.id
  secret_data = var.openweather_api_key
}

# 3. Le Service Serverless : Google Cloud Run
resource "google_cloud_run_v2_service" "weather_dashboard" {
  name     = "weather-dashboard-prod"
  location = var.region
  
  # Autoriser le trafic venant d'internet
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = var.image_url

      # Récupération sécurisée du secret pour le transformer en variable d'environnement
      env {
        name = "API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.weather_api_key.secret_id
            version = "latest"
          }
        }
      }

      # Optimisation des coûts (Free Tier)
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }
}

# 4. Permissions (IAM) : Rendre le site web public
resource "google_cloud_run_service_iam_member" "public_access" {
  location = google_cloud_run_v2_service.weather_dashboard.location
  service  = google_cloud_run_v2_service.weather_dashboard.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}