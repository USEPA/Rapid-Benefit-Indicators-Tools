"""
# Name: Tier 1 Rapid Benefit Indicator Assessment- Flood Module
# Purpose: Calculate values for benefit indicators using wetland restoration site polygons
#          and a variety of other input data
# Author: Justin Bousquin
#
# Version Notes:
# Developed in ArcGIS 10.3
# v27 Tier 1 Rapid Benefit Indicator Assessment
# Date: 11/7/2016

#inputs from mxd:
#L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Full_Demo.mxd
"""
###########IMPORTS###########
import os, sys, time
import arcpy
from arcpy import da
from decimal import *
###########FUNCTIONS##########
"""Global Timer
Purpose: returns the message and calc time since the last time the function was used."""
#Function Notes: used during testing to compare efficiency of each step
def exec_time(start, message):
    end = time.clock()
    comp_time = end - start
    arcpy.AddMessage("Run time for " + message + ": " + str(comp_time))
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
        arcpy.AddMessage("Spatial reference for " + otherFC + " does not match.")
        try:
            path = os.path.dirname(alphaFC)
            newName = os.path.basename(otherFC)
            output = path + os.sep + newName[:-4] + "_prj.shp"
            arcpy.Project_management(otherFC, output, alphaSR)
            fc = output
            arcpy.AddMessage("File was re-projected and saved as " + fc)
        except:
            arcpy.AddMessage("Warning: spatial reference could not be updated.")
            fc = otherFC
    else:
        fc = otherFC
    return fc

"""Buffer Contains
Purpose: returns number of points in buffer as list"""
#Function Notes:
#Example: lst = buffer_contains(view_50, addresses)
def buffer_contains(poly, pnts):
    lst = []
    #poly_out = poly[:-4] + "_2.shp" #check to be sure this is created in outTbl folder
    poly_out = poly + "_2" #if this is created in outTbl GDB
    arcpy.SpatialJoin_analysis(poly, pnts, poly_out, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "INTERSECT", "", "")
    lst = field_to_lst(poly_out, ["ORIG_FID", "Join_Count"])
    arcpy.Delete_management(poly_out)
    return lst

"""Buffer Population
Purpose: returns sum of raster cells in buffer as list"""
#Function Notes: Currently works on raster of population total (not density)
#Function Notes: Requires Spatial Analyst (look into rasterstats as alternative?)
#https://pcjericks.github.io/py-gdalogr-cookbook/raster_layers.html
def buffer_population(poly, popRaster):
    lst = []
    tempDBF = poly[:-4]+"_pop.dbf"
    arcpy.sa.ZonalStatisticsAsTable(poly, "FID", popRaster, tempDBF, "", "SUM")
    lst = field_to_lst(tempDBF, ["FID_", "SUM"]) #"AREA" "OID" "COUNT"
    arcpy.Delete_management(tempDBF)
    return lst

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

"""Read Field to List
Purpose:"""
#Function Notes: if field is: string, 1 field at a time; list , 1 field at a time or 1st field is used to sort
#Example: lst = field_to_lst("table.shp", "fieldName")
def field_to_lst(table, field):
    lst = []
    if type(field) == str:
        with arcpy.da.SearchCursor(table, [field]) as cursor:
            for row in cursor:
                lst.append(row[0])
    elif type(field) == list:
        if len(field) == 1:
            with arcpy.da.SearchCursor(table, field) as cursor:
                for row in cursor:
                    lst.append(row[0])
        else: #first field is used to sort, second field returned as list
            orderLst = []
            with arcpy.da.SearchCursor(table, field) as cursor:
                for row in cursor:
                    orderLst.append(row[0])
                    lst.append(row[1])
            orderLst, lst = (list(x) for x in zip(*sorted(zip(orderLst, lst))))
    else:
        arcpy.AddMessage("Something went wrong with the field to list function")
    return lst

