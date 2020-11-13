#
# Required environment variables : 
#   - GOOGLE_APPPLICATION_CREDENTIALS
#
#

locals {
  # Ids for multiple sets of EC2 instances, merged together
  project_id = "thermostat-292016"
}


terraform {
  required_providers {
    google = {
      # using beta for Cloud Build GitHub
      source = "hashicorp/google-beta"
      version = "3.46.0"
    }
  }
}

provider "google" {
  region  = "us-east4"
  project = local.project_id
}

resource "google_storage_bucket" "tfstate-thermostat-agent" {
  name          = "tfstate-thermostat-agent"
  location      = "US-EAST4"

  uniform_bucket_level_access = true

  storage_class = "REGIONAL"

  versioning {
      enabled = true
  }

  labels = {
      project = "thermostat"
  }
}

resource "google_service_account" "thermostat-agent" {
  account_id   = "thermostat-agent"
}

resource "google_cloud_run_service" "default" {
  location                   = "us-east4"
  name                       = "thermostat-agent"
  project                    = "thermostat-292016"
  template {
        spec {
            container_concurrency = 1
            service_account_name  = "thermostat-agent@thermostat-292016.iam.gserviceaccount.com"
            timeout_seconds       = 30

            containers {
                args    = []
                command = []
                image   = "us.gcr.io/thermostat-292016/thermostat-agent:fd3575916a1806bcdc98bf19f0894f2cf6516d64"

                env {
                    name  = "PROJECT_ID"
                    value = "thermostat-292016"
                }

                ports {
                    container_port = 8080
                }

                resources {
                    limits   = {
                        "cpu"    = "1000m"
                        "memory" = "256Mi"
                    }
                    requests = {}
                }
            }
        }
  }
}

resource "google_cloud_run_service_iam_member" "member" {
  project = local.project_id
  service = "climacell-agent"
  role = "roles/run.invoker"
  location = "us-east4"
  member = join(":", ["serviceAccount", google_service_account.thermostat-agent.email])
  
}

resource "google_storage_bucket" "thermostat_metric_data" {
  labels                      = {
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
  role = "roles/storage.objectCreator"
  members = [
    join(":", ["serviceAccount", google_service_account.thermostat-agent.email])
  ]
}

resource "google_storage_bucket_iam_binding" "thermostat_metric_data-ObjectViewer" {
  bucket = google_storage_bucket.thermostat_metric_data.name
  role = "roles/storage.objectViewer"
  members = [
    join(":", ["serviceAccount", google_service_account.thermostat-agent.email])
  ]
}