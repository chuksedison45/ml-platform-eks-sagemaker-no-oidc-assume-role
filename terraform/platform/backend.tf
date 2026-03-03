terraform {
  backend "s3" {
    bucket         = "ed45-ml-tfstate-v1"
    key            = "ed45-ml-platform/terraform.tfstate"
    region         = "us-west-2"
    dynamodb_table = "ed45-ml-terraform-locks"
    encrypt        = true
  }
}
