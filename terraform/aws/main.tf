# 1. Configuration du fournisseur AWS
provider "aws" {
  region = var.region
}

# 2. Sécurité : Le Coffre-fort (AWS Secrets Manager)
resource "aws_secretsmanager_secret" "weather_api_key" {
  name                    = "weather-api-key-portfolio"
  recovery_window_in_days = 0 # Permet de supprimer le secret immédiatement si on détruit l'infra
}

resource "aws_secretsmanager_secret_version" "weather_api_key_version" {
  secret_id     = aws_secretsmanager_secret.weather_api_key.id
  secret_string = var.openweather_api_key
}

# 3. Permissions (IAM) : Donner à App Runner le droit de lire le secret
resource "aws_iam_role" "apprunner_instance_role" {
  name = "AppRunnerWeatherRole"

  # Qui a le droit de mettre ce badge ? (Le service App Runner)
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "tasks.apprunner.amazonaws.com"
      }
    }]
  })
}

# La règle associée au badge : Autoriser la lecture du coffre-fort précis
resource "aws_iam_role_policy" "apprunner_secrets_policy" {
  name = "AppRunnerSecretsPolicy"
  role = aws_iam_role.apprunner_instance_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "secretsmanager:GetSecretValue"
      Effect = "Allow"
      Resource = aws_secretsmanager_secret.weather_api_key.arn
    }]
  })
}

# 4. Le Service Serverless : AWS App Runner
resource "aws_apprunner_service" "weather_dashboard" {
  service_name = "weather-dashboard-prod"

  source_configuration {
    image_repository {
      image_identifier      = var.image_url
      image_repository_type = "ECR_PUBLIC" # On assume que ton image est publique pour le portfolio
      
      image_configuration {
        port = "80"
        
        # On injecte la clé API de manière sécurisée depuis le Secrets Manager
        runtime_environment_secrets = {
          API_KEY = aws_secretsmanager_secret.weather_api_key.arn
        }
      }
    }
    auto_deployments_enabled = false
  }

  instance_configuration {
    cpu               = "1024" # 1 vCPU
    memory            = "2048" # 2 Go RAM
    instance_role_arn = aws_iam_role.apprunner_instance_role.arn
  }
}