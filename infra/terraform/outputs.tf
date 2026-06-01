output "pubsub_topics" {
  description = "Pipeline and DLQ Pub/Sub topic names"
  value = {
    raw_market_events            = google_pubsub_topic.pipeline["raw-market-events"].name
    enriched_market_events       = google_pubsub_topic.pipeline["enriched-market-events"].name
    trigger_events               = google_pubsub_topic.pipeline["trigger-events"].name
    alert_decisions              = google_pubsub_topic.pipeline["alert-decisions"].name
    raw_market_events_dlq        = google_pubsub_topic.dlq["raw-market-events-dlq"].name
    enriched_market_events_dlq   = google_pubsub_topic.dlq["enriched-market-events-dlq"].name
  }
}

output "pubsub_subscriptions" {
  description = "Consumer and DLQ monitor subscription names"
  value = {
    market_event_processor = google_pubsub_subscription.market_event_processor.name
    rule_engine            = google_pubsub_subscription.rule_engine.name
    agentic_ai             = google_pubsub_subscription.agentic_ai.name
    notification           = google_pubsub_subscription.notification.name
    raw_dlq_monitor        = google_pubsub_subscription.raw_dlq_monitor.name
    enriched_dlq_monitor   = google_pubsub_subscription.enriched_dlq_monitor.name
  }
}

output "firestore_database" {
  description = "Firestore database name"
  value       = google_firestore_database.main.name
}

output "firestore_collections" {
  description = "Firestore collections used by the pipeline"
  value       = ["rule_configs", "notification_configs", "agent_state"]
}

output "redis" {
  description = "Memorystore Redis connection details"
  value = {
    instance_id         = google_redis_instance.main.id
    host                = google_redis_instance.main.host
    port                = google_redis_instance.main.port
    connection_string   = "${google_redis_instance.main.host}:${google_redis_instance.main.port}"
  }
  sensitive = false
}

output "secret_ids" {
  description = "Secret Manager secret IDs for pipeline config"
  value = {
    streaming_pipeline_config = google_secret_manager_secret.streaming_pipeline_config.secret_id
    redis_connection          = google_secret_manager_secret.redis_connection.secret_id
  }
}

output "streaming_config" {
  description = "Full streaming pipeline config (also stored in Secret Manager)"
  value       = local.streaming_config
  sensitive   = true
}

output "vpc_network" {
  description = "VPC used by Memorystore Redis"
  value       = google_compute_network.main.name
}

output "vpc_connector" {
  description = "Serverless VPC connector id for Cloud Run (Memorystore access)"
  value       = google_vpc_access_connector.cloud_run.id
}

output "vpc_connector_name" {
  description = "Short connector name for gcloud run deploy --vpc-connector"
  value       = google_vpc_access_connector.cloud_run.name
}

output "bigquery_notification_audit" {
  description = "BigQuery notification audit table reference"
  value = {
    dataset_id = google_bigquery_dataset.stock_picker.dataset_id
    table_id   = google_bigquery_table.notification_audit.table_id
    table_ref  = "${var.project_id}.${google_bigquery_dataset.stock_picker.dataset_id}.${google_bigquery_table.notification_audit.table_id}"
  }
}
