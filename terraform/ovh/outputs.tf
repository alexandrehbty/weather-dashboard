#OVH
output "server_ip" {
  value       = openstack_compute_instance_v2.weather_server.access_ip_v4
  description = "Adresse IPv4 publique du serveur OVHcloud"
}

output "app_url" {
  value       = "http://${openstack_compute_instance_v2.weather_server.access_ip_v4}"
  description = "URL d'accès HTTP à l'application GeoMeteo sur OVHcloud"
}