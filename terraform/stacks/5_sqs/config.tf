# stack/app/config.tf
provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      "terraform" : true,
      "owner" : var.owner
    }
  }
}

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6"
    }
  }
}
