"""
# Name: Tier 1 Rapid Benefit Indicator Assessment- Flood Module
# Purpose: Calculate values for benefit indicators using wetland restoration site polygons
#          and a variety of other input data
# Author: Justin Bousquin
#
# Version Notes:
# Developed in ArcGIS 10.3
# v27 Tier 1 Rapid Benefit Indicator Assessment
# Date: 12/5/2016

#inputs from mxd:
#L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Full_Demo.mxd
"""
###########IMPORTS###########
import os, sys, time
import arcpy
import decimal, itertools
from collections import deque, defaultdict
from arcpy import da
from decimal import *
###########FUNCTIONS##########
""" Delete if exists
Purpose: if a file exists it is deleted and noted in a message message"""
def del_exists(item):
    if arcpy.Exists(item):
        arcpy.Delete_management(item)
        arcpy.AddMessage(str(item) + " already exists, it was deleted and will be replaced.")
        print(str(item) + " already exists, it was deleted and will be replaced.")
        
"""List in buffer
Purpose: generates a list of catchments in buffer"""
def list_buffer(lyr, field, lyr_range):
    arcpy.SelectLayerByAttribute_management(lyr, "CLEAR_SELECTION")
    arcpy.SelectLayerByLocation_management(lyr, "INTERSECT", lyr_range)
    HUC_ID_lst = field_to_lst(lyr, field) #list catchment IDs
    return (HUC_ID_lst)

"""List Downstream
Purpose: generates a list of catchments downstream of catchments in layer"""
#written to alternatively work for upstream
def list_downstream(lyr, field, COMs):
    #list lyr IDs
    HUC_ID_lst = field_to_lst(lyr, field)
    #list catchments downstream of site
    downCatchments = []
    for ID in set(HUC_ID_lst):
        downCatchments.append(children(ID, COMs))
        #upCatchments.append(children(ID, UpCOMs)) #list catchments upstream of site #alt
    #flatten list and remove any duplicates
    downCatchments = set(list(itertools.chain.from_iterable(downCatchments)))
    return(list(downCatchments))

"""List children
Purpose: returns list of all children"""
def children(token, tree):
    visited = set()
    to_crawl = deque([token])
    while to_crawl:
        current = to_crawl.popleft()
        if current in visited:
            continue
        visited.add(current)
        node_children = set(tree[current])
        to_crawl.extendleft(node_children - visited)
    return list(visited)
            
"""Read in NHD Relates
Purpose: read the upstream/downstream table to memory"""
def setNHD_dict(Flow):
    UpCOMs = defaultdict(list)
    DownCOMs = defaultdict(list)
    arcpy.AddMessage("Gathering info on upstream / downstream relationships")
    print("Gathering info on upstream / downstream relationships")
    with arcpy.da.SearchCursor(Flow, ["FROMCOMID", "TOCOMID"]) as cursor:
        for row in cursor:
            FROMCOMID = row[0]
            TOCOMID = row[1]
            if TOCOMID != 0:
                UpCOMs[TOCOMID].append(TOCOMID)
                DownCOMs[FROMCOMID].append(TOCOMID)
    return (UpCOMs, DownCOMs)

"""Selection Query String from list
Purpose: return a string for a where clause from a list of field values
"""
def selectStr_by_list(field, lst):
    exp = ''
    for item in lst:
        exp += '"' + field + '" = ' + str(item) + " OR "
    return (exp[:-4])

"""Global Timer
Purpose: returns the message and calc time since the last time the function was used."""
#Function Notes: used during testing to compare efficiency of each step
def exec_time(start, message):
    end = time.clock()
    comp_time = end - start
    arcpy.AddMessage("Run time for " + message + ": " + str(comp_time))
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
        arcpy.AddMessage("Spatial reference for " + otherFC + " does not match.")
        print("Spatial reference for " + otherFC + " does not match.")
        try:
            path = os.path.dirname(alphaFC)
            newName = os.path.basename(otherFC)
            output = path + os.sep + newName[:-4] + "_prj.shp"
            arcpy.Project_management(otherFC, output, alphaSR)
            fc = output
            arcpy.AddMessage("File was re-projected and saved as " + fc)
            print("File was re-projected and saved as " + fc)
        except:
            arcpy.AddMessage("Warning: spatial reference could not be updated.")
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
#Function Notes: if field is: string, 1 field at a time;
#                               list, 1 field at a time or 1st field is used to sort
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
        print("Something went wrong with the field to list function")
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

