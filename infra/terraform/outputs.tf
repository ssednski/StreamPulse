output "url" {
  description = "Public URL of the dashboard and API."
  value       = "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "ecr_repository_url" {
  description = "Push the API image here."
  value       = aws_ecr_repository.api.repository_url
}

output "web_bucket" {
  description = "Upload the built dashboard (frontend/dist) here."
  value       = aws_s3_bucket.web.bucket
}

output "cloudfront_distribution_id" {
  description = "Invalidate this after uploading a new dashboard build."
  value       = aws_cloudfront_distribution.main.id
}

output "ecs_cluster" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service" {
  value = aws_ecs_service.api.name
}

output "ingest_api_key_secret_arn" {
  description = "Secrets Manager ARN of the X-API-Key the simulator must send."
  value       = aws_secretsmanager_secret.ingest_api_key.arn
}
