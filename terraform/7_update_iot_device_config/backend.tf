terraform {
    backend "gcs" {
        bucket = "tfstate-thermostat-agent"
        prefix = "env/prod"
    }
}