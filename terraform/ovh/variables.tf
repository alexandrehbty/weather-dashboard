#OVH
variable "openstack_user_name" {
  description = "Nom d'utilisateur OpenStack OVH (optionnel si OS_USERNAME est défini via openrc.sh)"
  type        = string
  default     = null
}

variable "openstack_password" {
  description = "Mot de passe OpenStack OVH (optionnel si OS_PASSWORD est défini via openrc.sh)"
  type        = string
  default     = null
  sensitive   = true
}

variable "openstack_tenant_name" {
  description = "Nom du projet / tenant OVH (optionnel si OS_TENANT_NAME est défini via openrc.sh)"
  type        = string
  default     = null
}

variable "region" {
  description = "Région du datacenter OVHcloud (ex: GRA11 pour Gravelines, SBG5 pour Strasbourg)"
  type        = string
  default     = "GRA11"
}

variable "flavor_name" {
  description = "Gabarit d'instance OVHcloud Public Cloud (d2-2 = 1 vCore / 2 Go RAM)"
  type        = string
  default     = "d2-2"
}

variable "os_image" {
  description = "Image système OpenStack disponible sur OVHcloud"
  type        = string
  default     = "Ubuntu 24.04"
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

variable "ssh_public_key" {
  description = "Clé publique SSH optionnelle pour la maintenance de la VM"
  type        = string
  default     = ""
}

variable "ssh_allowed_cidrs" {
  description = "Liste des CIDR IPv4 autorisés en SSH sur le port 22 (vide = port 22 fermé par défaut)"
  type        = list(string)
  default     = []
}