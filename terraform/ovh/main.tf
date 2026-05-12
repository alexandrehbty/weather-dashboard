# 1. Configuration du fournisseur OpenStack (Connecté à OVH)
terraform {
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 1.53.0"
    }
  }
}

provider "openstack" {
  auth_url    = "https://auth.cloud.ovh.net/v3/" # Le point d'entrée OVHcloud
  domain_name = "default"
  user_name   = var.openstack_user_name
  password    = var.openstack_password
  tenant_name = var.openstack_tenant_name
  region      = var.region
}

# 2. Pare-feu : Création du groupe de sécurité (Security Group)
resource "openstack_networking_secgroup_v2" "weather_sg" {
  name        = "weather-portfolio-sg"
  description = "Autoriser le trafic HTTP pour le site web"
}

# Règle pour le trafic Web (Port 80)
resource "openstack_networking_secgroup_rule_v2" "allow_web" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.weather_sg.id
}

# 3. Le Serveur : Création de la Machine Virtuelle (Compute Instance)
resource "openstack_compute_instance_v2" "weather_server" {
  name        = "weather-dashboard-vm"
  image_name  = "Ubuntu 22.04"
  flavor_name = "d2-2" # Le gabarit "Discovery" d'OVH (très économique)

  security_groups = [openstack_networking_secgroup_v2.weather_sg.name]

  # Chez OVH, le réseau public par défaut qui donne accès à Internet s'appelle "Ext-Net"
  network {
    name = "Ext-Net"
  }

  # 4. Le Script d'amorçage (Cloud-Init / User-Data)
  # Ce script Bash s'exécute automatiquement lors du tout premier démarrage du serveur.
  user_data = <<-EOF
              #!/bin/bash
              # Mise à jour de la machine
              apt-get update -y
              
              # Installation de Docker
              apt-get install -y docker.io
              
              # Démarrage du service Docker
              systemctl enable --now docker
              
              # Lancement de l'application avec la clé API injectée
              docker run -d --name weather-app -p 80:80 -e API_KEY=${var.openweather_api_key} ${var.image_url}
              EOF
}