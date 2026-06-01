resource "google_project_service_identity" "pubsub" {
  provider = google-beta
  service  = "pubsub.googleapis.com"
  depends_on = [google_project_service.required]
}

locals {
  pipeline_topics = [
    "raw-market-events",
    "enriched-market-events",
    "trigger-events",
    "alert-decisions",
  ]
  dlq_topics = [
    "raw-market-events-dlq",
    "enriched-market-events-dlq",
  ]
}

resource "google_pubsub_topic" "pipeline" {
  for_each = toset(local.pipeline_topics)

  name   = each.value
  labels = local.labels
}

resource "google_pubsub_topic" "dlq" {
  for_each = toset(local.dlq_topics)

  name   = each.value
  labels = local.labels
}

# Allow Pub/Sub to forward failed messages to dead-letter topics.
resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  for_each = google_pubsub_topic.dlq

  topic  = each.value.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_project_service_identity.pubsub.email}"

  depends_on = [google_project_service_identity.pubsub]
}

resource "google_pubsub_subscription" "market_event_processor" {
  name  = "market-event-processor-raw-market-events"
  topic = google_pubsub_topic.pipeline["raw-market-events"].id
  labels = local.labels

  ack_deadline_seconds = 60

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq["raw-market-events-dlq"].id
    max_delivery_attempts = 5
  }

  depends_on = [google_pubsub_topic_iam_member.dlq_publisher]
}

resource "google_pubsub_subscription" "rule_engine" {
  name  = "rule-engine-enriched-market-events"
  topic = google_pubsub_topic.pipeline["enriched-market-events"].id
  labels = local.labels

  ack_deadline_seconds = 60

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq["enriched-market-events-dlq"].id
    max_delivery_attempts = 5
  }

  depends_on = [google_pubsub_topic_iam_member.dlq_publisher]
}

resource "google_pubsub_subscription" "agentic_ai" {
  name  = "agentic-ai-trigger-events"
  topic = google_pubsub_topic.pipeline["trigger-events"].id
  labels = local.labels

  ack_deadline_seconds = 60
}

resource "google_pubsub_subscription" "notification" {
  name  = "notification-alert-decisions"
  topic = google_pubsub_topic.pipeline["alert-decisions"].id
  labels = local.labels

  ack_deadline_seconds = 60
}

# Pull subscriptions on DLQ topics for manual inspection / replay.
resource "google_pubsub_subscription" "raw_dlq_monitor" {
  name  = "raw-market-events-dlq-monitor"
  topic = google_pubsub_topic.dlq["raw-market-events-dlq"].id
  labels = local.labels

  ack_deadline_seconds = 600
}

resource "google_pubsub_subscription" "enriched_dlq_monitor" {
  name  = "enriched-market-events-dlq-monitor"
  topic = google_pubsub_topic.dlq["enriched-market-events-dlq"].id
  labels = local.labels

  ack_deadline_seconds = 600
}
