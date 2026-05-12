variable "location" {
  description = "La région Azure (ex: francecentral)"
  default     = "francecentral"
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