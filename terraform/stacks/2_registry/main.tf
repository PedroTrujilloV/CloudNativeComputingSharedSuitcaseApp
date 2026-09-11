
# This can be improved by using a for_each loop if the number of repositories increases
module "users_repository" {
  source = "../../modules/repository"
  keep_tags_number = var.keep_tags_number
  repository_name  = var.users_repository_name
}

module "posts_repository" {
  source = "../../modules/repository"
  keep_tags_number = var.keep_tags_number
  repository_name  = var.posts_repository_name
}

module "offers_repository" {
  source = "../../modules/repository"
  keep_tags_number = var.keep_tags_number
  repository_name  = var.offers_repository_name
}

module "routes_repository" {
  source = "../../modules/repository"
  keep_tags_number = var.keep_tags_number
  repository_name  = var.routes_repository_name
}

module "scores_repository" {
  source = "../../modules/repository"
  keep_tags_number = var.keep_tags_number
  repository_name  = var.scores_repository_name
}

module "rf003_repository" {
  source = "../../modules/repository"
  keep_tags_number = var.keep_tags_number
  repository_name  = var.rf003_repository_name
}

module "rf004_repository" {
  source = "../../modules/repository"
  keep_tags_number = var.keep_tags_number
  repository_name  = var.rf004_repository_name
}

module "rf005_repository" {
  source = "../../modules/repository"
  keep_tags_number = var.keep_tags_number
  repository_name  = var.rf005_repository_name
}

