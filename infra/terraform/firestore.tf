resource "google_firestore_database" "main" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.required]
}

# Collections (rule_configs, notification_configs, agent_state) are created on
# first document write. Default rules are seeded via infra/scripts/seed_firestore.py.
