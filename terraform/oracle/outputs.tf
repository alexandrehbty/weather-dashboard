# Output

# On va chercher les détails de l'interface réseau pour récupérer l'IP
data "oci_core_vnic" "weather_vnic" {
  vnic_id = oci_container_instances_container_instance.weather_app.vnics[0].vnic_id
}

# On affiche l'IP récupérée
output "public_ip" {
  value       = "http://${data.oci_core_vnic.weather_vnic.public_ip_address}"
  description = "L'adresse IP publique du conteneur Oracle Cloud"
}