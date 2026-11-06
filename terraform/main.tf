# ==============================================================================
# FoodBridge Production Infrastructure as Code (Terraform)
# Provisions AWS VPC, Aurora Serverless PostGIS, ElastiCache Redis, ECS Fargate,
# and S3 Encrypted Upload Storage.
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "FoodBridge"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Compliance  = "42-USC-1791"
    }
  }
}

# ------------------------------------------------------------------------------
# 1. Virtual Private Cloud (VPC) & Multi-AZ Subnets
# ------------------------------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "foodbridge-vpc-${var.environment}"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 4, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "foodbridge-public-${count.index + 1}"
    Tier = "Public"
  }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 4, count.index + 4)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "foodbridge-private-${count.index + 1}"
    Tier = "Application"
  }
}

resource "aws_subnet" "database" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 4, count.index + 8)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "foodbridge-database-${count.index + 1}"
    Tier = "Database"
  }
}

# ------------------------------------------------------------------------------
# 2. S3 Bucket for Isolated Document & Media Uploads
# ------------------------------------------------------------------------------
resource "aws_kms_key" "s3_storage_key" {
  description             = "KMS Key for FoodBridge Encrypted Uploads"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_s3_bucket" "uploads" {
  bucket        = "foodbridge-uploads-${var.environment}-${var.aws_account_id}"
  force_destroy = false
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads_sse" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.s3_storage_key.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "uploads_block" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ------------------------------------------------------------------------------
# 3. Aurora PostgreSQL 16 + PostGIS Spatial Cluster
# ------------------------------------------------------------------------------
resource "aws_db_subnet_group" "aurora_subnet_group" {
  name       = "foodbridge-aurora-subnets"
  subnet_ids = aws_subnet.database[*].id
}

resource "aws_rds_cluster" "aurora_postgis" {
  cluster_identifier     = "foodbridge-aurora-${var.environment}"
  engine                 = "aurora-postgresql"
  engine_version         = "16.3"
  database_name          = "foodbridge"
  master_username        = "foodbridge_admin"
  manage_master_user_password = true
  db_subnet_group_name   = aws_db_subnet_group.aurora_subnet_group.name
  skip_final_snapshot    = (var.environment == "staging")
  storage_encrypted      = true

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 4.0
  }
}

resource "aws_rds_cluster_instance" "aurora_instances" {
  count               = 2
  cluster_identifier  = aws_rds_cluster.aurora_postgis.id
  instance_class      = "db.serverless"
  engine              = aws_rds_cluster.aurora_postgis.engine
  engine_version      = aws_rds_cluster.aurora_postgis.engine_version
  publicly_accessible = false
}

