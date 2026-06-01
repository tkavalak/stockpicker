# Serverless VPC Access so Cloud Run can reach Memorystore Redis on the private network.
resource "google_project_service" "vpcaccess" {
  count = var.enable_apis ? 1 : 0

  project            = var.project_id
  service            = "vpcaccess.googleapis.com"
  disable_on_destroy = false
}

resource "google_vpc_access_connector" "cloud_run" {
  name          = replace("${local.name_prefix}-conn", "-", "")
  region        = var.region
  network       = google_compute_network.main.name
  ip_cidr_range = "10.8.0.0/28"

  min_instances = 2
  max_instances = 3

  depends_on = [
    google_project_service.vpcaccess,
    google_compute_subnetwork.main,
  ]
}
