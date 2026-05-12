# 1. Configuration du fournisseur Oracle Cloud
provider "oci" {
  region = var.region
  # L'authentification (tenancy_ocid, user_ocid, private_key) est 
  # généralement lue automatiquement via les variables d'environnement locales
}

# Récupération de la première Zone de Disponibilité du datacenter
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_ocid
}

# 2. Création du Réseau (VCN - Virtual Cloud Network)
resource "oci_core_vcn" "weather_vcn" {
  compartment_id = var.compartment_ocid
  display_name   = "weather-portfolio-vcn"
  cidr_block     = "10.0.0.0/16"
}

# 3. Accès à Internet : Création de la passerelle et de la table de routage
resource "oci_core_internet_gateway" "weather_igw" {
  compartment_id = var.compartment_ocid
  display_name   = "weather-portfolio-igw"
  vcn_id         = oci_core_vcn.weather_vcn.id
}

resource "oci_core_route_table" "weather_route_table" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.weather_vcn.id
  display_name   = "weather-portfolio-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.weather_igw.id
  }
}

# 4. Création du Sous-réseau Public
resource "oci_core_subnet" "weather_subnet" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.weather_vcn.id
  display_name      = "weather-portfolio-subnet"
  cidr_block        = "10.0.1.0/24"
  route_table_id    = oci_core_route_table.weather_route_table.id
  
  # Pare-feu basique géré directement via une liste de sécurité par défaut
}

# 5. Le Conteneur : OCI Container Instance (Serverless)
resource "oci_container_instances_container_instance" "weather_app" {
  compartment_id           = var.compartment_ocid
  display_name             = "weather-dashboard-ci"
  availability_domain      = data.oci_identity_availability_domains.ads.availability_domains[0].name
  container_restart_policy = "ALWAYS"
  shape                    = "CI.Standard.E4.Flex" # Type de processeur basique

  shape_config {
    ocpus         = 1
    memory_in_gbs = 2
  }

  vnics {
    subnet_id             = oci_core_subnet.weather_subnet.id
    display_name          = "weather-vnic"
    is_public_ip_assigned = true
  }

  containers {
    display_name = "weather-container"
    image_url    = var.image_url

    # Injection de la clé API
    environment_variables = {
      API_KEY = var.openweather_api_key
    }
  }
  
  # Note de Senior : En production sur Oracle, on utiliserait le service OCI Vault 
  # pour injecter le secret, mais cela requiert la création de "Dynamic Groups" complexes.
}