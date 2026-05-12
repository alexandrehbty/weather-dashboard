# 1. Configuration du fournisseur Alibaba Cloud
provider "alicloud" {
  region = var.region
}

# Récupération automatique de la première zone de disponibilité (Datacenter) disponible dans la région
data "alicloud_zones" "available" {
  available_resource_creation = "VSwitch"
}

# 2. Création du Réseau (VPC - Virtual Private Cloud)
resource "alicloud_vpc" "weather_vpc" {
  vpc_name   = "weather-portfolio-vpc"
  cidr_block = "10.0.0.0/16"
}

# Création du sous-réseau (VSwitch)
resource "alicloud_vswitch" "weather_vswitch" {
  vswitch_name = "weather-portfolio-vswitch"
  cidr_block   = "10.0.1.0/24"
  vpc_id       = alicloud_vpc.weather_vpc.id
  zone_id      = data.alicloud_zones.available.zones[0].id
}

# 3. Sécurité : Création du Pare-feu (Security Group)
resource "alicloud_security_group" "weather_sg" {
  name   = "weather-portfolio-sg"
  vpc_id = alicloud_vpc.weather_vpc.id
}

# Règle de pare-feu : Autoriser le trafic web (Port 80) depuis n'importe où
resource "alicloud_security_group_rule" "allow_web" {
  type              = "ingress"
  ip_protocol       = "tcp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "80/80"
  priority          = 1
  security_group_id = alicloud_security_group.weather_sg.id
  cidr_ip           = "0.0.0.0/0"
}

# 4. Le Conteneur : Elastic Container Instance (ECI)
resource "alicloud_eci_container_group" "weather_app" {
  container_group_name = "weather-dashboard-eci"
  security_group_id    = alicloud_security_group.weather_sg.id
  vswitch_id           = alicloud_vswitch.weather_vswitch.id
  
  # Ressources minimales
  cpu    = 1.0
  memory = 2.0
  
  # Demande la création automatique d'une adresse IP publique
  auto_create_eip = true 

  containers {
    name  = "weather-dashboard-container"
    image = var.image_url

    # Injection de ta variable d'environnement secrète
    environment_vars {
      key   = "API_KEY"
      value = var.openweather_api_key
    }

    ports {
      port     = 80
      protocol = "TCP"
    }
  }
}