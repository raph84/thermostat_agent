from flask import Blueprint
import json
from flask import current_app
import os
import logging

from thermostat_accumulate import get_accumulate

from pythermalcomfort.models import pmv_ppd
from pythermalcomfort.psychrometrics import v_relative
from pythermalcomfort.utilities import met_typical_tasks, clo_typical_ensembles

thermal_comfort = Blueprint('thermal_comfort', __name__)



cloud_logger = logging


@thermal_comfort.route('/ppd/', methods=['GET'])
def retrieve_ppd():

    result = ppd()

    return result


def ppd(tdb=25,
        tr=25,
        rh=50,
        met=1.2,
        clo=0.5,
        wme=0):
    """Calculate PMV and PPD
    Arguments
    tdb : Dry bulb air temp
    tr : mean radiant temp
    vr : relative air velocity
    rh : relative humidity
    met : metabolic rate
    clo : clothing insulation

    Reference values for met : 
    - 'Cooking': 1.8
    - 'Filing, seated': 1.2
    - 'House cleaning': 2.7
    - 'Reading, seated': 1.0
    - 'Reclining': 0.8¸
    - 'Seated, quiet': 1.0
    - 'Sleeping': 0.7
    - 'Typing': 1.1
        from pythermalcomfort.utilities import met_typical_tasks
        print(met_typical_tasks['Filing, standing'])
    """
    met = met_typical_tasks['Seated, quiet']
    clo = clo_typical_ensembles['Sweat pants, long-sleeve sweatshirt']
    v_r = v_relative(v=0.1, met=met)

    results = pmv_ppd(
        tdb=tdb,  #25
        tr=tr,  #25
        vr=v_r,
        rh=rh,  #50
        met=met,
        clo=clo,
        wme=0,
        standard="ISO")

    cloud_logger.debug(results)

    return {"ppd": results['ppd']}
