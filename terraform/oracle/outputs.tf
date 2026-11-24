#Oracle
output "public_ip" {
  value       = data.oci_core_vnic.weather_vnic.public_ip_address
  description = "Adresse IP publique attribuée au conteneur Oracle Cloud"
}

output "app_url" {
  value       = "http://${data.oci_core_vnic.weather_vnic.public_ip_address}"
  description = "URL d'accès HTTP à l'application GeoMeteo sur Oracle Cloud"
}