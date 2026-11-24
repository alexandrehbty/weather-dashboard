#Alibaba

output "public_ip" {
  value       = alicloud_eci_container_group.weather_app.internet_ip
  description = "Adresse IP publique attribuée à l'instance ECI"
}

output "app_url" {
  value       = "http://${alicloud_eci_container_group.weather_app.internet_ip}"
  description = "URL d'accès HTTP à l'application GeoMeteo sur Alibaba Cloud"
}