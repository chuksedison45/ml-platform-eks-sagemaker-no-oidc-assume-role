locals {
  name = var.project_name
  tags = {
    Project = var.project_name
  }
}

# VPC
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name}-vpc"
  cidr = var.vpc_cidr

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  public_subnets  = var.public_subnet_cidrs
  private_subnets = var.private_subnet_cidrs

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = local.tags
}

# EKS
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  enable_irsa                              = false
  enable_cluster_creator_admin_permissions = true
  eks_managed_node_groups = {
    default = {
      instance_types = ["t3.large"]
      min_size       = 2
      max_size       = 4
      desired_size   = 2
    }
  }

  tags = local.tags
}

# Dataset bucket
resource "aws_s3_bucket" "datasets" {
  bucket = var.dataset_bucket_name != "" ? var.dataset_bucket_name : "${var.project_name}-datasets-${data.aws_caller_identity.current.account_id}"
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "datasets" {
  bucket = aws_s3_bucket.datasets.id
  versioning_configuration { status = "Enabled" }
}

# ECR repos for services
locals {
  repos = ["fraud-service", "recs-service", "forecast-service", "gateway", "dashboard"]
}

resource "aws_ecr_repository" "repos" {
  for_each = toset(local.repos)
  name     = "${var.project_name}/${each.value}"
  image_scanning_configuration { scan_on_push = true }
  tags = local.tags
}

