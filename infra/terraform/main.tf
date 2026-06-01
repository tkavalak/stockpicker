locals {
  name_prefix = "stock-picker-${var.environment}"
  labels = {
    app         = "stock-picker"
    environment = var.environment
    managed_by  = "terraform"
    work_order  = "wo-4"
  }
}

resource "google_project_service" "required" {
  for_each = var.enable_apis ? toset([
    "pubsub.googleapis.com",
    "firestore.googleapis.com",
    "redis.googleapis.com",
    "secretmanager.googleapis.com",
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "bigquery.googleapis.com",
  ]) : toset([])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
