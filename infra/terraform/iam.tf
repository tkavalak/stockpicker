# Default Compute Engine SA is used by Cloud Run revisions unless a custom SA is set.
# data.google_project.current is defined in versions.tf
resource "google_project_iam_member" "cloud_run_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"

  depends_on = [google_project_service.required]
}
