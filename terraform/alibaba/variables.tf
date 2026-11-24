#Alibaba

variable "region" {
  description = "Région de déploiement Alibaba Cloud (ex: eu-central-1 pour Francfort)"
  type        = string
  default     = "eu-central-1"
}

variable "image_url" {
  description = "URL complète de l'image Docker publique (ex: ghcr.io/<user>/weather-dashboard:main)"
  type        = string
}

variable "openweather_api_key" {
  description = "Clé API OpenWeather (injectable via TF_VAR_openweather_api_key)"
  type        = string
  sensitive   = true
}

variable "cpu" {
  description = "Nombre de vCPU alloués au conteneur ECI"
  type        = number
  default     = 1.0
}

variable "memory" {
  description = "Mémoire RAM allouée au conteneur ECI (en Go)"
  type        = number
  default     = 2.0
}