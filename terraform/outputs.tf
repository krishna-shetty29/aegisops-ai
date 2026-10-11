output "resource_group_name" {
  description = "Name of the Azure resource group managed by this configuration."
  value       = azurerm_resource_group.project.name
}

output "resource_group_location" {
  description = "Azure region configured for the resource group."
  value       = azurerm_resource_group.project.location
}

output "aks_name" {
  description = "Name planned for the future AKS cluster."
  value       = var.aks_name
}

output "aks_enabled" {
  description = "Whether the AKS resource is enabled for a future reviewed deployment."
  value       = var.enable_aks
}

output "acr_enabled" {
  description = "Whether Azure Container Registry is enabled for a future reviewed deployment."
  value       = var.enable_acr
}

output "monitoring_enabled" {
  description = "Whether Azure monitoring resources are enabled for a future reviewed deployment."
  value       = var.enable_monitoring
}