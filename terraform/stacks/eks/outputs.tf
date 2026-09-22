output "eks_cluster_id" {
  description = "El ID del clúster EKS desplegado."
  value       = module.my_eks_cluster.cluster_id 
}

output "eks_cluster_arn" {
  description = "El ARN del clúster EKS desplegado."
  value       = module.my_eks_cluster.cluster_arn 
}

output "eks_cluster_endpoint" {
  description = "El endpoint del clúster EKS desplegado."
  value       = module.my_eks_cluster.cluster_endpoint 
}

output "eks_cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data para conectarse al clúster EKS."
  value       = module.my_eks_cluster.cluster_certificate_authority_data 
  sensitive   = true
}

output "eks_cluster_oidc_issuer_url" {
  description = "La URL del OpenID Connect identity provider del clúster EKS."
  value       = module.my_eks_cluster.cluster_oidc_issuer_url #
}

output "eks_node_group_autoscaling_group_names" {
  description = "Nombres de los Auto Scaling Groups de los nodos gestionados por EKS."
  value       = module.my_eks_cluster.eks_managed_node_groups_autoscaling_group_names 
}

output "secret_token" {
  description = "Token de autenticacion de TrueNative (SECRET_TOKEN). Proviene del secret 'secrets-pipeline-native-map' de AWS Secrets Manager, poblado por el pipeline desde los secrets del ambiente de GitHub. El pipeline lo exporta como variable de entorno para el envsubst de los manifiestos k8s (k8s_entrega3/k8s-true-native-deployment.yml)."
  value       = local.pipeline_native_map["SECRET_TOKEN"]
  sensitive   = true
}