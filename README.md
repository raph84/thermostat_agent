## GCP resources

### Create service account
```
gcloud iam service-accounts create thermostat-agent

gcloud iam service-accounts create $env:THERMOSTAT_IOT_USERNAME --project=$env:PROJECT_IOT
```

### Deploy on Google Cloud Run
```
gcloud config set run/platform managed
gcloud config set run/region us-east4

gcloud builds submit --tag us.gcr.io/$env:PROJECT_ID/thermostat-agent

gcloud run deploy thermostat-agent --image us.gcr.io/$env:PROJECT_ID/thermostat-agent --no-allow-unauthenticated --platform managed --region us-east4 --set-env-vars "PROJECT_ID=$env:PROJECT_ID" --service-account thermostat-agent@$env:PROJECT_ID.iam.gserviceaccount.com --timeout=30s --max-instances 1 --concurrency 1

# redeploy
gcloud run deploy thermostat-agent --image us.gcr.io/$env:PROJECT_ID/thermostat-agent
```
### Cloud Run invokers
```
gcloud run services add-iam-policy-binding thermostat-agent --member=serviceAccount:$env:THERMOSTAT_IOT_SERVICE_ACCOUNT --role='roles/run.invoker'
```

### Automate deployment to Cloud Run
```
# https://cloud.google.com/cloud-build/docs/deploying-builds/deploy-cloud-run#continuous-iam
gcloud iam service-accounts add-iam-policy-binding $env:THERMOSTAT_AGENT_SERVICE_ACCOUNT --member="$env:CLOUD_BUILD_SVC_ACCOUNT" --role="roles/iam.serviceAccountUser"


gcloud beta builds triggers create github --repo-name=thermostat-agent --repo-owner=raph84 --branch-pattern="master" --build-config=cloudbuild.yaml
```

### Create storage bucket
```
gsutil mb -p $env:PROJECT_ID -c STANDARD -l $env:GCP_LOCATION -b on gs://thermostat_metric_data
gsutil label ch -l project:thermostat gs://thermostat_metric_data
```

### PubSub subscription to store thermostat IoT sensor data
```
gcloud beta pubsub subscriptions create $env:SUBSCRIPTION_THERMOSTAT_IOT --topic $env:TOPIC_THERMOSTAT_IOT --push-endpoint=$env:THERMOSTAT_AGENT_SERVICE_URL --push-auth-service-account=$env:THERMOSTAT_IOT_SERVICE_ACCOUNT --project=$env:PROJECT_IOT

gcloud pubsub subscriptions update $env:SUBSCRIPTION_THERMOSTAT_IOT --project=$env:PROJECT_IOT --update-labels=project=thermostat
```

### PubSub subscriptions to store weather data in storage bucket
```
gcloud beta pubsub subscriptions create $env:SUBSCRIPTION_CLIMACELL_STORE_REALTIME2 --topic $env:TOPIC_ID --push-endpoint=$endpoint --push-auth-service-account=$env:CLIMACELL_AGENT_SERVICE_ACCOUNT --message-filter='attribute.mode:realtime' --enable-message-ordering

gcloud beta pubsub subscriptions create $env:SUBSCRIPTION_CLIMACELL_STORE_HOURLY --topic $env:TOPIC_ID --push-endpoint=$endpoint_hourly --push-auth-service-account=$env:CLIMACELL_AGENT_SERVICE_ACCOUNT --message-filter='attributes.mode = \"hourly\"' --enable-message-ordering
```