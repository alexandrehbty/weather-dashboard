#GCP
output "app_url" {
  value       = google_cloud_run_v2_service.weather_dashboard.uri
  description = "URL HTTPS publique générée par Google Cloud Run"
}

output "service_account_email" {
  value       = google_service_account.cloud_run_sa.email
  description = "Adresse email du compte de service dédié à Cloud Run"
}