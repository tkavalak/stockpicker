resource "google_redis_instance" "main" {
  name               = "${local.name_prefix}-redis"
  tier               = "STANDARD_HA"
  memory_size_gb     = var.redis_memory_gb
  region             = var.region
  location_id        = "${var.region}-a"
  redis_version      = "REDIS_7_0"
  authorized_network = google_compute_network.main.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  labels = local.labels

  depends_on = [
    google_project_service.required,
    google_service_networking_connection.redis_private_vpc,
  ]
}
