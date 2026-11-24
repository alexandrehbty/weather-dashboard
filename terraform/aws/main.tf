#AWS

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# Authentification via variables d'environnement (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
# ou profil AWS CLI (~/.aws/credentials)
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "GeoMeteo"
      ManagedBy = "Terraform"
    }
  }
}

# 1. Coffre-fort : AWS Secrets Manager
resource "aws_secretsmanager_secret" "weather_api_key" {
  name                    = "weather-api-key-portfolio"
  recovery_window_in_days = 0 # Choix PoC : suppression immédiate lors d'un destroy (7-30j en prod)
}

resource "aws_secretsmanager_secret_version" "weather_api_key_version" {
  secret_id     = aws_secretsmanager_secret.weather_api_key.id
  secret_string = var.openweather_api_key
}

# 2. IAM : Rôle d'instance App Runner (principe du moindre privilège)
resource "aws_iam_role" "apprunner_instance_role" {
  name = "AppRunnerWeatherRole"

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

resource "aws_iam_role_policy" "apprunner_secrets_policy" {
  name = "AppRunnerSecretsPolicy"
  role = aws_iam_role.apprunner_instance_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action   = ["secretsmanager:GetSecretValue"]
      Effect   = "Allow"
      Resource = aws_secretsmanager_secret.weather_api_key.arn
    }]
  })
}

# 3. FinOps : Plafonnement explicite de l'auto-scaling (évite le défaut AWS à 25 instances)
resource "aws_apprunner_auto_scaling_configuration_version" "weather_scaling" {
  auto_scaling_configuration_name = "weather-dashboard-scaling"
  max_concurrency                 = 50
  min_size                        = 1
  max_size                        = 2
}

# 4. Service managé : AWS App Runner (HTTPS géré nativement)
resource "aws_apprunner_service" "weather_dashboard" {
  service_name                   = "weather-dashboard-prod"
  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.weather_scaling.arn

  source_configuration {
    image_repository {
      image_identifier      = var.image_url
      image_repository_type = "ECR_PUBLIC"

      image_configuration {
        port = "80"

        runtime_environment_secrets = {
          API_KEY = aws_secretsmanager_secret.weather_api_key.arn
        }
      }
    }
    auto_deployments_enabled = false
  }

  instance_configuration {
    cpu               = var.cpu
    memory            = var.memory
    instance_role_arn = aws_iam_role.apprunner_instance_role.arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 3
  }

  # Évite la race condition au démarrage avant l'écriture du secret ou l'attachement IAM
  depends_on = [
    aws_secretsmanager_secret_version.weather_api_key_version,
    aws_iam_role_policy.apprunner_secrets_policy,
  ]
}