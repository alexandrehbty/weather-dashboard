#GCP
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }
}

# Authentification via Google Cloud CLI (`gcloud auth application-default login`)
# ou variable d'environnement GOOGLE_APPLICATION_CREDENTIALS
provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Activation des APIs GCP requises (conservées lors d'un destroy)
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

# 2. Identité dédiée (moindre privilège au lieu du compte Compute par défaut)
resource "google_service_account" "cloud_run_sa" {
  account_id   = "weather-dashboard-sa"
  display_name = "GeoMeteo Cloud Run Runtime Service Account"

  depends_on = [google_project_service.required_apis]
}

# 3. Coffre-fort : Google Secret Manager
resource "google_secret_manager_secret" "weather_api_key" {
  secret_id = "weather-api-key-portfolio"

  labels = {
    project    = "geometeo"
    managed_by = "terraform"
  }

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret_version" "weather_key_version" {
  secret      = google_secret_manager_secret.weather_api_key.id
  secret_data = var.openweather_api_key
}

# Autorise uniquement le compte de service Cloud Run à lire ce secret précis
resource "google_secret_manager_secret_iam_member" "weather_secret_accessor" {
  project   = google_secret_manager_secret.weather_api_key.project
  secret_id = google_secret_manager_secret.weather_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# 4. Service Serverless : Google Cloud Run v2 (HTTPS géré nativement)
resource "google_cloud_run_v2_service" "weather_dashboard" {
  name                = "weather-dashboard-prod"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false # Choix PoC : autorise terraform destroy

  labels = {
    project    = "geometeo"
    managed_by = "terraform"
  }

  template {
    service_account = google_service_account.cloud_run_sa.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.image_url

      # Aligne Cloud Run sur le port 80 exposé par le Dockerfile (défaut Cloud Run = 8080)
      ports {
        container_port = 80
      }

      env {
        name = "API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.weather_api_key.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 80
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        timeout_seconds       = 3
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 80
        }
        initial_delay_seconds = 15
        period_seconds        = 20
        timeout_seconds       = 3
        failure_threshold     = 3
      }
    }
  }

  # Évite la race condition avant la création de la version du secret et des droits IAM
  depends_on = [
    google_project_service.required_apis,
    google_secret_manager_secret_version.weather_key_version,
    google_secret_manager_secret_iam_member.weather_secret_accessor,
  ]
}

# 5. Accès public (API v2 homogène)
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  project  = google_cloud_run_v2_service.weather_dashboard.project
  location = google_cloud_run_v2_service.weather_dashboard.location
  name     = google_cloud_run_v2_service.weather_dashboard.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}