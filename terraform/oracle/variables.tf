variable "region" {
  description = "La région Oracle Cloud (ex: eu-paris-1 pour Paris)"
  default     = "eu-paris-1"
  type        = string
}

variable "compartment_ocid" {
  description = "L'OCID du Compartiment Oracle où créer les ressources"
  type        = string
}

variable "image_url" {
  description = "L'URL de ton image Docker (ex: docker.io/tonpseudo/weather-app:latest)"
  type        = string
}

variable "openweather_api_key" {
  description = "Ta clé API OpenWeather"
  type        = string
  sensitive   = true
}