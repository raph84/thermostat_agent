#
# Required environment variables : 
#   - GOOGLE_APPPLICATION_CREDENTIALS
#
#

locals {
  project_id = "thermostat-292016"
  project_iot = "raph-iot"
}


terraform {
  required_providers {
    google = {
      # using beta for Cloud Build GitHub
      source  = "hashicorp/google-beta"
      version = "3.46.0"
    }
    docker = {
      source = "kreuzwerker/docker"
    }
  }
}

provider "google" {
  region  = "us-east4"
  project = local.project_id
}

resource "google_storage_bucket" "tfstate-thermostat-agent" {
  name     = "tfstate-thermostat-agent"
  location = "US-EAST4"

  uniform_bucket_level_access = true

  storage_class = "REGIONAL"

  versioning {
    enabled = true
  }

  labels = {
    project = "thermostat"
  }
}

data "google_client_config" "default" {}

output "test" {
  value = data.google_client_config.default.access_token
}



resource "google_service_account" "thermostat-agent" {
  account_id = "thermostat-agent"
}
resource "google_service_account" "api-call" {
  account_id = "api-call"
}

resource "google_project_service" "enable_cloud_resource_manager_api" {
  service = "cloudresourcemanager.googleapis.com"
}

resource "google_project_service" "run" {
  service = "run.googleapis.com"
}

provider "docker" {
  registry_auth {
    address  = "gcr.io"
    username = "oauth2accesstoken"
    password = data.google_client_config.default.access_token
  }
  #host = "npipe:////.//pipe//docker_engine"
}

data "docker_registry_image" "thermostat-agent" {
  name = "gcr.io/${local.project_id}/thermostat-agent"
}

data "google_container_registry_image" "thermostat-agent-latest" {
  name    = "thermostat-agent"
  project = local.project_id
  digest  = data.docker_registry_image.thermostat-agent.sha256_digest
}

output "image_url" {
  value = data.google_container_registry_image.thermostat-agent-latest.image_url
}

resource "google_cloud_run_service" "default" {
  location = "us-east4"
  name     = "thermostat-agent"
  project  = "thermostat-292016"
  template {
    spec {
      container_concurrency = 1
      service_account_name  = "thermostat-agent@thermostat-292016.iam.gserviceaccount.com"
      timeout_seconds       = 280

      containers {
        args    = []
        command = []
        image   = data.google_container_registry_image.thermostat-agent-latest.image_url

        env {
          name  = "PROJECT_ID"
          value = "thermostat-292016"
        }

        env {
          name  = "LEVEL"
          value = "info"
        }

        env {
          name  = "ACTION_THRESHOLD"
          value = "1.0"
        }

        ports {
          container_port = 8080
        }

        resources {
          limits = {
            "cpu"    = "2000m"
            "memory" = "612Mi"
          }
          requests = {}
        }
      }
    }
  }
}

output "url" {
  value = google_cloud_run_service.default.status[0].url
}

resource "google_cloud_run_service_iam_member" "member" {
  project  = local.project_id
  service  = "climacell-agent"
  role     = "roles/run.invoker"
  location = "us-east4"
  member   = join(":", ["serviceAccount", google_service_account.thermostat-agent.email])

}
resource "google_cloud_run_service_iam_member" "iam_thermostat-iot" {
  project  = local.project_id
  service  = "thermostat-agent"
  role     = "roles/run.invoker"
  location = "us-east4"
  member   = "serviceAccount:thermostat-iot@raph-iot.iam.gserviceaccount.com"
}
resource "google_cloud_run_service_iam_member" "thermostat-agent-id" {
  project  = local.project_id
  service  = "thermostat-agent"
  role     = "roles/run.invoker"
  location = "us-east4"
  member   = join(":", ["serviceAccount", google_service_account.thermostat-agent.email])
  ## Identity used by Cloud Scheduler to invoke next_action
}
resource "google_cloud_run_service_iam_member" "iam-api-call" {
  project  = local.project_id
  service  = "thermostat-agent"
  role     = "roles/run.invoker"
  location = "us-east4"
  member   = join(":", ["serviceAccount", google_service_account.api-call.email])
}
resource "google_cloud_run_service_iam_member" "api-call-climacell" {
  project  = local.project_id
  service  = "climacell-agent"
  role     = "roles/run.invoker"
  location = "us-east4"
  member   = join(":", ["serviceAccount", google_service_account.api-call.email])
}



resource "google_project_iam_member" "cloud-debuger" {
  project = local.project_id
  role    = "roles/clouddebugger.agent"
  member  = join(":", ["serviceAccount", google_service_account.thermostat-agent.email])
}
resource "google_project_iam_binding" "cloud-logger" {
  project = local.project_id
  role    = "roles/logging.logWriter"
  members = [
    join(":", ["serviceAccount", google_service_account.thermostat-agent.email]),
  ]
}

# resource "google_project_iam_member" "thermostat-agent-iot-controller" {
#   project = local.project_iot
#   role    = "roles/cloudiot.deviceController"
#   member  = join(":", ["serviceAccount", google_service_account.thermostat-agent.email])
# }

resource "google_storage_bucket" "thermostat_metric_data" {
  labels = {
    "project" = "thermostat"
  }
  location                    = "US-EAST4"
  name                        = "thermostat_metric_data"
  project                     = "us-east4"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_iam_binding" "thermostat_metric_data-ObjectCreator" {
  bucket = google_storage_bucket.thermostat_metric_data.name
  role   = "roles/storage.objectCreator"
  members = [
    join(":", ["serviceAccount", google_service_account.thermostat-agent.email])
  ]
}

