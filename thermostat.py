import os
from flask import Flask, url_for, request
import json
from google.cloud import pubsub_v1
import time
from datetime import datetime
from google.cloud import secretmanager
from google.cloud import storage
from google.oauth2 import id_token
import google.auth
from google.auth.transport.requests import Request
import base64
import copy
import requests

credentials, project = google.auth.default(scopes=[
    'https://www.googleapis.com/auth/cloud-platform',
    'https://climacell-agent-ppb6otnevq-uk.a.run.app'
])

# Instantiates a client
storage_client = storage.Client()

# The name for the new bucket
bucket_name = "thermostat_metric_data"
bucket = storage_client.bucket(bucket_name)


project_id = os.environ['PROJECT_ID']

app = Flask(__name__)
app.config["DEBUG"] = True


def create_file(payload, filename):
    """Create a file.

  The retry_params specified in the open call will override the default
  retry params for this particular file handle.

  Args:
    filename: filename.
  """
    blob = bucket.blob(filename)

    blob.upload_from_string(data=payload,
                            content_type='text/plain')


def get_metric_from_bucket(last):
    if last != 1:
        last = range(-1,0-int(last)-1,-1)
    else:
        last = range(-1,-2,-1)

    blobs = list(storage_client.list_blobs(bucket_name, prefix='thermostat'))
    last_json = []
    print("Get last {} thermostat metric(s).".format(last))
    print(last)
    for i in last:
        print("Loop {}".format(i))
        j = json.loads(blobs[i].download_as_string())
        j['datetime'] = '-'.join(blobs[i].name.rsplit('-', 2)[1:])
        last_json.append(j)

    return last_json

@app.route('/metric/thermostat/', methods=['GET'])
def get_metric_thermostat():

    last = request.args.get('last', 1)

    last_json = get_metric_from_bucket(last)

    return json.dumps(last_json)


@app.route('/metric/thermostat/', methods=['POST'])
def store_metric_thermostat():
    envelope = request.get_json()
    if not envelope:
        msg = 'no Pub/Sub message received'
        print(f'error: {msg}')
        return f'Bad Request: {msg}', 400

    if not isinstance(envelope, dict) or 'message' not in envelope:
        msg = 'invalid Pub/Sub message format'
        print(f'error: {msg}')
        return f'Bad Request: {msg}', 400

    pubsub_message = envelope['message']

    payload = ''
    if isinstance(pubsub_message, dict) and 'data' in pubsub_message:
        payload = base64.b64decode(pubsub_message['data']).decode('utf-8').strip()

    filename = "thermostat-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    create_file(payload, filename)

    return ('', 204)

def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)


@app.route("/site-map")
def site_map():
    links = []
    for rule in app.url_map.iter_rules():
        # Filter out rules we can't navigate to in a browser
        # and rules that require parameters
        if ("GET" in rule.methods or "POST" in rule.methods) and has_no_empty_params(rule):
            url = url_for(rule.endpoint, **(rule.defaults or {}))
            links.append((url, rule.endpoint))
    # links is now a list of url, endpoint tuples

    return (str(links))


request_headers = {
    "content-type": "application/json"
}
target_audience = 'thermostat-agent-ppb6otnevq-uk.a.run.app'

url_weather = 'https://climacell-agent-ppb6otnevq-uk.a.run.app'

def update_id_connect_token():
    open_id_connect_token = id_token.fetch_id_token(Request(),
                                                            audience=url_weather)
    return open_id_connect_token

def query(url_query):
    resp = requests.request(
        'GET',
        url_query,
        headers={'Authorization': 'Bearer {}'.format(open_id_connect_token)}
    )
    return resp

open_id_connect_token = update_id_connect_token()

resp = requests.request(
    'GET',
    url_weather + '/realtime/',
    headers={'Authorization': 'Bearer {}'.format(open_id_connect_token)}
)
print(resp)

def get_weather_realtime():
    url_query = url_weather + '/realtime/'
    resp = query(url_query)
    return resp

def get_weather_hourly():
    url_query = url_weather + '/hourly/'
    resp = query(url_query)
    return resp

def get_set_point(date):
    if date.hour > 21 or (date.hour < 5 and date.minute > 30):
        return 18
    else:
        return 22

def map_climacell_data(data):
    date = datetime.strptime(data['observation_time']['value'],
                             '%Y-%m-%dT%H:%M:%S.%f%z')
    return {
        "dt": date.strftime("%Y-%m-%d %H:%M:%S"),
        "Indoor Temp. Setpoint": get_set_point(date),
        "Outdoor Temp.": data['temp']['value'],
        "Outdoor RH": data['humidity']['value'],
        "Wind Speed": data['wind_speed']['value'],
        "Wind Direction": data['wind_direction']['value'],
        "Direct Solar Rad.": data['surface_shortwave_radiation']['value']
    }


@app.route("/digest")
def digest():
    open_id_connect_token = id_token.fetch_id_token(Request(),
                                                    audience=url_weather)


    thermostat = get_metric_from_bucket(1)[0]
    hourly = get_weather_hourly().json()
    realtime = get_weather_realtime().json()
    result = {
                "digest": {}
            }
    result["digest"]["current"] = {
            "Htg SP": 0,
            "Indoor Temp. Setpoint": 0,
            "Occupancy Flag": thermostat['motion'],
            "PPD": 0,
            "Coil Power": 0,
            "MA Temp.": 0,
            "Sys Out Temp.": 0,
            "dt": thermostat['datetime'],
            "Outdoor Temp.": realtime['temp']['value'],
            "Outdoor RH": realtime['humidity']['value'],
            "Wind Speed": realtime['wind_speed']['value'],
            "Wind Direction": realtime['wind_direction']['value'],
            "Direct Solar Rad.":
            realtime['surface_shortwave_radiation']['value'],
            "Indoor Temp.": thermostat['temperature']
        }
        
    disturbances = []
    result["digest"]["disturbances"] = disturbances
    for i in range(0, 12):
        h = hourly[i]
        mapping = map_climacell_data(h)
        mapping["Occupancy Flag"] = 0
        disturbances.append(mapping)

    return result["digest"]


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))