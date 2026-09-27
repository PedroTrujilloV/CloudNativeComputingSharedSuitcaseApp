terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      # version = "~> 5.0"
    }
  }
  backend "s3" {
    # Filled in via -backend-config=backend.tfvars at `terraform init` time
  }
}

provider "aws" {
  region = var.aws_region
}
