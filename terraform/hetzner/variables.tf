variable "hcloud_token" {
  description = "Ton jeton API Hetzner Cloud (HCloud Token)"
  type        = string
  sensitive   = true
}

variable "location" {
  description = "Le datacenter Hetzner (ex: fsn1 pour Falkenstein en Allemagne)"
  default     = "fsn1"
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