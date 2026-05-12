# Output : Afficher l'adresse IP pour accéder au site

output "server_ip" {
  value       = "http://${hcloud_server.weather_server.ipv4_address}"
  description = "L'adresse IP publique de ton serveur Hetzner"
}