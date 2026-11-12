variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Name prefix for all resources."
  type        = string
  default     = "streampulse"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "api_image_tag" {
  description = "Tag of the API image in ECR to deploy (use the git SHA; the repository is immutable)."
  type        = string
}

variable "api_cpu" {
  description = "Fargate CPU units for the API task."
  type        = number
  default     = 256
}

variable "api_memory" {
  description = "Fargate memory (MiB) for the API task."
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Minimum (and initial) number of API tasks."
  type        = number
  default     = 2
}

variable "max_count" {
  description = "Maximum number of API tasks when autoscaling."
  type        = number
  default     = 4
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "RDS storage in GiB."
  type        = number
  default     = 20
}

variable "db_multi_az" {
  description = "Run the database in two availability zones."
  type        = bool
  default     = false
}

variable "db_deletion_protection" {
  description = "Protect the database from deletion (enable for anything you care about)."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the API."
  type        = number
  default     = 14
}

variable "cloudfront_price_class" {
  description = "CloudFront price class."
  type        = string
  default     = "PriceClass_100"
}
