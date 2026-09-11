variable "bucket_name" {
  description = "Globally unique S3 bucket name"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g. student1, tutor)"
  type        = string
}

variable "versioning_enabled" {
  description = "Enable S3 object versioning"
  type        = bool
  default     = true
}

variable "force_destroy" {
  description = "Allow bucket deletion even if it contains objects (use with care)"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags to merge into the bucket"
  type        = map(string)
  default     = {}
}
