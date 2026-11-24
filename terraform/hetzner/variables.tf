#Hetzner
variable "hcloud_token" {
  description = "Jeton API Hetzner Cloud (optionnel si HCLOUD_TOKEN est défini dans l'environnement)"
  type        = string
  default     = null
  sensitive   = true
}

variable "location" {
  description = "Datacenter Hetzner Cloud (ex: fsn1 = Falkenstein, nbg1 = Nuremberg, hel1 = Helsinki)"
  type        = string
  default     = "fsn1"
}

variable "server_type" {
  description = "Type d'instance Hetzner Cloud (cx23 remplace l'ancien cx22 déprécié)"
  type        = string
  default     = "cx23"
}

variable "os_image" {
  description = "Image système de la machine virtuelle"
  type        = string
  default     = "ubuntu-24.04"
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
  description = "Liste des CIDR autorisés en SSH sur le port 22 (vide = port 22 fermé par défaut)"
  type        = list(string)
  default     = []
}