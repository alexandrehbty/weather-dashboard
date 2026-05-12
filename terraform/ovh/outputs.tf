# Output : Afficher l'adresse IP pour accéder au site

output "server_ip" {
  value       = "http://${openstack_compute_instance_v2.weather_server.access_ip_v4}"
  description = "L'adresse IP publique de ton serveur OVHcloud"
}