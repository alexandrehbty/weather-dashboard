# Output : Afficher l'adresse IP pour accéder au site une fois déployé

output "public_ip" {
  value       = alicloud_eci_container_group.weather_app.internet_ip
  description = "L'adresse IP publique générée pour accéder à l'application sur Alibaba Cloud"
}