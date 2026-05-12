variable "region" {
  description = "La région de déploiement Scaleway (ex: fr-par pour Paris)"
  default     = "fr-par"
  type        = string
}

variable "image_url" {
  description = "L'URL de ton image Docker sur le registre"
  type        = string
}

variable "openweather_api_key" {
  description = "Ta clé API OpenWeather"
  type        = string
  sensitive   = true
}