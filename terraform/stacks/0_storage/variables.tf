variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (e.g. student1, tutor)"
  type        = string
}

variable "bucket_name" {
  description = "Globally unique S3 bucket name for this environment"
  type        = string
}

variable "owner" {
  description = "Owner of the resources, generally the user or team name."
  type        = string
}