"""Add List to Field
Purpose: """
#Function Notes: 1 field at a time
#Example: lst_to_field(featureClass, "fieldName", lst)
def lst_to_field(table, field, lst):
    i=0
    with arcpy.da.UpdateCursor(table, [field]) as cursor:
        for row in cursor:
            row[0] = lst[i]
            i+=1
            cursor.updateRow(row)
###########FLOODING##########

start = time.clock() #start the clock
#inputs gdb
in_gdb = r"L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Test_Inputs.gdb"

#params = [restorationSites, addresses, popRast, floodZone, existingWetlands, dams, outTbl]
#define variables from user inputs
#wetlands = params[0].valueAsText
wetlands = in_gdb + os.sep + "restoration_Sites"

#addresses = params[1].valueAsText
addresses = in_gdb+ os.sep + "e911_14_Addresses"

#popRast = params[2].valueAsText
popRast = None

#flood_zone = params[3].valueAsText
flood_zone = in_gdb + os.sep + "FEMA_FloodZones_clp"

#ExistingWetlands = params[4].valueAtText
ExistingWetlands = in_gdb + os.sep + "NWI14"

#subs = params[5].valueAsText
subs = in_gdb + os.sep + "dams"

#watershed is optional
watershed = None

#output table (not the gdb it is in)
#outTbl = params[6].valueAsText
outTbl = r"L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Test_Results\Intermediates2.gdb\Results"
        
path = os.path.dirname(outTbl) + os.sep
        
#Copy wetlands in for results
arcpy.CopyFeatures_management(wetlands, outTbl)

start=exec_time(start, "intiating variables")
        
#set variables
outTbl_flood = path + "int_flood.dbf" #table of flood results
#naming convention for flood intermediates
floodArea = path + "int_FloodArea"

flood_area = floodArea #+ ".shp"
flood_areaB = floodArea + "temp"#.shp" #buffers
flood_areaC = floodArea + "temp2"#.shp" #buffers
assets = floodArea + "_assets" #addresses/population in flood zone

#3.2: NUMBER WHO BENEFIT                    
#step 1: check that there are people in the flood zone
if addresses is not None: #if using addresses
    addresses = checkSpatialReference(outTbl, addresses) #check spatial ref
    flood_zone = checkSpatialReference(outTbl, flood_zone) #check spatial ref
    #start cutting back the datasets
    if watershed is not None: #if user specified watershed
        watershed = checkSpatialReference(outTbl, watershed)
        #limit flood zone to what is within watershed
        flood_zone = arcpy.Clip_analysis(flood_zone, watershed, flood_area)
    #limit addresses to only those within the flood_zone
    arcpy.Clip_analysis(addresses, flood_zone, assets)
    total_cnt = arcpy.GetCount_management(assets) #count addresses
    if int(total_cnt.getOutput(0)) <= 0: #if there are no addresses in flood zones stop analysis
        arcpy.AddError("No addresses were found within the flooded area.")
        print("No addresses were found within the flooded area.")
        raise arcpy.ExecuteError
elif popRast is not None: #not yet tested
    #check projection?
    if watershed is not None: #if user specified watershed
        watershed = checkSpatialReference(outTbl, watershed)
        #limit flood zone to what is within watershed
        flood_zone = arcpy.Clip_analysis(flood_zone, watershed, flood_area)
    arcpy.Clip_management(popRast, "", assets, flood_zone, "", "ClippingGeometry", "NO_MAINTAIN_EXTENT")
    #add error handel to fail if floodarea contains no population    
    arcpy.AddError("Nothing to do with input raster yet")
    print("Nothing to do with input raster yet")
    raise arcpy.ExecuteError
else:
    arcpy.AddError("No population inputs specified")

#step 2: buffer each site by 5 miles
arcpy.Buffer_analysis(outTbl, flood_areaB, "2.5 Miles")
#step 3A: clip the buffer to flood polygon
arcpy.Clip_analysis(flood_areaB, flood_zone, flood_areaC)
#step 3B: clip the buffered flood area to downstream basins (OPTIONAL)
        
