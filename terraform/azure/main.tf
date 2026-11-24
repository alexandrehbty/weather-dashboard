#Azure
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

# Authentification via Azure CLI (`az login`) ou Service Principal.
# Avec azurerm >= 4.0, définir ARM_SUBSCRIPTION_ID pour plan/apply :
# export ARM_SUBSCRIPTION_ID="00000000-0000-0000-0000-000000000000"
provider "azurerm" {
  features {}
}

locals {
  common_tags = {
    Project   = "GeoMeteo"
    ManagedBy = "Terraform"
  }
}

# 1. Groupe de ressources
resource "azurerm_resource_group" "weather_rg" {
  name     = "rg-weather-portfolio"
  location = var.location
  tags     = local.common_tags
}

# 2. Observabilité : Log Analytics Workspace (requis par Container Apps)
resource "azurerm_log_analytics_workspace" "weather_logs" {
  name                = "law-weather-portfolio"
  location            = azurerm_resource_group.weather_rg.location
  resource_group_name = azurerm_resource_group.weather_rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.common_tags
}

# 3. Environnement d'hébergement Serverless (plan Consumption)
resource "azurerm_container_app_environment" "weather_env" {
  name                       = "cae-weather-portfolio"
  location                   = azurerm_resource_group.weather_rg.location
  resource_group_name        = azurerm_resource_group.weather_rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.weather_logs.id
  tags                       = local.common_tags
}

# 4. Application : Azure Container Apps (HTTPS géré nativement)
resource "azurerm_container_app" "weather_app" {
  name                         = "ca-weather-dashboard"
  container_app_environment_id = azurerm_container_app_environment.weather_env.id
  resource_group_name          = azurerm_resource_group.weather_rg.name
  revision_mode                = "Single"
  tags                         = local.common_tags

  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 80
    transport                  = "auto"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  secret {
    name  = "openweather-api-key"
    value = var.openweather_api_key
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    container {
      name   = "weather-container"
      image  = var.image_url
      cpu    = var.cpu
      memory = var.memory

      env {
        name        = "API_KEY"
        secret_name = "openweather-api-key"
      }

      readiness_probe {
        transport               = "HTTP"
        path                    = "/health"
        port                    = 80
        initial_delay           = 5
        interval_seconds        = 10
        timeout                 = 3
        failure_count_threshold = 3
      }

      liveness_probe {
        transport               = "HTTP"
        path                    = "/health"
        port                    = 80
        initial_delay           = 15
        interval_seconds        = 20
        timeout                 = 3
        failure_count_threshold = 3
      }
    }
  }
}