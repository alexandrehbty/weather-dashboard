variable "region" {
  description = "La région AWS (ex: eu-west-3 pour Paris)"
  default     = "eu-west-3"
  type        = string
}

variable "image_url" {
  description = "L'URL de l'image Docker (ex: public.ecr.aws/tonpseudo/weather-app:latest)"
  type        = string
}

variable "openweather_api_key" {
  description = "Ta clé API OpenWeather"
  type        = string
  sensitive   = true
}