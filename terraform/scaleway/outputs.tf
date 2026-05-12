# Output : Afficher l'URL pour accéder au site

output "app_url" {
  value       = "https://${scaleway_container.weather_app.domain_name}"
  description = "L'URL publique générée par Scaleway Serverless Containers"
}