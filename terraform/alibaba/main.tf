#Alibaba

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.230"
    }
  }
}

# Authentification via variables d'environnement :
# export ALICLOUD_ACCESS_KEY="..."
# export ALICLOUD_SECRET_KEY="..."
provider "alicloud" {
  region = var.region
}

# Récupération automatique d'une zone disponible dans la région cible
data "alicloud_zones" "available" {
  available_resource_creation = "VSwitch"
}

# 1. Réseau : VPC et sous-réseau (VSwitch)
resource "alicloud_vpc" "weather_vpc" {
  vpc_name   = "weather-portfolio-vpc"
  cidr_block = "10.0.0.0/16"
}

resource "alicloud_vswitch" "weather_vswitch" {
  vswitch_name = "weather-portfolio-vswitch"
  cidr_block   = "10.0.1.0/24"
  vpc_id       = alicloud_vpc.weather_vpc.id
  zone_id      = data.alicloud_zones.available.zones[0].id
}

# 2. Sécurité : Security Group (VPC)
resource "alicloud_security_group" "weather_sg" {
  security_group_name = "weather-portfolio-sg"
  security_group_type = "normal"
  vpc_id              = alicloud_vpc.weather_vpc.id
}

# Trafic entrant HTTP sur le port 80 (nic_type = "intranet" requis en mode VPC)
resource "alicloud_security_group_rule" "allow_web_ingress" {
  type              = "ingress"
  ip_protocol       = "tcp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "80/80"
  priority          = 1
  security_group_id = alicloud_security_group.weather_sg.id
  cidr_ip           = "0.0.0.0/0"
}

# Trafic sortant HTTPS (pull GHCR + appels OpenWeather) et DNS
resource "alicloud_security_group_rule" "allow_https_egress" {
  type              = "egress"
  ip_protocol       = "tcp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "443/443"
  priority          = 1
  security_group_id = alicloud_security_group.weather_sg.id
  cidr_ip           = "0.0.0.0/0"
}

# 3. Calcul : Elastic Container Instance (ECI)
resource "alicloud_eci_container_group" "weather_app" {
  container_group_name = "weather-dashboard-eci"
  security_group_id    = alicloud_security_group.weather_sg.id
  vswitch_id           = alicloud_vswitch.weather_vswitch.id

  cpu             = var.cpu
  memory          = var.memory
  restart_policy  = "Always"
  auto_create_eip = true
  eip_bandwidth   = 5

  containers {
    name              = "weather-dashboard-container"
    image             = var.image_url
    image_pull_policy = "Always"

    environment_vars {
      key   = "API_KEY"
      value = var.openweather_api_key
    }

    ports {
      port     = 80
      protocol = "TCP"
    }

    readiness_probe {
      http_get {
        path   = "/health"
        port   = 80
        scheme = "HTTP"
      }
      initial_delay_seconds = 5
      period_seconds        = 10
      timeout_seconds       = 3
    }

    liveness_probe {
      http_get {
        path   = "/health"
        port   = 80
        scheme = "HTTP"
      }
      initial_delay_seconds = 15
      period_seconds        = 20
      timeout_seconds       = 3
    }
  }
}