#step 3C: calculate flood area as benefitting percentage
arcpy.AddField_management(flood_areaC, "area", "Double")
arcpy.AddField_management(flood_areaC, "area_pct", "Double")
arcpy.CalculateField_management(flood_areaC, "area", "!SHAPE.area!", "PYTHON_9.3", "")

with arcpy.da.UpdateCursor(flood_areaC, ["area_pct", "area", "BUFF_DIST"]) as cursor:
    #BUFF_DIST is used rather than 25 sq miles because it is in the datum units used for area calculation
    #if BUFF_DIST is field in wetlands it was renamed by index in flood_area
    for row in cursor:
        row[0] = row[1]/(math.pi*((row[2]**2.0)))
        cursor.updateRow(row)
                
#step 4: calculate number of people benefitting.
if addresses is not None:
    lst_flood_cnt = buffer_contains(flood_areaC, assets) #addresses in buffer/flood

elif popRast is not None: #not yet tested
    lst_flood_cnt = buffer_population(flood_areaC, popRast)
#add results at end (lst_flood_cnt)
    
start=exec_time(start, "flood analysis")

#3.3.A: SERVICE QUALITY
#calculate area of each restoration site
siteAreaLst =[]
with arcpy.da.SearchCursor(outTbl, ["SHAPE@"]) as cursor:
    for row in cursor:
        siteAreaLst.append(row[0].getArea("GEODESIC", "ACRES"))
#add results at end (siteAreaLst)

##STOPPED DE-BUG HERE
        
#3.3.B: SCARCITY
if ExistingWetlands is not None:
    ExistingWetlands = checkSpatialReference(outTbl, ExistingWetlands) #check spatial ref
    #lst_floodRet_Density = percent_cover(ExistingWetlands, flood_areaC) #analysis for scarcity
#CONCERN- the above only looks at wetlands in the flood areas within 2.5 miles, the below does entire buffer (up/down outside)
    lst_floodRet_Density = percent_cover(ExistingWetlands, flood_areaB) #analysis for scarcity
#CONCERN: THIS IS WICKED SLOW
#add results at end (lst_floodRet_Density)

#3.3.C: SUBSTITUTES
if subs is not None:
    subs = checkSpatialReference(outTbl, subs)
    lst_subs_cnt = buffer_contains(flood_areaC, assets) #subs in buffer/flood
    #lst_subs_cnt = buffer_contains(flood_areaB, subs) # all subs in 2.5 miles
    #lst_subs_cnt = buffer_contains(flood_area, subs) #only subs in flood zone
        #list how many dams/levees in flood of buffersmanagement(outTbl, "Flood_sub", "Double")
        #lst_to_field(outTbl, "Flood_cnt", lst_subs_cnt)
#add results at end (lst_subs_cnt)

start=exec_time(start, "flood benefit")
                                           
#FINAL STEP: move results to results file
#count of beneficiaries = lst_flood_cnt
arcpy.AddField_management(outTbl, "Flood_cnt", "Double")
lst_to_field(outTbl, "Flood_cnt", lst_flood_cnt)
#area of each site = siteAreaLst
arcpy.AddField_management(outTbl, "Flood_acr", "Double")
lst_to_field(outTbl, "Flood_acr", siteAreaLst)
#scarcitty at each site =lst_floodRet_Density
arcpy.AddField_management(outTbl, "FScarcity", "Double")
lst_to_field(outTbl, "Fscarcity", lst_floodRet_Density)
#subs at each site = lst_subs_cnt
arcpy.AddField_management(outTbl, "Flood_sub", "Double")
lst_to_field(outTbl, "Flood_sub", lst_subs_cnt)

#cleanup
arcpy.Delete_management(flood_areaC)
arcpy.Delete_management(flood_areaB)
arcpy.Delete_management(flood_area)
arcpy.Delete_management(assets)
                                   
arcpy.AddMessage("Flood Module Complete")
start=exec_time(start, "flood module")
#############################
