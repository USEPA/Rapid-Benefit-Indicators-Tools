"""
# Name: Tier 1 Rapid Benefit Indicator Assessment - Benefit Reliability
# Purpose: Calculate reliabilty of site benefit product into the future
# Author: Justin Bousquin
#
# Version Notes:
# Developed in ArcGIS 10.3
# Date: 3/1/2017
#0.1.0 converted from .pyt
"""
###########IMPORTS###########
import os, sys, time
import arcpy
import decimal, itertools
from arcpy import da, env
from decimal import *

arcpy.env.parallelProcessingFactor = "100%" #use all available resources

##########USER INPUTS##########
conserved = ""#conservation Feature dataset
rel_field = ""#field in feature dataset e.g. "Landuse"
cons_fieldLst = ""#list of values from field to consider conservation e.g. ["Conserved", "Protected"]
threat_fieldLst = ""#DETERMINE FROM cons_fieldLst?
rel_buff_dist = ""#Buffer Distance e.g. "1 Miles"
outTbl = ""#output file
###############################
###########FUNCTIONS###########
"""Global Timer
Purpose: returns the message and calc time since the last time the function was used."""
#Function Notes: used during testing to compare efficiency of each step
def exec_time(start, message):
    end = time.clock()
    comp_time = time.strftime("%H:%M:%S", time.gmtime(end-start))
    print("Run time for " + message + ": " + str(comp_time))
    start = time.clock()
    return start

"""Check Spatial Reference
Purpose: checks that a second spatial reference matches the first and re-projects if not."""
#Function Notes: Either the original FC or the re-projected one is returned
def checkSpatialReference(alphaFC, otherFC):
    alphaSR = arcpy.Describe(alphaFC).spatialReference
    otherSR = arcpy.Describe(otherFC).spatialReference
    if alphaSR.name != otherSR.name:
        #e.g. .name = u'WGS_1984_UTM_Zone_19N' for Projected Coordinate System = WGS_1984_UTM_Zone_19N
        print("Spatial reference for " + otherFC + " does not match.")
        try:
            path = os.path.dirname(alphaFC)
            ext = arcpy.Describe(alphaFC).extension
            newName = os.path.basename(otherFC)
            output = path + os.sep + os.path.splitext(newName)[0] + "_prj" + ext
            arcpy.Project_management(otherFC, output, alphaSR)
            fc = output
            print("File was re-projected and saved as " + fc)
        except:
            print("Warning: spatial reference could not be updated.")
            fc = otherFC
    else:
        fc = otherFC
    return fc

"""Selection Query String from list
Purpose: return a string for a where clause from a list of field values
"""
def selectStr_by_list(field, lst):
    exp = ''
    for item in lst:
        if type(item)==str or type(item)==unicode:
            exp += '"' + field + '" = ' + "'" + str(item) + "' OR "
        else: #float or int or long or ?complex
            exp += '"' + field + '" = ' + str(item) + " OR " #numeric
    return (exp[:-4])

"""Percent Cover
Purpose:"""
#Function Notes:
def percent_cover(poly, bufPoly):
    arcpy.MakeFeatureLayer_management(poly, "polyLyr")
    lst=[]
    orderLst=[]
    #add handle for when no overlap?
    with arcpy.da.SearchCursor(bufPoly, ["SHAPE@", "ORIG_FID"]) as cursor:
        for row in cursor:
            totalArea = Decimal(row[0].getArea("PLANAR", "SQUAREMETERS"))
            arcpy.SelectLayerByLocation_management("polyLyr", "INTERSECT", row[0])
            lyrLst = []
            with arcpy.da.SearchCursor("polyLyr", ["SHAPE@"]) as cursor2:
                for row2 in cursor2:
                    interPoly = row2[0].intersect(row[0], 4) #dimension = 4 for polygon
                    interArea = Decimal(interPoly.getArea("PLANAR", "SQUAREMETERS"))
                    lyrLst.append((interArea/totalArea)*100)
            lst.append(sum(lyrLst))
            orderLst.append(row[1])
    #arcpy.Delete_management(polyD)
    #fix above cleanup
    orderLst, lst = (list(x) for x in zip(*sorted(zip(orderLst, lst)))) #sort by ORIG_FID
    return lst

"""Lists to ADD Field
Purpose: """
#Function Notes: table, list of new fields, list of listes of field values, list of field datatypes
def lst_to_AddField_lst(table, field_lst, list_lst, type_lst):
    if len(field_lst) != len(field_lst) or len(field_lst) != len(type_lst):
        print("ERROR: lists aren't the same length!")
    #"" defaults to "DOUBLE"
    type_lst = ["Double" if x == "" else x for x in type_lst]

    i = 0
    for field in field_lst:
        #add fields
        arcpy.AddField_management(table, field, type_lst[i])
        #add values
        lst_to_field(table, field, list_lst[i])
        i +=1

"""Add List to Field
Purpose: """
#Function Notes: 1 field at a time
#Example: lst_to_field(featureClass, "fieldName", lst)
def lst_to_field(table, field, lst): #handle empty list
    if len(lst) ==0:
        print("No values to add to '{}'.".format(field))
    else:
        i=0
        with arcpy.da.UpdateCursor(table, [field]) as cursor:
            for row in cursor:
                row[0] = lst[i]
                i+=1
                cursor.updateRow(row)
                
#########RELIABILITY##########
def reliability_MODULE(PARAMS):
    print("Reliability of Benefits analysis...")

    cons_poly = PARAMS[0]
    field = PARAMS[1]
    consLst, threatLst = PARAMS[2], PARAMS[3]
    bufferDist = PARAMS[4]
    outTbl = PARAMS[5]

    path = os.path.dirname(outTbl) + os.sep
    ext = arcpy.Describe(outTbl).extension
    
    #set variables
    buf = path + "conservation" + ext

    #remove None from lists #WHY WAS THIS A CONCERN?
    consLst = [x for x in consLst if x is not None]
    threatLst = [x for x in threatLst if x is not None]

    cons_poly = checkSpatialReference(outTbl, cons_poly)

    #buffer site by user specified distance
    arcpy.Buffer_analysis(outTbl, buf, bufferDist)
    
    #make selection from FC based on fields to include
    arcpy.MakeFeatureLayer_management(cons_poly, "consLyr")
    whereClause = selectStr_by_list(field, consLst)
    arcpy.SelectLayerByAttribute_management("consLyr", "NEW_SELECTION", whereClause)

    #determine percent of buffer which is each conservation type
    pct_consLst = percent_cover("consLyr", buf)

    #make list based on threat use types
    whereClause = selectStr_by_list(field, threatLst)
    arcpy.SelectLayerByAttribute_management("consLyr", "NEW_SELECTION", whereClause)
    pct_threatLst = percent_cover("consLyr", buf)
    #start=exec_time(start, "Percent conserved/threatened use types calculated")

    #move results to outTbl
    fields_lst = ["Conserved", "Threatene"]
    list_lst = [pct_consLst, pct_threatLst]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, ["", ""])

    print("Reliability assessment complete")

##############################
###########EXECUTE############
try:
    start = time.clock()
    reliability_MODULE([conserved, rel_field, cons_fieldLst, threat_fieldLst, rel_buff_dist, outTbl])
    start = exec_time(start1, "Reliability assessment")
except:
    print("Reliability of Benefits not assessed")
    arcpy.GetMessages()
