variable "region" {
  description = "La région de déploiement Alibaba (ex: eu-central-1 pour Francfort)"
  default     = "eu-central-1"
  type        = string
}

variable "image_url" {
  description = "L'URL de ton image Docker sur le registre (ex: docker.io/tonpseudo/weather-app:latest)"
  type        = string
}

variable "openweather_api_key" {
  description = "Ta clé API OpenWeather"
  type        = string
  sensitive   = true
}