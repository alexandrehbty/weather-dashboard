#Scaleway
output "app_url" {
  value       = scaleway_container.weather_app.public_endpoint
  description = "URL HTTPS publique générée par Scaleway Serverless Containers"
}

output "container_status" {
  value       = scaleway_container.weather_app.status
  description = "Statut de déploiement du conteneur Scaleway"
}