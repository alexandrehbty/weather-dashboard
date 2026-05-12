variable "openstack_user_name" {
  description = "Ton nom d'utilisateur OpenStack OVH"
  type        = string
}

variable "openstack_password" {
  description = "Ton mot de passe OpenStack OVH"
  type        = string
  sensitive   = true
}

variable "openstack_tenant_name" {
  description = "Le nom de ton projet OVH (Service Name / Tenant)"
  type        = string
}

variable "region" {
  description = "La région du datacenter OVH (ex: GRA11 pour Gravelines)"
  default     = "GRA11"
  type        = string
}

variable "image_url" {
  description = "L'URL de ton image Docker"
  type        = string
}

variable "openweather_api_key" {
  description = "Ta clé API OpenWeather"
  type        = string
  sensitive   = true
}