#Catchment
Catchment = r"C:\ArcGIS\Local_GIS\NHD_Plus\NHDPlusNationalData\NHDPlusV21_National_Seamless.gdb\NHDPlusCatchment\Catchment"
InputField = "FEATUREID" #field from feature layer

#UpDown
UpDown = "Downstream" #alt = "Upstream"

#watershed is optional
watershed = None

#output table (not the gdb it is in)
#outTbl = params[6].valueAsText
outTbl = r"L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Test_Results\Intermediates2.gdb\Results"
NHD_path = arcpy.Describe(Catchment).Path
Flow = NHD_path.replace('\\NHDPlusCatchment','\\PlusFlow')
        
path = os.path.dirname(outTbl) + os.sep
        
#Copy wetlands in for results
arcpy.CopyFeatures_management(wetlands, outTbl)

start=exec_time(start, "intiating variables")
        
#set variables
outTbl_flood = path + "int_flood.dbf" #table of flood results
#naming convention for flood intermediates
FA = path + "int_FloodArea"

flood_area = FA #+ ".shp"
flood_areaB = FA + "temp_buffer"#.shp" #buffers
flood_areaC = FA + "temp2_zone"#.shp" #buffers
flood_areaD = FA + "temp3_down" #.shp #downstream
flood_areaD_clip_single = FA + "temp3_single" #.shp #downstream
clip_name = os.path.basename(FA) + "temp3_clip" #.shp #single downstream buffer 
assets = FA + "_assets" #addresses/population in flood zone

#3.2: NUMBER WHO BENEFIT                    
#3.2 Step 1: check that there are people in the flood zone
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

#3.2 Step 2: buffer each site by 5 miles
arcpy.Buffer_analysis(outTbl, flood_areaB, "2.5 Miles")
#step 3A: clip the buffer to flood polygon
arcpy.AddMessage("Reducing flood zone to 2.5 Miles from sites...")
print("Reducing flood zone to 2.5 Miles from sites...")
arcpy.Clip_analysis(flood_areaB, flood_zone, flood_areaC)

#3.2 Step 3B: clip the buffered flood area to downstream basins (OPTIONAL)
#if Catchment is not None:
arcpy.AddMessage("Using {} to determine downstream areas of flood zone".format(Catchment))
print("Using {} to determine downstream areas of flood zone".format(Catchment))
arcpy.MakeFeatureLayer_management(flood_areaB, "buffer_lyr")
arcpy.MakeFeatureLayer_management(Catchment, "catchment_lyr")

UpCOMs, DownCOMs = setNHD_dict(Flow) #reduce to downstream only?
#create empty FC for downstream catchments
del_exists(path + os.sep + clip_name) #may not need?
flood_areaD_clip = arcpy.CreateFeatureclass_management(path, clip_name, "POLYGON", spatial_reference = "catchment_lyr")

site_cnt = arcpy.GetCount_management(outTbl)

