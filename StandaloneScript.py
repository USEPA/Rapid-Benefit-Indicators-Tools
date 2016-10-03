"""
# Name: Tier 1 Rapid Benefit Indicator Assessment
# Purpose: Calculate values for benefit indicators using wetland restoration site polygons
#          and a variety of other input data
# Author: Justin Bousquin
#
# Version Notes:
# Developed in ArcGIS 10.3
# v26 implemented setParam to streamline arcpy.Parameter
# Date: 8/18/2016
"""

import sys, os
from decimal import *
import arcpy
from arcpy import env
from arcpy import da

arcpy.env.parallelProcessingFactor = "100%" #won't matter in most cases

###########FUNCTIONS###########
"""Set Input Parameter
Purpose: returns arcpy.Parameter for provided string, setting defaults for missing."""
def setParam(str1, str2, str3, str4, str5):
    lst = [str1, str2, str3, str4, str5]
    defLst = ["Input", "name", "GpFeatureLayer", "Required", "Input"]
    i = 0
    for str_ in lst:
        if str_ =="":
            lst[i]=defLst[i]
        i+=1       
    return arcpy.Parameter(
        displayName = lst[0],
        name = lst[1],
        datatype = lst[2],
        parameterType = lst[3],
        direction = lst[4])

"""Global Timer
Purpose: returns the message and calc time since the last time the function was used."""
#Function Notes: used during testing to compare efficiency of each step
def exec_time(start, message):
    end = time.clock()
    comp_time = end - start
    arcpy.AddMessage("Run time for " + message + ": " + str(comp_time))
    start = time.clock()
    return start