resource "google_storage_bucket_iam_binding" "thermostat_metric_data-ObjectViewer" {
  bucket = google_storage_bucket.thermostat_metric_data.name
  role   = "roles/storage.objectViewer"
  members = [
    join(":", ["serviceAccount", google_service_account.thermostat-agent.email])
  ]
}

resource "google_storage_bucket_iam_binding" "thermostat_metric_data-ObjectAdmin" {
  bucket = google_storage_bucket.thermostat_metric_data.name
  role   = "roles/storage.objectAdmin"
  members = [
    join(":", ["serviceAccount", google_service_account.thermostat-agent.email])
  ]
}



resource "google_service_account" "thermostat-bigquery" {
  account_id = "thermostat-bigquery"
}

data "google_cloudfunctions_function" "data-accumulation-import" {
  project = local.project_id
  region = "us-east4"
  name = "accumulation_import"
}

output "accumulation_import" {
  value = data.google_cloudfunctions_function.data-accumulation-import.name
}

resource "google_cloudfunctions_function_iam_binding" "accumulation-import" {
  project  = local.project_id
  region = "us-east4"
  cloud_function = data.google_cloudfunctions_function.data-accumulation-import.name
  role     = "roles/cloudfunctions.invoker"
  members   = [join(":", ["serviceAccount", google_service_account.thermostat-bigquery.email])]
}


resource "google_cloud_run_service_iam_member" "thermostat-bigquery-id" {
  project  = local.project_id
  service  = "thermostat-agent"
  role     = "roles/run.invoker"
  location = "us-east4"
  member   = join(":", ["serviceAccount", google_service_account.thermostat-bigquery.email])
}

resource "google_bigquery_dataset" "dataset-thermostat" {
  dataset_id                  = "thermostat"
  friendly_name               = "thermostat"
  description                 = "Thermostat"
  location                    = "us-east4"
  #default_table_expiration_ms = 3600000
  project                     = local.project_id

  labels = {
    project = "thermostat"
  }

  
}

resource "google_bigquery_dataset_iam_binding" "dataEditor" {
  dataset_id = google_bigquery_dataset.dataset-thermostat.dataset_id
  role       = "roles/bigquery.dataEditor"

  members = [
    join(":", ["serviceAccount", google_service_account.thermostat-bigquery.email]),
  ]
}

resource "google_project_iam_member" "jobUser" {
  project = local.project_id
  role    = "roles/bigquery.jobUser"
  member  = join(":", ["serviceAccount", google_service_account.thermostat-bigquery.email])
}

# resource "google_bigquery_table" "thermostat_metric" {
#   dataset_id = google_bigquery_dataset.dataset-thermostat.dataset_id
#   table_id   = "thermostat_metric"

#   time_partitioning {
#     type = "DAY"
#   }

#   labels = {
#     project = "thermostat"
#   }

#   schema = <<EOF
# [
#   {
#     "name": "location",
#     "type": "String",
#     "mode": "REQUIRED",
#     "description": "IoT Device location"
#   },
#   {
#     "name": "temperature",
#     "type": "NUMERIC",
#     "mode": "NULLABLE",
#     "description": "Temperature from sensor"
#   },
#   {
#     "name": "humidity",
#     "type": "NUMERIC",
#     "mode": "NULLABLE",
#     "description": "Humidity from sensor"
#   },
#   {
#     "name": "stove_exhaust_temp",
#     "type": "NUMERIC",
#     "mode": "NULLABLE",
#     "description": "Stove exhaust temp from thermocouple"
#   },
#   {
#     "name": "motion",
#     "type": "INT64",
#     "mode": "NULLABLE",
#     "description": "Motion detection from sensor"
#   }
# ]
# EOF

# }

resource "google_cloud_scheduler_job" "bigquery" {
  name             = "thermostat-bigquery"
  description      = "Determine next action and push it to thermostat"
  schedule         = "*/32 * * * *"
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
    uri         = "https://us-east4-thermostat-292016.cloudfunctions.net/accumulation_import"

    oidc_token {
      service_account_email = google_service_account.thermostat-bigquery.email
      audience = "https://us-east4-thermostat-292016.cloudfunctions.net/accumulation_import"
    }
  }
}

resource "google_cloud_scheduler_job" "job" {
  name             = "thermostat-next-action"
  description      = "Determine next action and push it to thermostat"
  schedule         = "*/15 * * * *"
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

data "google_pubsub_topic" "environment-sensor-topic" {
  name = "environment-sensor"
  project = "raph-iot"
}

resource "google_pubsub_subscription" "environment-sensor-sub" {
    ack_deadline_seconds       = 20
    enable_message_ordering    = true
    filter                     = "attributes.deviceId=\"environment-sensor\""
    labels                     = {
        "project" = "thermostat"
    }
    message_retention_duration = "259200s"
    name                       = "SUBSCRIPTION_THERMOSTAT_ENVIRONMENT_SENSOR"
    project                    = "raph-iot"
    retain_acked_messages      = false
    topic                      = "projects/raph-iot/topics/environment-sensor"

    expiration_policy {
        ttl = "2678400s"
    }

    push_config {
        attributes    = {}
        push_endpoint = "https://thermostat-agent-ppb6otnevq-uk.a.run.app/metric/environment-sensor/"

        oidc_token {
            audience              = "https://thermostat-agent-ppb6otnevq-uk.a.run.app/metric/environment-sensor/"
            service_account_email = "thermostat-iot@raph-iot.iam.gserviceaccount.com"
        }
    }

    retry_policy {
        maximum_backoff = "600s"
        minimum_backoff = "30s"
    }

    timeouts {}
}