with arcpy.da.SearchCursor(outTbl, ["SHAPE@", "OID@"]) as cursor:
    for site in cursor:
        #select buffer for site
        where_clause = "OBJECTID = " + str(site[1])
        arcpy.SelectLayerByAttribute_management("buffer_lyr", "NEW_SELECTION", where_clause)
        
        #list catchments in buffer
        bufferCatchments = list_buffer("catchment_lyr", InputField, "buffer_lyr")

        #subset DownCOMs to only those in buffer (keeps them consecutive)
        shortDownCOMs = defaultdict(list)
        for item in bufferCatchments:
            shortDownCOMs[item].append(DownCOMs[item])
            shortDownCOMs[item] = list(itertools.chain.from_iterable(shortDownCOMs[item]))

        #select catchments where the restoration site is
        arcpy.SelectLayerByLocation_management("catchment_lyr", "INTERSECT", site[0])

        #list downstream catchments
        downCatchments = list_downstream("catchment_lyr", InputField, shortDownCOMs)

        #catchments in both lists
        #NOTE: THIS SHOULDN'T BE NEEDED, the last catchment will already be outside the buffer clip
        catchment_lst = list(set(downCatchments).intersection(bufferCatchments))
        
        #SELECT downstream catchments in buffer
        slt_qry_down = selectStr_by_list(InputField, catchment_lst)
        arcpy.SelectLayerByAttribute_management("catchment_lyr", "NEW_SELECTION", slt_qry_down)
        #make this selection into single feature
        arcpy.Dissolve_management("catchment_lyr", flood_areaD_clip_single)
        #append to empty clip set
        arcpy.Append_management(flood_areaD_clip_single, flood_areaD_clip)
        clip_rows = arcpy.GetCount_management(flood_areaD_clip)
        arcpy.AddMessage("Determine catchments downstream for row {}, of {}".format(clip_rows, site_cnt))
        print("Determine catchments downstream for row {}, of {}".format(clip_rows, site_cnt))

#Clip the flood area within each buffer to the corresponding downstream segments
arcpy.AddMessage("Reducing flood zone areas downstream from sites...")
print("Reducing flood zone areas downstream from sites...")
arcpy.Clip_analysis(flood_areaC, flood_areaD_clip, flood_areaD) #FIX THIS

#step 3C: calculate flood area as benefitting percentage
arcpy.AddMessage("Measuring flood zone area downstream of each site...")
print("Measuring flood zone area downstream of each site...")

#Add/calculate fields for flood
arcpy.AddField_management(flood_areaC, "area", "Double")
arcpy.AddField_management(flood_areaC, "area_pct", "Double")
arcpy.CalculateField_management(flood_areaC, "area", "!SHAPE.area!", "PYTHON_9.3", "")
arcpy.AddField_management(flood_areaC, "areaD_pct", "Double")

#Add/calculate fields for downstream flood zone
arcpy.AddField_management(flood_areaD, "areaD", "Double")
arcpy.CalculateField_management(flood_areaD, "areaD", "!SHAPE.area!", "PYTHON_9.3", "")

#move downstream area result to flood zone table
arcpy.JoinField_management(flood_areaC, "OBJECT_ID", flood_areaD, "OBJECT_ID", ["areaD"])

#calculate percent area fields
with arcpy.da.UpdateCursor(flood_areaC, ["area_pct", "area", "BUFF_DIST", "areaD_pct", "areaD"]) as cursor:
    #BUFF_DIST is used rather than 25 sq miles because it is in the datum units used for area calculation
    #if BUFF_DIST is field in wetlands it was renamed by index in flood_area
    for row in cursor:
        row[0] = row[1]/(math.pi*((row[2]**2.0))) #percent of zone (2.5 mile radius) that is flood zone
        row[3] = row[4]/row[1] #percent of flood zone in range that is downstream of site
        cursor.updateRow(row)

lst_floodzoneArea_pct = field_to_lst(flood_areaC, "area_pct")
lst_floodzoneD = field_to_lst(flood_areaC, "areaD")
lst_floodzoneD_pct = field_to_lst(flood_areaC, "areaD_pct")
                
#step 4: calculate number of people benefitting.
arcpy.AddMessage("Counting people who benefit...")
print("Counting people who benefit...")
if addresses is not None:
    lst_flood_cnt = buffer_contains(flood_areaD, assets) #addresses in buffer/flood zone/downstream

elif popRast is not None: #not yet tested
    lst_flood_cnt = buffer_population(flood_areaD, popRast) #population in buffer/flood zone/downstream 
    
start=exec_time(start, "Flood Risk 3.2 How Many Benefit analysis")

#3.3.A: SERVICE QUALITY
arcpy.AddMessage("Measuring area of each restoration site...")
print("Measuring area of each restoration site...")

