#Scaleway
variable "region" {
  description = "Région Scaleway Serverless Containers (fr-par, nl-ams ou pl-waw)"
  type        = string
  default     = "fr-par"

  validation {
    condition     = contains(["fr-par", "nl-ams", "pl-waw"], var.region)
    error_message = "La région doit être fr-par, nl-ams ou pl-waw."
  }
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

variable "cpu_limit" {
  description = "Limite CPU en mvCPU correspondant au palier mémoire (280 pour 512 MiB, 560 pour 1024 MiB)"
  type        = number
  default     = 280
}

variable "memory_limit_bytes" {
  description = "Limite mémoire en octets (536870912 = 512 MiB, 1073741824 = 1024 MiB)"
  type        = number
  default     = 536870912
}

variable "min_scale" {
  description = "Nombre minimal d'instances (0 = scale-to-zero)"
  type        = number
  default     = 0
}

variable "max_scale" {
  description = "Nombre maximal d'instances (plafond FinOps)"
  type        = number
  default     = 2
}