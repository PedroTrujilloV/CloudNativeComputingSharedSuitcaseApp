module "app_bucket" {
  source = "../../modules/storage"

  bucket_name        = var.bucket_name
  environment        = var.environment
  versioning_enabled = true
  force_destroy      = false

  tags = {
    Project = "grupo33"
    Stack   = "storage"
    Owner   = var.owner
  }
}
