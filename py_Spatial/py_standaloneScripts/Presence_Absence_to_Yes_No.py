"""
# Name: Tier 1 Rapid Benefit Indicator Assessment - Presence/Absence to Yes/No
# Purpose: Determine is features are within a given range
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
from arcpy import da, env

arcpy.env.parallelProcessingFactor = "100%" #use all available resources

#########USER INPUTS#########
#existing results outTable
outTbl =
#field in outTable to overwrite
field = #e.g. ""
#dataset to test presence/absence against
FC =
#distance within which feature matters
buff_dist = #e.g. "1 Miles"
##########FUNCTIONS##########
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

"""Buffer Contains
Purpose: returns number of points in buffer as list"""
#Function Notes:
#Example: lst = buffer_contains(view_50, addresses)
def buffer_contains(poly, pnts):
    ext = arcpy.Describe(poly).extension
    poly_out = os.path.splitext(poly)[0] + "_2" + ext #hopefully this is created in outTbl
    arcpy.SpatialJoin_analysis(poly, pnts, poly_out, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "INTERSECT", "", "")
    #When a buffer is created for a site it may get a new OBJECT_ID, but the site ID is maintained as ORIG_FID,
    #"OID@" returns the ID generated for poly_out, based on TARGET_FID (OBJECT_ID for buffer). Since results
    #are joined back to the site they must be sorted in that order.
    #check for ORIG_FID
    fields = arcpy.ListFields(poly_out)
    if "ORIG_FID" in fields:
        lst = field_to_lst(poly_out, ["ORIG_FID", "Join_Count"])
    else:
        lst = field_to_lst(poly_out, ["Join_Count"])
    arcpy.Delete_management(poly_out)
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
        
#############################
def absTest_MODULE(PARAMS):

    outTbl, field = PARAMS[0], PARAMS[1]
    FC = PARAMS[2]
    buff_dist = PARAMS[3]
    
    path = os.path.dirname(outTbl) + os.sep
    ext = arcpy.Describe(outTbl).extension

    #set variables
    buff_temp = path + "feature_buffer" + ext
    FC = checkSpatialReference(outTbl, FC) #check spatial ref

    #create buffers 
    arcpy.Buffer_analysis(outTbl, buff_temp, buff_dist) #buffer each site by buff_dist

    #check if feature is present
    lst_present = buffer_contains(buff_temp, FC)
    booleanLst = []
    for item in lst_present:
        if item == 0:
            booleanLst.append("NO")
        else:
            booleanLst.append("YES")

    #move results to outTbl.field
    lst_to_AddField_lst(outTbl, [field], [booleanLst], ["Text"])
    arcpy.Delete_management(buff_temp)
    
###########EXECUTE###########
try:
    start = time.clock() #start the clock
    absTest_MODULE([outTbl, field, FC, buff_dist])
    start = exec_time(start, "Presence/Absence assessment")
else:
    print("error occured")
