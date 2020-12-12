import pandas as pd
from datetime import datetime
from pytz import timezone
import pytz
import iso8601

class Accumulator():

    def __init__(self):

        self.temperature = None
        self.dt = None

    def temp_dict(self, temp=None, humidity=None, motion=None, stove_exhaust_temp=None):
        t = {
            "temperature": temp,
            "humidity": humidity,
            "stove_exhaust_temp": stove_exhaust_temp,
            "motion": motion
        }

        return t

    def add_temperature(self, d, temp=None, humidity=None, motion=None, stove_exhaust_temp=None):
        if self.dt == None:
            dt = d
            replace = (d.minute // 15) * 15
            dt.replace(minute=replace, second=0, microsecond=0)
            self.dt = dt


        t = self.temp_dict(temp, humidity, motion, stove_exhaust_temp)
        df_t = pd.DataFrame(t, index=[d])
        if (self.temperature == None):
            self.temperature = df_t
        else:
            self.temperature.append(df_t)