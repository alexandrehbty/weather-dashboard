#Hetzner
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.70"
    }
  }
}

# Authentification via variable d'environnement (export HCLOUD_TOKEN="...")
# ou via var.hcloud_token dans terraform.tfvars
provider "hcloud" {
  token = var.hcloud_token
}

locals {
  common_labels = {
    project    = "geometeo"
    managed_by = "terraform"
  }
}

# 1. Clé SSH optionnelle (évite l'authentification par mot de passe root)
resource "hcloud_ssh_key" "deploy_key" {
  count      = var.ssh_public_key != "" ? 1 : 0
  name       = "weather-portfolio-key"
  public_key = var.ssh_public_key
  labels     = local.common_labels
}

# 2. Sécurité : Pare-feu Hetzner Cloud
resource "hcloud_firewall" "web_firewall" {
  name   = "weather-portfolio-fw"
  labels = local.common_labels

  # Trafic Web entrant (HTTP sur le port 80)
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  # Trafic SSH (Port 22) : fermé par défaut, ouvert uniquement aux IP/CIDR déclarés
  dynamic "rule" {
    for_each = length(var.ssh_allowed_cidrs) > 0 ? [1] : []
    content {
      direction  = "in"
      protocol   = "tcp"
      port       = "22"
      source_ips = var.ssh_allowed_cidrs
    }
  }
}

# 3. Serveur IaaS (VM + Cloud-Init Docker)
resource "hcloud_server" "weather_server" {
  name         = "weather-dashboard-vm"
  image        = var.os_image
  server_type  = var.server_type
  location     = var.location
  firewall_ids = [hcloud_firewall.web_firewall.id]
  ssh_keys     = [for key in hcloud_ssh_key.deploy_key : key.id]
  labels       = local.common_labels

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  # Script d'amorçage (Cloud-Init) : installation Docker + lancement résilient du conteneur
  # Note IaaS : user_data reste stocké dans le tfstate (exclu de Git via .gitignore)
  user_data = <<-EOF
              #!/bin/bash
              set -euo pipefail
              export DEBIAN_FRONTEND=noninteractive

              apt-get update -y
              apt-get install -y --no-install-recommends docker.io

              systemctl enable --now docker

              # Stockage protégé de la clé API hors ligne de commande Docker
              install -m 600 /dev/null /etc/geometeo.env
              cat <<'ENVEOF' > /etc/geometeo.env
              API_KEY=${var.openweather_api_key}
              ENVEOF

              docker pull "${var.image_url}"
              docker run -d \
                --name weather-app \
                --restart unless-stopped \
                -p 80:80 \
                --env-file /etc/geometeo.env \
                --health-cmd='python -c "import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:80/health\", timeout=2)"' \
                --health-interval=15s \
                --health-timeout=3s \
                --health-retries=3 \
                "${var.image_url}"
              EOF
}