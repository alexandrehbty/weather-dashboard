#AWS

output "app_url" {
  value       = "https://${aws_apprunner_service.weather_dashboard.service_url}"
  description = "URL HTTPS publique générée par AWS App Runner"
}

output "service_arn" {
  value       = aws_apprunner_service.weather_dashboard.arn
  description = "ARN du service AWS App Runner"
}