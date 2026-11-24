#Azure
output "app_url" {
  value       = "https://${azurerm_container_app.weather_app.ingress[0].fqdn}"
  description = "URL HTTPS publique stable de l'application sur Azure Container Apps"
}

output "latest_revision_fqdn" {
  value       = "https://${azurerm_container_app.weather_app.latest_revision_fqdn}"
  description = "URL HTTPS dédiée à la dernière révision déployée"
}