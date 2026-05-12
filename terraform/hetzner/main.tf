# 1. Déclaration du fournisseur Hetzner Cloud
terraform {
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.45"
    }
  }
}

provider "hcloud" {
  token = var.hcloud_token
}

# 2. Sécurité : Création du Pare-feu (Firewall)
resource "hcloud_firewall" "web_firewall" {
  name = "weather-portfolio-fw"

  # Règle 1 : Autoriser le trafic Web (HTTP sur le port 80)
  rule {
    direction = "in"
    protocol  = "tcp"
    port      = "80"
    source_ips = [
      "0.0.0.0/0",
      "::/0"
    ]
  }

  # Règle 2 : Autoriser le trafic SSH (Port 22) pour la maintenance
  rule {
    direction = "in"
    protocol  = "tcp"
    port      = "22"
    source_ips = [
      "0.0.0.0/0",
      "::/0"
    ]
  }
}

# 3. Le Serveur : Création de la Machine Virtuelle (VM)
resource "hcloud_server" "weather_server" {
  name        = "weather-dashboard-vm"
  image       = "ubuntu-22.04"     # Système d'exploitation brut
  server_type = "cx22"             # Instance basique (très abordable)
  location    = var.location
  
  # On attache le pare-feu au serveur
  firewall_ids = [hcloud_firewall.web_firewall.id]

  # Assignation d'une adresse IP publique
  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  # 4. Le Script d'amorçage (Cloud-Init / User-Data)
  # Ce script Bash s'exécute automatiquement lors du tout premier démarrage du serveur.
  # Il transforme notre serveur brut en un hôte Docker prêt à l'emploi.
  user_data = <<-EOF
              #!/bin/bash
              # Mise à jour de la machine
              apt-get update -y
              
              # Installation de Docker
              apt-get install -y docker.io
              
              # Démarrage du service Docker
              systemctl enable --now docker
              
              # Lancement de ton application avec la clé API injectée
              docker run -d --name weather-app -p 80:80 -e API_KEY=${var.openweather_api_key} ${var.image_url}
              EOF
}