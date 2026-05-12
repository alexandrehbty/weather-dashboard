# Output

output "app_url" {
  value       = "https://${azurerm_container_app.weather_app.latest_revision_fqdn}"
  description = "L'URL publique générée par Azure Container Apps"
}