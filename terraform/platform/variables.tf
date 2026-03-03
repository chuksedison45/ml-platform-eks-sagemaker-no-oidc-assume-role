variable "region" { type = string }
variable "project_name" { type = string }
variable "cluster_name" { type = string }

variable "kubernetes_version" {
  type    = string
  default = "1.29"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.20.0.0/20", "10.20.16.0/20", "10.20.32.0/20"]
}

variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.20.48.0/20", "10.20.64.0/20", "10.20.80.0/20"]
}

variable "dataset_bucket_name" {
  type        = string
  description = "Optional: provide a fixed dataset bucket name; otherwise a name is generated."
  default     = ""
}
