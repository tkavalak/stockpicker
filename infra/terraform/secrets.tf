locals {
  streaming_config = {
    project_id  = var.project_id
    region      = var.region
    environment = var.environment
    pubsub = {
      topics = {
        raw_market_events      = google_pubsub_topic.pipeline["raw-market-events"].name
        enriched_market_events = google_pubsub_topic.pipeline["enriched-market-events"].name
        trigger_events         = google_pubsub_topic.pipeline["trigger-events"].name
        alert_decisions        = google_pubsub_topic.pipeline["alert-decisions"].name
        raw_market_events_dlq      = google_pubsub_topic.dlq["raw-market-events-dlq"].name
        enriched_market_events_dlq = google_pubsub_topic.dlq["enriched-market-events-dlq"].name
      }
      topic_paths = {
        raw_market_events      = google_pubsub_topic.pipeline["raw-market-events"].id
        enriched_market_events = google_pubsub_topic.pipeline["enriched-market-events"].id
        trigger_events         = google_pubsub_topic.pipeline["trigger-events"].id
        alert_decisions        = google_pubsub_topic.pipeline["alert-decisions"].id
        raw_market_events_dlq      = google_pubsub_topic.dlq["raw-market-events-dlq"].id
        enriched_market_events_dlq = google_pubsub_topic.dlq["enriched-market-events-dlq"].id
      }
      subscriptions = {
        market_event_processor = google_pubsub_subscription.market_event_processor.name
        rule_engine            = google_pubsub_subscription.rule_engine.name
        agentic_ai             = google_pubsub_subscription.agentic_ai.name
        notification           = google_pubsub_subscription.notification.name
        raw_dlq_monitor        = google_pubsub_subscription.raw_dlq_monitor.name
        enriched_dlq_monitor   = google_pubsub_subscription.enriched_dlq_monitor.name
      }
      subscription_paths = {
        market_event_processor = google_pubsub_subscription.market_event_processor.id
        rule_engine            = google_pubsub_subscription.rule_engine.id
        agentic_ai             = google_pubsub_subscription.agentic_ai.id
        notification           = google_pubsub_subscription.notification.id
        raw_dlq_monitor        = google_pubsub_subscription.raw_dlq_monitor.id
        enriched_dlq_monitor   = google_pubsub_subscription.enriched_dlq_monitor.id
      }
    }
    firestore = {
      database_id = google_firestore_database.main.name
      collections = ["rule_configs", "notification_configs", "agent_state"]
    }
    redis = {
      instance_id = google_redis_instance.main.id
      host        = google_redis_instance.main.host
      port        = google_redis_instance.main.port
      connection_string = "${google_redis_instance.main.host}:${google_redis_instance.main.port}"
    }
    bigquery = {
      dataset_id = google_bigquery_dataset.stock_picker.dataset_id
      table_id   = google_bigquery_table.notification_audit.table_id
      table_ref  = "${var.project_id}.${google_bigquery_dataset.stock_picker.dataset_id}.${google_bigquery_table.notification_audit.table_id}"
    }
  }
}

resource "google_secret_manager_secret" "streaming_pipeline_config" {
  secret_id = "${local.name_prefix}-streaming-pipeline-config"
  labels    = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "streaming_pipeline_config" {
  secret      = google_secret_manager_secret.streaming_pipeline_config.id
  secret_data = jsonencode(local.streaming_config)
}

resource "google_secret_manager_secret" "redis_connection" {
  secret_id = "${local.name_prefix}-redis-connection"
  labels    = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "redis_connection" {
  secret = google_secret_manager_secret.redis_connection.id
  secret_data = jsonencode({
    host              = google_redis_instance.main.host
    port              = google_redis_instance.main.port
    connection_string = "${google_redis_instance.main.host}:${google_redis_instance.main.port}"
  })
}
