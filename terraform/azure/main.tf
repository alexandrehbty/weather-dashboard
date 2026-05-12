# 1. Configuration du fournisseur Azure
provider "azurerm" {
  # Le bloc features est obligatoire pour Azure, même s'il est vide
  features {}
}

# 2. La Boîte : Création du Groupe de Ressources
# Tout ce qui suit devra être rangé dans ce groupe.
resource "azurerm_resource_group" "weather_rg" {
  name     = "rg-weather-portfolio"
  location = var.location
}

# 3. Le journal de bord : Log Analytics Workspace
# Azure oblige les applications Serverless à avoir un espace pour écrire leurs logs.
resource "azurerm_log_analytics_workspace" "weather_logs" {
  name                = "law-weather-portfolio"
  location            = azurerm_resource_group.weather_rg.location
  resource_group_name = azurerm_resource_group.weather_rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# 4. L'Environnement d'hébergement
resource "azurerm_container_app_environment" "weather_env" {
  name                       = "cae-weather-portfolio"
  location                   = azurerm_resource_group.weather_rg.location
  resource_group_name        = azurerm_resource_group.weather_rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.weather_logs.id
}

# 5. L'Application : Azure Container Apps
resource "azurerm_container_app" "weather_app" {
  name                         = "ca-weather-dashboard"
  container_app_environment_id = azurerm_container_app_environment.weather_env.id
  resource_group_name          = azurerm_resource_group.weather_rg.name
  revision_mode                = "Single"

  # Le point d'entrée réseau (Ingress)
  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 80
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  # Déclaration sécurisée du secret
  secret {
    name  = "openweather-api-key"
    value = var.openweather_api_key
  }

  # Configuration du conteneur
  template {
    container {
      name   = "weather-container"
      image  = var.image_url
      cpu    = 0.5
      memory = "1Gi"

      # On injecte le secret dans les variables d'environnement
      env {
        name        = "API_KEY"
        secret_name = "openweather-api-key"
      }
    }
  }
}