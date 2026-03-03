output "cluster_name" { value = module.eks.cluster_name }
output "cluster_region" { value = var.region }
output "datasets_bucket" { value = aws_s3_bucket.datasets.bucket }

output "ecr_repo_urls" {
  value = { for k, v in aws_ecr_repository.repos : k => v.repository_url }
}


output "github_deploy_role_arn" { value = aws_iam_role.github_deploy.arn }

output "github_actions_user_arn" { value = aws_iam_user.github_actions.arn }

output "sagemaker_invoke_user_arn" { value = aws_iam_user.sagemaker_invoke.arn }
