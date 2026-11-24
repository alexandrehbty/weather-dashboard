#Azure
variable "location" {
  description = "Région Azure de déploiement (ex: francecentral)"
  type        = string
  default     = "francecentral"
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
  description = "Allocation CPU du conteneur en plan Consumption (0.25, 0.5, 1.0...)"
  type        = number
  default     = 0.25
}

variable "memory" {
  description = "Allocation mémoire associée au CPU (0.5Gi pour 0.25 vCPU, 1Gi pour 0.5 vCPU)"
  type        = string
  default     = "0.5Gi"
}

variable "min_replicas" {
  description = "Nombre minimal d'instances (0 = scale-to-zero pour limiter les coûts)"
  type        = number
  default     = 0
}

variable "max_replicas" {
  description = "Nombre maximal d'instances (plafond FinOps)"
  type        = number
  default     = 2
}