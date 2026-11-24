#Hetzner
output "server_ip" {
  value       = hcloud_server.weather_server.ipv4_address
  description = "Adresse IPv4 publique du serveur Hetzner Cloud"
}

output "app_url" {
  value       = "http://${hcloud_server.weather_server.ipv4_address}"
  description = "URL d'accès HTTP à l'application GeoMeteo sur Hetzner Cloud"
}