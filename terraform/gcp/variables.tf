#GCP
variable "project_id" {
  description = "ID du projet Google Cloud"
  type        = string
}

variable "region" {
  description = "Région GCP de déploiement (europe-west9 = Paris ; europe-west1 = Belgique éligible Tier 1 Always Free)"
  type        = string
  default     = "europe-west9"
}

variable "image_url" {
  description = "URL de l'image Docker dans Artifact Registry (ex: europe-west9-docker.pkg.dev/<project>/<repo>/weather-dashboard:main) ou via un remote repository GHCR"
  type        = string
}

variable "openweather_api_key" {
  description = "Clé API OpenWeather (injectable via TF_VAR_openweather_api_key)"
  type        = string
  sensitive   = true
}

variable "cpu" {
  description = "Allocation CPU du conteneur Cloud Run"
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Allocation mémoire du conteneur Cloud Run"
  type        = string
  default     = "512Mi"
}

variable "min_instances" {
  description = "Nombre minimal d'instances (0 = scale-to-zero)"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Nombre maximal d'instances (plafond FinOps)"
  type        = number
  default     = 2
}