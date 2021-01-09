resource "google_cloud_scheduler_job" "pull-thermostat-metric" {
  name             = "pull-thermostat-metric"
  description      = "Pull metrics received from IoT devices"
  schedule         = "*/4 * * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "320s"
  project = local.project_id

  retry_config {
    retry_count = 5
    min_backoff_duration = "30s"
    #max_retry_duration = "180s"
  }

  http_target {
    http_method = "POST"
    uri         = "https://thermostat-agent-ppb6otnevq-uk.a.run.app/aggregation/pull-thermostat-metric/"

    oidc_token {
      service_account_email = google_service_account.thermostat-agent.email
      audience = "https://thermostat-agent-ppb6otnevq-uk.a.run.app/aggregation/pull-thermostat-metric/"
    }
  }

  depends_on = [google_cloud_run_service.default]
}

resource "google_cloud_scheduler_job" "job" {
  name             = "thermostat-next-action"
  description      = "Determine next action and push it to thermostat"
  schedule         = "5,20,35,50 * * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "320s"
  project = local.project_id

  retry_config {
    retry_count = 2
    min_backoff_duration = "60s"
    max_retry_duration = "40s"
  }

  http_target {
    http_method = "GET"
    uri         = "https://thermostat-agent-ppb6otnevq-uk.a.run.app/next-action"

    oidc_token {
      service_account_email = google_service_account.thermostat-agent.email
      audience = "https://thermostat-agent-ppb6otnevq-uk.a.run.app/next-action"
    }
  }
}