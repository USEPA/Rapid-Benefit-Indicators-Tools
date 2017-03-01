"""
# Name: Tier 1 Rapid Benefit Indicator Assessment- Flood Module
# Purpose: Calculate values for benefit indicators using wetland restoration site polygons
#          and a variety of other input data
# Author: Justin Bousquin
# Additional Author Credits: Marc Weber and Tad Larsen (StreamCat)

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
from collections import deque, defaultdict
from decimal import *

arcpy.env.parallelProcessingFactor = "100%" #use all available resources

##########USER INPUTS#########
addresses =
popRast =
flood_zone =
OriWetlands =
subs =
Catchment =
InputField =
relTbl =
outTbl =
###############################
#inputs gdb
#in_gdb = r"L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Test_Inputs.gdb"
#wetlands = params[0].valueAsText
#wetlands = in_gdb + os.sep + "restoration_Sites"
#addresses = params[1].valueAsText
#addresses = in_gdb+ os.sep + "e911_14_Addresses"
#popRast = params[2].valueAsText
#popRast = None
#flood_zone = params[3].valueAsText
#flood_zone = in_gdb + os.sep + "FEMA_FloodZones_clp"
#ExistingWetlands = params[4].valueAtText
#ExistingWetlands = in_gdb + os.sep + "NWI14"
#subs = params[5].valueAsText
#subs = in_gdb + os.sep + "dams"
#Catchment = r"C:\ArcGIS\Local_GIS\NHD_Plus\NHDPlusNationalData\NHDPlusV21_National_Seamless.gdb\NHDPlusCatchment\Catchment"
#InputField = "FEATUREID" #field from feature layer
#UpDown = "Downstream" #alt = "Upstream"
#output table (not the gdb it is in)
#outTbl = params[6].valueAsText
#outTbl = r"L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Test_Results\Intermediates2.gdb\Results"
#NHD_path = arcpy.Describe(Catchment).Path
#Flow = NHD_path.replace('\\NHDPlusCatchment','\\PlusFlow')
##############################
###########FUNCTIONS##########
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

"""Read in NHD Relates
Purpose: read the upstream/downstream table to memory"""
def setNHD_dict(Flow):
    UpCOMs = defaultdict(list)
    DownCOMs = defaultdict(list)
    print("Gathering info on upstream / downstream relationships")
    with arcpy.da.SearchCursor(Flow, ["FROMCOMID", "TOCOMID"]) as cursor:
        for row in cursor:
            FROMCOMID = row[0]
            TOCOMID = row[1]
            if TOCOMID != 0:
                UpCOMs[TOCOMID].append(TOCOMID)
                DownCOMs[FROMCOMID].append(TOCOMID)
    return (UpCOMs, DownCOMs)

""" Delete if exists
Purpose: if a file exists it is deleted and noted in a message message"""
def del_exists(item):
    if arcpy.Exists(item):
        arcpy.Delete_management(item)
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
        print("Something went wrong with the field to list function")
    return lst

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

"""Quantitative List to Qualitative List
Purpose: convert counts of >0 to YES"""
def quant_to_qual_lst(lst):
    qual_lst = []
    for i in lst:
        if (i == 0):
            qual_lst.append("NO")
        else:
            qual_lst.append("YES")
    return qual_lst

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
        
"""delete listed feature classes or layers
Purpose: delete feature classes or layers using a list"""
def deleteFC_Lst(lst):
    for l in lst:
        arcpy.Delete_management(l)
        
###########FLOODING###########
def FR_MODULE(PARAMS):
    start1 = time.clock() #start the clock (full module)
    start = time.clock() #start the clock (parts)

    addresses, popRast = PARAMS[0], PARAMS[1]
    flood_zone = PARAMS[2]
    ExistingWetlands, subs = PARAMS[3], PARAMS[4]
    Catchment, InputField, Flow = PARAMS[5], PARAMS[6], PARAMS[7]
    outTbl = PARAMS[8]

    path = os.path.dirname(outTbl) + os.sep
    ext = arcpy.Describe(outTbl).extension

    #set variables
    FA = path + "int_FloodArea" #naming convention for flood intermediates

    flood_areaB = FA + "temp_buffer" + ext #buffers
    flood_areaC = FA + "temp2_zone" + ext #flood zone in buffer
    flood_areaD_clip = FA + "temp3_clip" + ext #downstream
    flood_areaD_clip_single = FA + "temp3_single" + ext #single site's downstream area
    clip_name = os.path.basename(FA) + "temp3_down" + ext #single downstream buffer
    flood_areaD = path + os.sep + clip_name + ext
    assets = FA + "_assets" + ext #addresses/population in flood zone
            
    start=exec_time(start, "intiating variables for Flood Risk")

    #3.2 - NUMBER WHO BENEFIT                    
    #3.2 - Step 1: check that there are people in the flood zone
    flood_zone = checkSpatialReference(outTbl, flood_zone) #check spatial ref
    if addresses is not None: #if using addresses
        arcpy.Clip_analysis(addresses, flood_zone, assets)
        total_cnt = arcpy.GetCount_management(assets) #count addresses
        if int(total_cnt.getOutput(0)) <= 0: #if there are no addresses in flood zones stop analysis
            arcpy.AddError("No addresses were found within the flooded area.")
            print("No addresses were found within the flooded area.")
            raise arcpy.ExecuteError
    elif popRast is not None: #NOT YET TESTED
        arcpy.Clip_management(popRast, "", assets, flood_zone, "", "ClippingGeometry", "NO_MAINTAIN_EXTENT")
        #add error handel to fail if floodarea contains no population
        if cond <= 0:
            arcpy.AddError("Nothing to do with input raster yet")
            print("Nothing to do with input raster yet")
            raise arcpy.ExecuteError

    #3.2 - Step 2: buffer each site by 2.5 mile radius
    arcpy.Buffer_analysis(outTbl, flood_areaB, "2.5 Miles")
    #3.2 - Step 3A: clip the buffer to flood polygon
    print("Reducing flood zone to 2.5 Miles from sites...")
    arcpy.Clip_analysis(flood_areaB, flood_zone, flood_areaC)
    #3.2 - Step 3B: clip the buffered flood area to downstream basins (OPTIONAL?)
    #if Catchment is not None:
    print("Using {} to determine downstream areas of flood zone".format(Catchment))

    arcpy.MakeFeatureLayer_management(flood_areaB, "buffer_lyr")
    arcpy.MakeFeatureLayer_management(flood_areaC, "flood_zone_lyr")
    arcpy.MakeFeatureLayer_management(Catchment, "catchment_lyr")

    UpCOMs, DownCOMs = setNHD_dict(Flow) #REDUCE TO DownCOMs ONLY
    #create empty FC for downstream catchments
    del_exists(path + os.sep + clip_name)
    arcpy.CreateFeatureclass_management(path, clip_name, "POLYGON", spatial_reference = "flood_zone_lyr")

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

            #list catchments downstream selection
            downCatchments = list_downstream("catchment_lyr", InputField, shortDownCOMs)

            #catchments in both lists
            #NOTE: this is redundant, the last catchment will already be outside the buffer clip
            catchment_lst = list(set(downCatchments).intersection(bufferCatchments))
            
            #SELECT downstream catchments in buffer
            slt_qry_down = selectStr_by_list(InputField, catchment_lst)
            arcpy.SelectLayerByAttribute_management("catchment_lyr", "NEW_SELECTION", slt_qry_down)
            #may need to make this selection into single feature for population as raster
            #arcpy.Dissolve_management("catchment_lyr", flood_areaD_clip_single)

            #select and clip corresponding flood zone
            arcpy.SelectLayerByAttribute_management("flood_zone_lyr", "NEW_SELECTION", where_clause)
            arcpy.Clip_analysis("flood_zone_lyr", "catchment_lyr", flood_areaD_clip)
            arcpy.MakeFeatureLayer_management(flood_areaD_clip, "flood_zone_down_lyr")
            arcpy.Dissolve_management("flood_zone_down_lyr", flood_areaD_clip_single)
                               
            #append to empty clipped set
            arcpy.Append_management(flood_areaD_clip_single, flood_areaD)
            clip_rows = arcpy.GetCount_management(flood_areaD)
            print("Determined catchments downstream for site {}, of {}".format(clip_rows, site_cnt))

    print("Finished reducing flood zone areas to downstream from sites...")

    #3.2 - Step 3C: calculate flood area as benefitting percentage
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
    arcpy.JoinField_management(flood_areaC, "OBJECTID", flood_areaD, "OBJECTID", ["areaD"])

    #calculate percent area fields
    with arcpy.da.UpdateCursor(flood_areaC, ["area_pct", "area", "BUFF_DIST", "areaD_pct", "areaD"]) as cursor:
        #BUFF_DIST is used rather than 25 sq miles because it is in the datum units used for area calculation
        #if BUFF_DIST is field in wetlands it was renamed by index in flood_area
        for row in cursor:
            row[0] = row[1]/(math.pi*((row[2]**2.0))) #percent of zone (2.5 mile radius) that is flood zone
            if row[4] is not None:
                row[3] = row[4]/row[1] #percent of flood zone in range that is downstream of site
            cursor.updateRow(row)

    lst_floodzoneArea_pct = field_to_lst(flood_areaC, "area_pct")
    lst_floodzoneD = field_to_lst(flood_areaC, "areaD")
    lst_floodzoneD_pct = field_to_lst(flood_areaC, "areaD_pct")

    #3.2 - Step 4: calculate number of people benefitting
    print("Counting people who benefit...")
    if addresses is not None:
        lst_flood_cnt = buffer_contains(str(flood_areaD), assets) #addresses in buffer/flood zone/downstream

    elif popRast is not None: #not yet tested
        lst_flood_cnt = buffer_population(flood_areaD, popRast) #population in buffer/flood zone/downstream 
        
    start=exec_time(start, "Flood Risk Reduction analysis: 3.2 How Many Benefit")

    #3.3.A: SERVICE QUALITY
    print("Measuring area of each restoration site...")

    #calculate area of each restoration site
    siteAreaLst =[]
    with arcpy.da.SearchCursor(outTbl, ["SHAPE@"]) as cursor:
        for row in cursor:
            siteAreaLst.append(row[0].getArea("GEODESIC", "ACRES"))

    start = exec_time (start, "Flood Risk Reduction analysis: 3.3.A Service Quality")

    #3.3.B: SUBSTITUTES
    if subs is not None:
        print("Estimating number of substitutes within 2.5 miles downstream of restoration site...")
        subs = checkSpatialReference(outTbl, subs)

        lst_subs_cnt = buffer_contains(str(flood_areaD), subs) #subs in buffer/flood/downstream

        #convert lst to binary list
        lst_subs_cnt_boolean = quant_to_qual_lst(lst_subs_cnt)

        start = exec_time (start, "Flood Risk Reduction analysis: 3.3.B Scarcity (substitutes - 'FR_3B_boo')")
    else:
        print("Substitutes (dams and levees) input not specified, 'FR_sub' will all be '0' and 'FR_3B_boo' will be left blank.")
        lst_subs_cnt, lst_subs_cnt_boolean = [], []
            
    #3.3.B: SCARCITY
    if ExistingWetlands is not None:
        print("Estimating area of wetlands within 2.5 miles in both directions (5 miles total) of restoration site...")
        #lst_floodRet_Density = percent_cover(ExistingWetlands, flood_areaC) #analysis for scarcity
    #CONCERN- the above only looks at wetlands in the flood areas within 2.5 miles, the below does entire buffer.
    #Should this be restricted to upstream/downstream?
        lst_floodRet_Density = percent_cover(ExistingWetlands, flood_areaB) #analysis for scarcity
    #CONCERN: THIS IS WICKED SLOW
        start = exec_time (start, "Flood Risk Reduction analysis: Scarcity (scarcity - 'FR_3B_sca')")
    else:
        print("Substitutes (existing wetlands) input not specified, 'FR_3B_sca' will all be '0'.")
        lst_floodRet_Density = []
        
    #FINAL STEP: move results to results file
    fields_lst = ["FR_2_cnt", "FR_zPct", "FR_zDown", "FR_zDoPct", "FR_3A_acr", "FR_3A_boo", "FR_sub",
                  "FR_3B_boo", "FR_3B_sca", "FR_3D_boo"]
    list_lst = [lst_flood_cnt, lst_floodzoneArea_pct, lst_floodzoneD, lst_floodzoneD_pct, siteAreaLst, [], lst_subs_cnt,
                lst_subs_cnt_boolean, lst_floodRet_Density, []]
    type_lst = ["", "", "", "", "", "Text", "", "Text", "", "Text"]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, type_lst)

    #cleanup
    deleteFC_Lst([flood_areaD_clip_single, flood_areaD_clip, str(flood_areaD), flood_areaC, flood_areaB, assets])
    deleteFC_Lst(["flood_zone_lyr", "flood_zone_down_lyr", "catchment_lyr", "polyLyr", "buffer_lyr"])
                                       
    print("Flood Module Complete")
    start1=exec_time(start1, "full flood module")

#########################
#########EXECUTE#########
try:
    start = time.clock()
    FR_MODULE([addresses, popRast, flood_zone, OriWetlands, subs, Catchment, InputField, relTbl, outTbl])
    start = exec_time(start1, "Flood Risk Benefit assessment")
else:
    print("Flood Risk Benefits not assessed")
