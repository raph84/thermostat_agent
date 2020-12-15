from datetime import datetime
from pytz import timezone
import pytz
import iso8601

from utils import utcnow, ceil_dt

from accumulator_entity import Accumulator_Entity

from google.cloud import storage
import pickle



class Accumulator():


    PREFIX = "accumulator-"
    bucket_name = "thermostat_metric_data"

    class A:
        def __init__(self, entity, blob):
            self.entity = entity
            self.blob = blob

    def __init__(self):
        self.entities = []
        # Instantiates a client
        self.storage_client = storage.Client()
        # The name for the new bucket
        self.bucket = self.storage_client.bucket(self.bucket_name)

    def get_filename(self, dt):
        filename = dt.isoformat()
        filename = self.PREFIX + filename
        return filename

    def store_and_release(self):
        pickle_dump = pickle.dumps(self.entities[0].entity)
        #try:
        #    self.blob.temporary_hold = False
        #    self.blob.patch()
        #except:
        #    print("There was no hold.")
        blob = self.bucket.get_blob(self.entities[0].blob.name)
        blob.upload_from_string(data=pickle_dump)

    def release(self):
        self.blob.temporary_hold = False
        self.blob.patch()

    def load_and_hold(self):
        self.load(1)

    def load(self, n=1, hold=False):
        self.entities = []
        blobs = list(
            self.storage_client.list_blobs(self.bucket_name,
                                           prefix=self.PREFIX))

        if len(blobs) >= n:
            rng = range(-1, 0 - int(n) - 1, -1)
            for i in rng:
                b = self.bucket.get_blob(blobs[i].name)
                if (b.temporary_hold):
                    now = utcnow()
                    while b.temporary_hold:
                        elapse = utcnow() - now
                        if elapse.seconds >= 10:
                            b.temporary_hold = False
                            b.patch()
                        b = self.bucket.get_blob(blobs[i].name)


                pickle_load = blobs[i].download_as_bytes()
                e = pickle.loads(pickle_load)
                a = Accumulator.A(e, blobs[i])
                self.entities.append(a)
        else:
            entity = Accumulator_Entity()
            entity.dt = ceil_dt(utcnow(), 15)

            filename = self.get_filename(entity.dt)

            blob = self.bucket.blob(filename)
            pickle_dump = pickle.dumps(entity)
            blob.upload_from_string(data=pickle_dump)

            a = Accumulator.A(entity, blob)
            self.entities = self.entities.append(a)

        #if hold:
        #    self.blob.temporary_hold = True
        #    self.blob.patch()

    def add_temperature(self, d, temp=None, humidity=None, motion=None, stove_exhaust_temp=None):
        self.load_and_hold()

        self.entities[0].entity.add_temperature(d, temp, humidity, motion, stove_exhaust_temp)
        self.store_and_release()

    def to_json(self):
        resp = []
        for e in self.entities:
            resp.append(e.entity.to_json())

        return {"metrics":resp}