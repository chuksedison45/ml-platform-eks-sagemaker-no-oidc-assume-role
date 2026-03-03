# CI/CD without OIDC (assume-role pattern):
# - Create a minimal IAM user for GitHub Actions (long-lived keys).
# - The user assumes an IAM role that has the permissions required for deployment.
#
# This avoids granting broad permissions directly to the IAM user.

# Bootstrap user (keys live in GitHub Secrets)
resource "aws_iam_user" "github_actions" {
  name = "${var.project_name}-github-actions"
}

# Deploy role (assumed by github_actions user)
data "aws_iam_policy_document" "github_deploy_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [aws_iam_user.github_actions.arn]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name               = "${var.project_name}-github-deploy-role"
  assume_role_policy = data.aws_iam_policy_document.github_deploy_trust.json
}

# Permissions for deploy role: ECR push + EKS cluster describe
data "aws_iam_policy_document" "github_deploy_policy" {
  statement {
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
      "ecr:BatchGetImage",
      "ecr:DescribeRepositories",
      "ecr:ListImages"
    ]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "eks:DescribeCluster"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "github_deploy" {
  name   = "${var.project_name}-github-deploy-policy"
  policy = data.aws_iam_policy_document.github_deploy_policy.json
}

resource "aws_iam_role_policy_attachment" "github_deploy_attach" {
  role       = aws_iam_role.github_deploy.name
  policy_arn = aws_iam_policy.github_deploy.arn
}

# Allow the IAM user to assume the deploy role (nothing else)
data "aws_iam_policy_document" "github_assume_role_only" {
  statement {
    effect    = "Allow"
    actions   = ["sts:AssumeRole"]
    resources = [aws_iam_role.github_deploy.arn]
  }
}

resource "aws_iam_policy" "github_assume_role_only" {
  name   = "${var.project_name}-github-assume-role-only"
  policy = data.aws_iam_policy_document.github_assume_role_only.json
}

resource "aws_iam_user_policy_attachment" "github_assume_attach" {
  user       = aws_iam_user.github_actions.name
  policy_arn = aws_iam_policy.github_assume_role_only.arn
}

# Map deploy role to EKS cluster admin so kubectl apply works in CI/CD
resource "aws_eks_access_entry" "github_role" {
  cluster_name  = module.eks.cluster_name
  principal_arn = aws_iam_role.github_deploy.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "github_role_admin" {
  cluster_name  = module.eks.cluster_name
  principal_arn = aws_iam_role.github_deploy.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}

# Separate IAM user for pods (no IRSA in restricted environment).
# Create access keys manually and store them as GitHub Secrets:
# - POD_AWS_ACCESS_KEY_ID
# - POD_AWS_SECRET_ACCESS_KEY
resource "aws_iam_user" "sagemaker_invoke" {
  name = "${var.project_name}-sagemaker-invoke"
}

data "aws_iam_policy_document" "invoke_sagemaker" {
  statement {
    effect = "Allow"
    actions = [
      "sagemaker:InvokeEndpoint"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "invoke_sagemaker" {
  name   = "${var.project_name}-invoke-sagemaker"
  policy = data.aws_iam_policy_document.invoke_sagemaker.json
}

resource "aws_iam_user_policy_attachment" "sagemaker_invoke_attach" {
  user       = aws_iam_user.sagemaker_invoke.name
  policy_arn = aws_iam_policy.invoke_sagemaker.arn
}
