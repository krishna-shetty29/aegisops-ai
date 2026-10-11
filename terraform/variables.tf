variable "resource_group_name" {
  description = "Name of the Azure resource group for this project."
  type        = string
  default     = "rg-autonomous-ai-devops-staging"
}

variable "location" {
  description = "Azure region where future infrastructure would be created."
  type        = string
  default     = "centralindia"
}

variable "enable_acr" {
  description = "Whether Azure Container Registry should be created in a future reviewed deployment."
  type        = bool
  default     = false
}

variable "enable_aks" {
  description = "Whether Azure Kubernetes Service should be created in a future reviewed deployment."
  type        = bool
  default     = false
}

variable "enable_monitoring" {
  description = "Whether Azure monitoring resources should be created in a future reviewed deployment."
  type        = bool
  default     = false
}

variable "aks_name" {
  description = "Name of the future AKS cluster."
  type        = string
  default     = "aks-autonomous-ai-devops"
}

variable "aks_dns_prefix" {
  description = "DNS prefix for the future AKS cluster."
  type        = string
  default     = "autonomous-ai-devops"
}

variable "aks_node_count" {
  description = "Initial AKS node count."
  type        = number
  default     = 1
}

variable "aks_node_size" {
  description = "Azure VM size for AKS nodes."
  type        = string
  default     = "Standard_B2s"
}