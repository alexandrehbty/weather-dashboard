variable "project_id" {
  description = "L'ID de ton projet Google Cloud"
  type        = string
}

variable "region" {
  description = "La région de déploiement GCP (ex: europe-west9 pour Paris)"
  default     = "europe-west9"
  type        = string
}

variable "image_url" {
  description = "L'URL de ton image Docker (ex: gcr.io/ton-projet/weather-app:latest)"
  type        = string
}

variable "openweather_api_key" {
  description = "Ta clé API OpenWeather"
  type        = string
  sensitive   = true
}