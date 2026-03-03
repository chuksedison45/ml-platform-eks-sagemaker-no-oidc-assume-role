variable "region" {
  type    = string
  default = "us-west-2"
}

variable "state_bucket_name" {
  type        = string
  description = "Globally unique bucket name for terraform state"
}

variable "lock_table_name" {
  type        = string
  description = "DynamoDB table name for terraform state locking"
  default     = "terraform-locks"
}
