import json

from flask import Blueprint
from flask import current_app as app
from flask import Flask, url_for, request

from accumulator import Accumulator

thermostat_accumulate = Blueprint('thermostat_accumulate', __name__)


@thermostat_accumulate.route('/accumulate/', methods=['POST'])
def test_accumulate():
    j = request.get_json()
    accumulator = acc(j)

    resp = accumulator.to_dict()
    print(resp)
    return resp


def acc(j):
    accumulator = Accumulator(app.logger)
    n = utcnow()

    if j.get('temperature') is not None:
        j['temperature'] = float(j.get('temperature'))
    if j.get('humidity') is not None:
        j['humidity'] = float(j.get('humidity'))
    if j.get('stove_exhaust_temp') is not None:
        j['stove_exhaust_temp'] = float(j.get('stove_exhaust_temp'))

    try:
        accumulator.add_temperature2(n, value_dict=j)
    except ValueError as ex:
        app.logger.warn(
            "Accumulator - no value to add - content: {} --- {}".format(
                payload, ex))

    return accumulator


@thermostat_accumulate.route('/metric/accumulate/', methods=['POST'])
def accumulate_metric_thermostat():
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
        payload = base64.b64decode(
            pubsub_message['data']).decode('utf-8').strip()
    try:
        j = json.loads(payload)

        acc(json.loads(payload))
    except Exception as ex:
        app.logger.error("Unable to loads payload Json {} : {}".format(
            ex, payload))

    return ('', 204)


@thermostat_accumulate.route('/metric/accumulate/', methods=['GET'])
def get_accumulate_metric_thermostat():

    load = int(request.args.get('load', None))
    records = bool(request.args.get('records', False))

    if load >= 1:
        accumulate = get_accumulate(logger=app.logger, load=load)
    else:
        accumulate = get_accumulate()

    if records:
        resp = accumulate.to_json_records()
    else:
        resp = accumulate.to_dict()

    return (resp, 200)


def get_accumulate(logger, load=2, hold=True):
    accumulator = Accumulator(logger)
    accumulator.load(load, hold=hold)

    return accumulator