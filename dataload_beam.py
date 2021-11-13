# %%
import argparse
import logging

import apache_beam as beam
from apache_beam.dataframe.convert import to_dataframe
from apache_beam.dataframe.convert import to_pcollection
from apache_beam.io import ReadFromText
from apache_beam.options.pipeline_options import PipelineOptions


table_schema = {
    'fields': [{
        'name': 'location',
        'type': 'STRING',
        'mode': 'NULLABLE'
    }, {
        'name': 'motion',
        'type': 'BOOL',
        'mode': 'NULLABLE'
    }, {
        'name': 'humidity',
        'type': 'NUMERIC',
        'mode': 'NULLABLE'
    }, {
        'name': 'dt',
        'type': 'TIMESTAMP',
        'mode': 'REQUIRED'
    }, {
        'name': 'ppd',
        'type': 'NUMERIC',
        'mode': 'NULLABLE'
    }, {
        'name': 'indoor_temp_setpoint',
        'type': 'NUMERIC',
        'mode': 'NULLABLE'
    }, {
        'name': 'indoor_temp',
        'type': 'NUMERIC',
        'mode': 'NULLABLE'
    }, {
        'name': 'ma_temp',
        'type': 'NUMERIC',
        'mode': 'NULLABLE'
    }, {
        'name': 'htg_sp',
        'type': 'NUMERIC',
        'mode': 'NULLABLE'
    }, {
        'name': 'filename',
        'type': 'STRING',
        'mode': 'NULLABLE'
    }, {
        'name': 'load_date',
        'type': 'TIMESTAMP',
        'mode': 'NULLABLE'
    }, {
        'name': 'temp_basement',
        'type': 'NUMERIC',
        'mode': 'NULLABLE'
    }, {
        'name': 'sys_out_temp',
        'type': 'NUMERIC',
        'mode': 'NULLABLE'
    }, {
        'name': 'stove_exhaust_temp',
        'type': 'NUMERIC',
        'mode': 'NULLABLE'
    }, {
        'name': 'coil_power',
        'type': 'BIGNUMERIC',
        'mode': 'NULLABLE'
    }]
}


def process_data(data):
    from thermostat_utils.thermostat_aggregation_utils import aggregate_to_dataframe, metric_str_to_json
    from thermostat_utils.yadt import scan_and_apply_tz, utcnow

    dd = []
    load_date = utcnow()

    try:
        #print("DATA: {}".format(data))
        filename = data[0].split("/")[-1]

        #print("file : {} data : {}".format(filename, data[1]))
        last_json = metric_str_to_json(data[1])
        dd.extend(last_json)



        #merge, thermostat_metric_data = aggregate_to_dataframe(
        #    filename, last_json, thermostat_metric_data, load_date)


    except Exception as e:
        logging.error(data)
        logging.error(e)
        raise e

    result = {'load_date': load_date, 'filename': filename, 'data': dd}
    #print(result)

    return result

def data_to_dataframe(elements, fields):
    from thermostat_utils.thermostat_aggregation_utils import aggregate_to_dataframe, metric_str_to_json
    import pandas as pd
    import numpy as np

    #print(elements)
    data = []
    for e in elements:
        data.append(e)

    #print(data)

    merge, thermostat_metric_data = aggregate_to_dataframe(
        data, None)



    thermostat_metric_data.rename(columns={
        'Indoor Temp. Setpoint': 'indoor_temp_setpoint',
        'Indoor Temp.': 'indoor_temp',
        'MA Temp.': 'ma_temp',
        'Htg SP': 'htg_sp',
        'PPD': 'ppd',
        'Sys Out Temp.': 'sys_out_temp',
        'Coil Power': 'coil_power'
    },
                                  inplace=True)

    missing_fields = False
    for f in fields['fields']:
        if f['name'].lower() not in thermostat_metric_data.columns:
            print("MISSING ===> {}".format(f['name'].lower()))
            thermostat_metric_data[f['name'].lower()] = None
            if f['mode'] != 'NULLABLE':
                missing_fields = True

    # thermostat_metric_data = thermostat_metric_data.where(
    #     (pd.notnull(thermostat_metric_data)), None)

    # thermostat_metric_data['dt'] = pd.Series(
    #     thermostat_metric_data['dt'].dt.to_pydatetime(), dtype=object)

    # thermostat_metric_data['load_date'] = pd.Series(
    #     thermostat_metric_data['load_date'].dt.to_pydatetime(), dtype=object)

    print(thermostat_metric_data.columns)
    #print(thermostat_metric_data.dtypes)
    print(thermostat_metric_data)


    #return thermostat_metric_data.to_dict(orient='records')
    if missing_fields:
        return beam.pvalue.TaggedOutput('missing_fields',
                                        [thermostat_metric_data])
    else:
        return [thermostat_metric_data]


def combine_dataframe(df):
    import pandas as pd

    data = pd.concat(df)
    return data


def read_file(f):
    try:
        content = f.read_utf8()
        return (f.metadata.path, content)
    except Exception:
        return beam.pvalue.TaggedOutput('exception', f.metadata.path)


def get_fields():
    fields = []
    for f in table_schema['fields']:
        fields.append(f['name'])

    return fields

def replace_nan(element):
    import numpy as np
    import math

    for k in element.keys():
        try:
            if math.isnan(element[k]):
                print("Replace NaN")
                element[k] = None
        except:
            pass
    return element

def check_type(element, fields):
    pass


