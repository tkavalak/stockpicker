variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run, Pub/Sub, Firestore, and Redis"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment label (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "redis_memory_gb" {
  description = "Memorystore Redis memory size in GB"
  type        = number
  default     = 1
}

variable "enable_apis" {
  description = "Enable required GCP APIs via Terraform"
  type        = bool
  default     = true
}
