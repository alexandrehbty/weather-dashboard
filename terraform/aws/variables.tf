#AWS

variable "region" {
  description = "Région AWS de déploiement (ex: eu-west-3 pour Paris)"
  type        = string
  default     = "eu-west-3"
}

variable "image_url" {
  description = "URL de l'image Docker sur Amazon ECR Public (ex: public.ecr.aws/<alias>/weather-dashboard:latest)"
  type        = string

  validation {
    condition     = startswith(var.image_url, "public.ecr.aws/")
    error_message = "Avec image_repository_type = ECR_PUBLIC, AWS App Runner exige une image hébergée sur public.ecr.aws/ (ghcr.io non supporté directement)."
  }
}

variable "openweather_api_key" {
  description = "Clé API OpenWeather (injectable via TF_VAR_openweather_api_key)"
  type        = string
  sensitive   = true
}

variable "cpu" {
  description = "Allocation CPU App Runner (256 = 0.25 vCPU, 512 = 0.5 vCPU, 1024 = 1 vCPU)"
  type        = string
  default     = "256"
}

variable "memory" {
  description = "Allocation mémoire App Runner en Mo (512, 1024, 2048...)"
  type        = string
  default     = "512"
}