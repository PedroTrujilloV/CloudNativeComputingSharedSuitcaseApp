variable "region" { 
  description = "La región de AWS donde se desplegarán los recursos."
  type        = string
  nullable    = false
}

variable "cluster_name" {
  description = "El nombre del clúster EKS."
  type        = string
}

variable "k8s_cluster_version" {
  description = "La versión de Kubernetes para el clúster EKS."
  type        = string
}

variable "cluster_endpoint_public_access" {
  description = "Habilita o deshabilita el acceso público al endpoint del clúster EKS."
  type        = bool
}

variable "owner" {
  description = "Dueño de los recursos. Para propósito acadmémico."
  type        = string
  nullable    = false
}


variable "db_username" {
  description = "Unused in this stack; declared only because the course evaluation workflow always passes it via -var."
  type        = string
  sensitive   = true
  default     = null
}

variable "db_password" {
  description = "Unused in this stack; declared only because the course evaluation workflow always passes it via -var."
  type        = string
  sensitive   = true
  default     = null
}