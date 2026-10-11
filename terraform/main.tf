# Root Azure resource group for the project.
#
# This configuration is only a design until a human runs
# terraform apply with an active Azure subscription.
# Do not run terraform apply automatically.

resource "azurerm_resource_group" "project" {
  name     = var.resource_group_name
  location = var.location

  tags = {
    project     = "autonomous-ai-devops-engineer"
    environment = "staging"
    managed_by  = "terraform"
  }
}