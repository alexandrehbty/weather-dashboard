# Output : Afficher l'URL d'accès

output "app_url" {
  value       = google_cloud_run_v2_service.weather_dashboard.uri
  description = "L'URL publique générée par Google Cloud Run"
}