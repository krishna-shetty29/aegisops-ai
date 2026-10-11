# AKS is disabled by default.
# It will not be created unless enable_aks is changed to true
# and a human reviews and applies the Terraform plan.

resource "azurerm_kubernetes_cluster" "project" {
  count = var.enable_aks ? 1 : 0

  name                = var.aks_name
  location            = azurerm_resource_group.project.location
  resource_group_name = azurerm_resource_group.project.name
  dns_prefix          = var.aks_dns_prefix

  default_node_pool {
    name       = "system"
    node_count = var.aks_node_count
    vm_size    = var.aks_node_size
  }

  identity {
    type = "SystemAssigned"
  }

  tags = {
    project     = "autonomous-ai-devops-engineer"
    environment = "staging"
    managed_by  = "terraform"
  }
}