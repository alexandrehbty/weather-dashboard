# Output

output "app_url" {
  value       = "https://${aws_apprunner_service.weather_dashboard.service_url}"
  description = "L'URL publique générée par AWS App Runner"
}