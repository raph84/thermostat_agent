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
      timeout_seconds       = 30

      containers {
        args    = []
        command = []
        image   = data.google_container_registry_image.thermostat-agent-latest.image_url

        env {
          name  = "PROJECT_ID"
          value = "thermostat-292016"
        }

        ports {
          container_port = 8080
        }

        resources {
          limits = {
            "cpu"    = "1000m"
            "memory" = "256Mi"
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