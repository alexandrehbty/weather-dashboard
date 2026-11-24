#OVH
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 3.0"
    }
  }
}

# Authentification via le fichier openrc.sh d'OVHcloud (OS_USERNAME, OS_PASSWORD, OS_TENANT_NAME)
# ou via les variables dédiées dans terraform.tfvars
provider "openstack" {
  auth_url    = "https://auth.cloud.ovh.net/v3/"
  domain_name = "default"
  user_name   = var.openstack_user_name
  password    = var.openstack_password
  tenant_name = var.openstack_tenant_name
  region      = var.region
}

# 1. Clé SSH optionnelle (recommandée pour la maintenance sur Ubuntu Public Cloud)
resource "openstack_compute_keypair_v2" "deploy_key" {
  count      = var.ssh_public_key != "" ? 1 : 0
  name       = "weather-portfolio-key"
  public_key = var.ssh_public_key
}

# 2. Pare-feu : Groupe de sécurité Neutron géré intégralement par Terraform
resource "openstack_networking_secgroup_v2" "weather_sg" {
  name                 = "weather-portfolio-sg"
  description          = "Pare-feu dédié à l'application GeoMeteo"
  delete_default_rules = true
}

# Trafic entrant : HTTP (port 80) en IPv4 et IPv6
resource "openstack_networking_secgroup_rule_v2" "allow_web_v4" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.weather_sg.id
}

resource "openstack_networking_secgroup_rule_v2" "allow_web_v6" {
  direction         = "ingress"
  ethertype         = "IPv6"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  remote_ip_prefix  = "::/0"
  security_group_id = openstack_networking_secgroup_v2.weather_sg.id
}

# Trafic entrant SSH (port 22) : fermé par défaut, ouvert uniquement aux CIDR explicitement déclarés
resource "openstack_networking_secgroup_rule_v2" "allow_ssh" {
  for_each          = toset(var.ssh_allowed_cidrs)
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = each.value
  security_group_id = openstack_networking_secgroup_v2.weather_sg.id
}

# Trafic sortant : autorisé pour apt, pull GHCR, DNS et appels HTTPS OpenWeather
resource "openstack_networking_secgroup_rule_v2" "allow_egress_v4" {
  direction         = "egress"
  ethertype         = "IPv4"
  security_group_id = openstack_networking_secgroup_v2.weather_sg.id
}

resource "openstack_networking_secgroup_rule_v2" "allow_egress_v6" {
  direction         = "egress"
  ethertype         = "IPv6"
  security_group_id = openstack_networking_secgroup_v2.weather_sg.id
}

# 3. Instance Public Cloud OVH (IaaS + Cloud-Init Docker)
resource "openstack_compute_instance_v2" "weather_server" {
  name        = "weather-dashboard-vm"
  image_name  = var.os_image
  flavor_name = var.flavor_name
  key_pair    = length(openstack_compute_keypair_v2.deploy_key) > 0 ? openstack_compute_keypair_v2.deploy_key[0].name : null

  security_groups = [openstack_networking_secgroup_v2.weather_sg.name]

  metadata = {
    project    = "geometeo"
    managed_by = "terraform"
  }

  # Réseau public par défaut sur OVHcloud Public Cloud
  network {
    name = "Ext-Net"
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

  depends_on = [
    openstack_networking_secgroup_rule_v2.allow_web_v4,
    openstack_networking_secgroup_rule_v2.allow_web_v6,
    openstack_networking_secgroup_rule_v2.allow_egress_v4,
    openstack_networking_secgroup_rule_v2.allow_egress_v6,
  ]
}