#Oracle
variable "region" {
  description = "Région Oracle Cloud (ex: eu-paris-1 pour Paris, eu-marseille-1 pour Marseille)"
  type        = string
  default     = "eu-paris-1"
}

variable "compartment_ocid" {
  description = "OCID du compartiment OCI cible"
  type        = string
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

variable "shape" {
  description = "Shape OCI Container Instance (ex: CI.Standard.E4.Flex)"
  type        = string
  default     = "CI.Standard.E4.Flex"
}

variable "ocpus" {
  description = "Nombre d'OCPUs alloués à la Container Instance"
  type        = number
  default     = 1
}

variable "memory_in_gbs" {
  description = "Mémoire RAM allouée en Go (minimum 1 Go par OCPU sur E4.Flex)"
  type        = number
  default     = 2
}