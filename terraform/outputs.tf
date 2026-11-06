output "vpc_id" {
  description = "ID of the provisioned VPC"
  value       = aws_vpc.main.id
}

output "aurora_cluster_endpoint" {
  description = "Primary writer endpoint for PostgreSQL + PostGIS cluster"
  value       = aws_rds_cluster.aurora_postgis.endpoint
}

output "s3_upload_bucket_name" {
  description = "Name of the encrypted S3 storage bucket for inspection media"
  value       = aws_s3_bucket.uploads.id
}

