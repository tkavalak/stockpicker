resource "google_bigquery_dataset" "stock_picker" {
  dataset_id = "stock_picker"
  location   = var.region
  labels     = local.labels

  depends_on = [google_project_service.required]
}

resource "google_bigquery_table" "notification_audit" {
  dataset_id = google_bigquery_dataset.stock_picker.dataset_id
  table_id   = "notification_audit"
  labels     = local.labels

  schema = jsonencode([
    { name = "decision_id", type = "STRING", mode = "REQUIRED" },
    { name = "channel", type = "STRING", mode = "REQUIRED" },
    { name = "symbol", type = "STRING", mode = "REQUIRED" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "http_status", type = "INTEGER", mode = "NULLABLE" },
    { name = "latency_ms", type = "INTEGER", mode = "NULLABLE" },
    { name = "dispatched_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])

  depends_on = [google_bigquery_dataset.stock_picker]
}
