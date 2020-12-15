from datetime import datetime
from pytz import timezone
import pytz
import iso8601

from utils import utcnow, ceil_dt

from accumulator_entity import Accumulator_Entity

from google.cloud import storage
import pickle



class Accumulator():

    # Instantiates a client
    storage_client = storage.Client()

    # The name for the new bucket
    bucket_name = "thermostat_metric_data"
    bucket = storage_client.bucket(bucket_name)

    PREFIX = "accumulator-"

    def get_filename(self, dt):
        filename = dt.isoformat()
        filename = self.PREFIX + filename
        return filename

    def store_and_release(self):
        if self.blob == None:
            filename = self.get_filename(self.entity.dt)
            self.blob = self.bucket.blob(filename)

        pickle_dump = pickle.dumps(self.entity)
        #try:
        #    self.blob.temporary_hold = False
        #    self.blob.patch()
        #except:
        #    print("There was no hold.")
        self.blob.upload_from_string(data=pickle_dump)

    def release(self):
        self.blob.temporary_hold = False
        self.blob.patch()

    def load_and_hold(self):
        self.load(1)

    def load(self, n=1, hold=False):
        self.entity = None
        blobs = list(
            self.storage_client.list_blobs(self.bucket_name,
                                           prefix=self.PREFIX))

        if n > 0 and len(blobs) >= n:
            rng = range(-1, 0 - int(n) - 1, -1)
            for i in rng:
                if i < -1:
                    self.blob = None
                else:
                    self.blob = blobs[i]

                pickle_load = blobs[i].download_as_string()
                e = pickle.loads(pickle_load)
                if self.entity is None:
                    self.entity = e
                else:
                    if (self.entity.dt < e.dt):
                        self.entity.dt = e.dt
                    self.entity.temperature = self.entity.temperature.append(
                        e.temperature)
        else:
            self.entity = Accumulator_Entity()
            self.entity.dt = ceil_dt(utcnow(), 15)
            filename = self.get_filename(self.entity.dt)

            self.blob = self.bucket.blob(filename)
            pickle_dump = pickle.dumps(self.entity)
            self.blob.upload_from_string(data=pickle_dump)

        #if hold:
        #    self.blob.temporary_hold = True
        #    self.blob.patch()

    def add_temperature(self, d, temp=None, humidity=None, motion=None, stove_exhaust_temp=None):
        self.load_and_hold()
        if self.entity.dt < d:
            self.entity = Accumulator_Entity()
            self.blob = None
        self.entity.add_temperature(d, temp, humidity, motion, stove_exhaust_temp)
        self.store_and_release()
