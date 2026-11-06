variable "aws_region" {
  description = "AWS deployment region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (staging or production)"
  type        = string
  default     = "production"
}

variable "aws_account_id" {
  description = "AWS Account ID used for global unique S3 bucket naming"
  type        = string
  default     = "123456789012"
}

variable "domain_name" {
  description = "Production custom domain"
  type        = string
  default     = "foodbridge.org"
}