def run(argv=None):

    from apache_beam.options import pipeline_options
    from apache_beam.options.pipeline_options import GoogleCloudOptions, PipelineOptions, StandardOptions, SetupOptions, WorkerOptions
    from google.cloud import storage
    from apache_beam.io.gcp.internal.clients import bigquery
    import json

    if argv is None:
        argv = [
            "--flexrs_goal", "SPEED_OPTIMIZED", '--direct_num_workers', '1',
            '--service_account_email',
            'thermostat-bigquery@thermostat-292016.iam.gserviceaccount.com'
        ]

    """Main entry point; """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--input',
        dest='input',
        default='gs://thermostat_metric_data/**/*-202*',
        help='Input file to process.')
    known_args, pipeline_args = parser.parse_known_args(argv)

    options = pipeline_options.PipelineOptions(pipeline_args)
    options.view_as(StandardOptions).runner = 'DataflowRunner'
    #options.view_as(StandardOptions).runner = 'DirectRunner'
    #options.view_as(WorkerOptions).network = 'asdf'
    #options.view_as(WorkerOptions).use_public_ips = False
    options.view_as(WorkerOptions).disk_size_gb = 25
    options.view_as(SetupOptions).setup_file = './setup.py'
    #options.view_as(SetupOptions).requirements_file = './requirements.txt'
    options.view_as(SetupOptions).save_main_session = True
    options.view_as(WorkerOptions).max_num_workers = 20
    options.view_as(WorkerOptions).machine_type = 'e2-standard-2'

    google_cloud_options = options.view_as(GoogleCloudOptions)
    google_cloud_options.project = 'thermostat-292016'
    google_cloud_options.job_name = 'thermostat-metrics2'
    google_cloud_options.staging_location = 'gs://dataflow-workdir/staging'
    google_cloud_options.temp_location = 'gs://dataflow-workdir/temp'
    google_cloud_options.region = 'us-east4'

    # Import this here to avoid pickling the main session.
    import re

    from apache_beam.io.gcp.gcsfilesystem import GCSFileSystem
    from operator import add
    from functools import reduce
    import pandas as pd

    print(options)





    p = beam.Pipeline(options=options)

    # gcs = GCSFileSystem(PipelineOptions(options=options))
    # result = [m.metadata_list for m in gcs.match([known_args.input])]
    # result = reduce(add, result)

    # storage_client = storage.Client()
    # bucket = storage_client.bucket("thermostat_metric_data")
    # blobs = bucket.list_blobs()
    # json_paths = []
    # for blob in blobs:
    #     #json_paths.append(f"gs://{bucket_name}/{blob.name}")
    #     json_paths.append(f"{blob.name}")

    # print(json_paths)
    # return json_paths

    # readable_files = (p
    #                   | beam.io.fileio.MatchFiles(known_args.input)
    #                   | beam.io.fileio.ReadMatches()
    #                   | beam.Reshuffle()
    #                   | beam.Map(lambda x: (x.metadata.path, beam.io.ReadFromText(x.metadata.path)))
    #                   | beam.Map(print)
    #                  )
    #| "List files" >> beam.Map(lambda a: (a.metadata.path)))

    readable_files = (p
                      | beam.io.fileio.MatchFiles(known_args.input)
                      | beam.io.fileio.ReadMatches()
                      | beam.Reshuffle()
                      | beam.Map(read_file).with_outputs()
                      )


    read = (
        readable_files[None]
        #reading | 'Flatten PCollections' >> beam.Flatten()
        #merged = reading | 'Flatten PCollections' >> beam.Flatten() | beam.Map(print)
        | beam.Map(process_data)
        | beam.combiners.ToList()
        | beam.FlatMap(data_to_dataframe, table_schema).with_outputs()
    )


    readable_files.exception | beam.io.WriteToText(
        'gs://thermostat_metric_data/exception', num_shards=1)



    table_spec = bigquery.TableReference(projectId='thermostat-292016',
                                         datasetId='thermostat',
                                         tableId='data')

    read.missing_fields | beam.Map(lambda a: a.to_pickle(
         'gs://thermostat_metric_data/missing_fields.p'))

    (read[None]
     | beam.Map(lambda a: a.to_dict(orient='records'))
     #| beam.Map(lambda a: json.loads(a.to_json(orient='records')))
     | beam.FlatMap(lambda a: a)
     | beam.Map(lambda a: replace_nan(a))
     | beam.io.WriteToBigQuery(
         table_spec,
         schema=table_schema,
         write_disposition=beam.io.BigQueryDisposition.WRITE_TRUNCATE,
         create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
         additional_bq_parameters={
             'timePartitioning': {
                 'type': 'DAY',
                 'field': 'dt'
             }
         }))

    (read
     | beam.Map(lambda a: a.to_pickle(
         'gs://thermostat_metric_data/thermostat_metric_data.p',
         compression=None,
         protocol=5,
         storage_options=None)))

    r = p.run()
    #r.wait_until_finish()

    return read
    # reading = []
    # for r in result:
    #     reading.append((p
    #                    | "Read {}".format(r.path) >> beam.io.ReadFromText(
    #                        str(r.path), strip_trailing_newlines=True)
    #                    | "Map {}".format(r.path) >> beam.Map(lambda a:
    #                                                          (str(r.path), a))))


    print("Reading len {}".format(len(reading)))

    df = pd.DataFrame()
    # flatten all PCollections into a single one
    merged = (
        reading | 'Flatten PCollections' >> beam.Flatten()
        #merged = reading | 'Flatten PCollections' >> beam.Flatten() | beam.Map(print)
        | beam.Map(process_data)
        | beam.combiners.ToList()
        | beam.Map(data_to_dataframe)
        | beam.Map(print))
    r = p.run()
    r.wait_until_finish()



# %%
if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    run()

# %%
