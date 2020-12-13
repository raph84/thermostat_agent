import pandas as pd
from utils import utcnow, ceil_dt


class Accumulator_Entity():

    def __init__(self):
        self.temperature = None
        self.dt = None

    def temp_dict(self,
                  temp=None,
                  humidity=None,
                  motion=None,
                  stove_exhaust_temp=None):
        t = {
            "temperature": temp,
            "humidity": humidity,
            "stove_exhaust_temp": stove_exhaust_temp,
            "motion": motion
        }

        return t

    def add_temperature(self, d, temp=None, humidity=None, motion=None, stove_exhaust_temp=None):

        t = self.temp_dict(temp, humidity, motion, stove_exhaust_temp)
        df_t = pd.DataFrame(t, index=[d])

        if self.temperature is not None:
            self.temperature = self.temperature.append(df_t)
        else:
            self.dt = ceil_dt(d, 15)
            self.temperature = df_t

        print(len(self.temperature))