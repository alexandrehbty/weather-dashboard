#Oracle
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 9.0"
    }
  }
}

# Authentification via profil CLI (~/.oci/config) ou variables d'environnement :
# TF_VAR_tenancy_ocid / OCI_TENANCY_OCID, OCI_USER_OCID, OCI_FINGERPRINT, OCI_PRIVATE_KEY_PATH
provider "oci" {
  region = var.region
}

locals {
  common_tags = {
    Project   = "GeoMeteo"
    ManagedBy = "Terraform"
  }
}

# Récupération automatique de la première Availability Domain de la région
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_ocid
}

# 1. Réseau : VCN avec résolution DNS activée
resource "oci_core_vcn" "weather_vcn" {
  compartment_id = var.compartment_ocid
  display_name   = "weather-portfolio-vcn"
  cidr_blocks    = ["10.0.0.0/16"]
  dns_label      = "geometeovcn"
  freeform_tags  = local.common_tags
}

# 2. Accès Internet : Passerelle et table de routage
resource "oci_core_internet_gateway" "weather_igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.weather_vcn.id
  display_name   = "weather-portfolio-igw"
  enabled        = true
  freeform_tags  = local.common_tags
}

resource "oci_core_route_table" "weather_route_table" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.weather_vcn.id
  display_name   = "weather-portfolio-rt"
  freeform_tags  = local.common_tags

  route_rules {
    description       = "Routage du trafic sortant vers Internet"
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.weather_igw.id
  }
}

# 3. Pare-feu : Security List explicite (le défaut OCI bloque le port 80)
resource "oci_core_security_list" "weather_sl" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.weather_vcn.id
  display_name   = "weather-portfolio-sl"
  freeform_tags  = local.common_tags

  # Trafic entrant : uniquement HTTP sur le port 80 (pas de SSH exposé)
  ingress_security_rules {
    description = "Autoriser le trafic HTTP entrant vers GeoMeteo"
    protocol    = "6" # TCP
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    stateless   = false

    tcp_options {
      min = 80
      max = 80
    }
  }

  # Trafic sortant : autorisé pour le pull d'image, le DNS et les appels HTTPS OpenWeather
  egress_security_rules {
    description      = "Autoriser le trafic sortant (pull image, DNS, API OpenWeather)"
    protocol         = "all"
    destination      = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
    stateless        = false
  }
}

# 4. Sous-réseau public avec pare-feu et DNS attachés
resource "oci_core_subnet" "weather_subnet" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.weather_vcn.id
  display_name               = "weather-portfolio-subnet"
  cidr_block                 = "10.0.1.0/24"
  dns_label                  = "geometeosub"
  prohibit_public_ip_on_vnic = false
  route_table_id             = oci_core_route_table.weather_route_table.id
  security_list_ids          = [oci_core_security_list.weather_sl.id]
  freeform_tags              = local.common_tags
}

# 5. Conteneur managé : OCI Container Instance
# Note PoC : la clé API est injectée en variable d'environnement ; en production OCI,
# on couplerait OCI Vault avec un Dynamic Group dédié.
resource "oci_container_instances_container_instance" "weather_app" {
  compartment_id           = var.compartment_ocid
  display_name             = "weather-dashboard-ci"
  availability_domain      = data.oci_identity_availability_domains.ads.availability_domains[0].name
  container_restart_policy = "ALWAYS"
  shape                    = var.shape
  freeform_tags            = local.common_tags

  shape_config {
    ocpus         = var.ocpus
    memory_in_gbs = var.memory_in_gbs
  }

  vnics {
    subnet_id             = oci_core_subnet.weather_subnet.id
    display_name          = "weather-vnic"
    is_public_ip_assigned = true
  }

  containers {
    display_name = "weather-container"
    image_url    = var.image_url

    environment_variables = {
      API_KEY = var.openweather_api_key
    }

    health_checks {
      name                     = "geometeo-health"
      health_check_type        = "HTTP"
      path                     = "/health"
      port                     = 80
      initial_delay_in_seconds = 5
      interval_in_seconds      = 15
      timeout_in_seconds       = 3
      failure_threshold        = 3
      failure_action           = "KILL"
    }
  }
}

# Récupération des détails de l'interface réseau pour exposer l'IP publique
data "oci_core_vnic" "weather_vnic" {
  vnic_id = oci_container_instances_container_instance.weather_app.vnics[0].vnic_id
}