#calculate area of each restoration site
siteAreaLst =[]
with arcpy.da.SearchCursor(outTbl, ["SHAPE@"]) as cursor:
    for row in cursor:
        siteAreaLst.append(row[0].getArea("GEODESIC", "ACRES"))

start = exec_time (start, "Flood Risk 3.3.A Service Quality analysis")

#3.3.B: SUBSTITUTES
if subs is not None:
    arcpy.AddMessage("Estimating number of substitutes within 2.5 miles downstream of restoration site...")
    print("Estimating number of substitutes within 2.5 miles downstream of restoration site...")
    subs = checkSpatialReference(outTbl, subs)

    lst_subs_cnt = buffer_contains(flood_areaD, subs) #subs in buffer/flood/downstream

    #convert lst to binary list
    lst_subs_cnt_boolean = []
    for item in lst_subs_cnt:
          if item >0:
              lst_subs_cnt_boolean.append("YES")
          else:
              lst_subs_cnt_boolean.append("NO")

    start = exec_time (start, "Flood Risk 3.3.B Scarcity (substitutes) analysis")
        
#3.3.B: SCARCITY
if ExistingWetlands is not None:
    arcpy.AddMessage("Estimating area of wetlands within 2.5 miles in both directions (5 miles total) of restoration site...")
    print("Estimating area of wetlands within 2.5 miles in both directions (5 miles total) of restoration site...")
    ExistingWetlands = checkSpatialReference(outTbl, ExistingWetlands) #check spatial ref
    #lst_floodRet_Density = percent_cover(ExistingWetlands, flood_areaC) #analysis for scarcity
#CONCERN- the above only looks at wetlands in the flood areas within 2.5 miles, the below does entire buffer
    lst_floodRet_Density = percent_cover(ExistingWetlands, flood_areaB) #analysis for scarcity
#CONCERN: THIS IS WICKED SLOW
    start = exec_time (start, "Flood Risk 3.3.B Scarcity analysis")
                                          
#FINAL STEP: move results to results file
#count of beneficiaries = lst_flood_cnt
arcpy.AddField_management(outTbl, "FR_2_cnt", "Double")
lst_to_field(outTbl, "FR_2_cnt", lst_flood_cnt)
#percent surrounding area in flood zone = lst_floodzoneArea_pct(not in summary)
arcpy.AddField_management(outTbl, "FR_zPct", "Double")
lst_to_field(outTbl, "FR_zPct", lst_floodzoneArea_pct)  
#area of flood zone downstream = lst_floodzoneD(not in summary)
arcpy.AddField_management(outTbl, "FR_zDown", "Double")
lst_to_field(outTbl, "FR_zDown", lst_floodzoneD)          
#percent of flood zone downstream = lst_floodzoneD_pct(not in summary)
arcpy.AddField_management(outTbl, "FR_zDoPct", "Double")
lst_to_field(outTbl, "FR_zDoPct", lst_floodzoneD_pct)
#area of each site = siteAreaLst
arcpy.AddField_management(outTbl, "FR_3A_acr", "Double")
lst_to_field(outTbl, "FR_3A_acr", siteAreaLst)
#subs at each site = lst_subs_cnt (not in summary)
arcpy.AddField_management(outTbl, "FR_sub", "Double")
lst_to_field(outTbl, "FR_sub", lst_subs_cnt)
#subs at each site Y/N = lst_subs_cnt_boolean
arcpy.AddField_management(outTbl, "FR_3B_boo", "Text")
lst_to_field(outTbl, "FR_3B_boo", lst_subs_cnt_boolean)
#scarcitty at each site =lst_floodRet_Density
arcpy.AddField_management(outTbl, "FR_3B_sca", "Double")
lst_to_field(outTbl, "FR_3B_sca", lst_floodRet_Density)

#cleanup
arcpy.Delete_management(flood_areaD_Clip)
arcpy.Delete_management(flood_areaD)
arcpy.Delete_management(flood_areaC)
arcpy.Delete_management(flood_areaB)
arcpy.Delete_management(flood_area)
arcpy.Delete_management(assets)
                                   
arcpy.AddMessage("Flood Module Complete")
start=exec_time(start, "flood module")
#############################
