"""
# Name: Tier 1 Rapid Benefit Indicator Assessment- All Modules
# Purpose: Calculate values for benefit indicators using wetland restoration site polygons
#          and a variety of other input data
# Author: Justin Bousquin
# Additional Author Credits: Marc Weber and Tad Larsen (StreamCat)

# Version Notes:
# Developed in ArcGIS 10.3
# v27 Tier 1 Rapid Benefit Indicator Assessment
"""
###########IMPORTS###########
import os, sys, time
import arcpy
import decimal, itertools
from arcpy import da, env
from collections import deque, defaultdict
from decimal import *

arcpy.env.parallelProcessingFactor = "100%" #use all available resources

###########FUNCTIONS###########
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

"""Calculate Weighted View Score
Purpose: list of weighted view scores."""
#Function Notes: Does not currently test that the lists are of equal length
def view_score(lst_50, lst_100):
    lst =[]
    i=0
    #add test for equal length of lists? (robust check, but should never happen)
    #if len(lst_50) != len(lst_100):
    #   arcpy.AddMessage("Error in view score function, unequal list lengths")
    #   break
    for item in lst_50:
       lst.append(lst_50[i] * 0.7 + lst_100[i] * 0.3)
       i+=1
    return lst

"""Set Input Parameter
Purpose: returns arcpy.Parameter for provided string, setting defaults for missing."""
def setParam(str1, str2, str3, str4, str5, multiValue=False):
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
        direction = lst[4],
        multiValue = multiValue)

"""Disable Parameter List
Purpose: disables input fields for a list of parameters"""
def disableParamLst(lst):
    for field in lst:
        field.enabled = False
    
"""Generic message
Purpose: prints string message in py or pyt"""
def message(string):
    arcpy.AddMessage(string)
    print(string)

"""Global Timer
Purpose: returns the message and calc time since the last time the function was used."""
#Function Notes: used during testing to compare efficiency of each step
def exec_time(start, message):
    end = time.clock()
    comp_time = time.strftime("%H:%M:%S", time.gmtime(end-start))
    arcpy.AddMessage("Run time for " + message + ": " + str(comp_time))
    print("Run time for " + message + ": " + str(comp_time))
    start = time.clock()
    return start

""" Delete if exists
Purpose: if a file exists it is deleted and noted in a message message"""
def del_exists(item):
    if arcpy.Exists(item):
        arcpy.Delete_management(item)
        arcpy.AddMessage(str(item) + " already exists, it was deleted and will be replaced.")
        print(str(item) + " already exists, it was deleted and will be replaced.")
        
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
            ext = arcpy.Describe(alphaFC).extension
            newName = os.path.basename(otherFC)
            output = path + os.sep + os.path.splitext(newName)[0] + "_prj" + ext
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

"""Donut Buffer
Purpose: takes inside buffer and creates outside buffers. Ensures ORIG_FID is correct."""
#Function Notes: there can be multiple buffer distances, but must be list
def buffer_donut(FC, outFC, buf, units):
    ext = arcpy.Describe(FC).extension
    FCsort = os.path.splitext(FC)[0] + "_2"  + ext #the buffers should all be in the outTbl folder
    arcpy.Sort_management(FC, FCsort, [["ORIG_FID", "ASCENDING"]]) #sort FC by ORGI_FID
    arcpy.MultipleRingBuffer_analysis(FCsort, outFC, buf, units, "Distance", "NONE", "OUTSIDE_ONLY") #new buffer
    arcpy.Delete_management(FCsort) #Delete intermediate FC
    return outFC

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
        
"""List in buffer
Purpose: generates a list of catchments in buffer"""
def list_buffer(lyr, field, lyr_range):
    arcpy.SelectLayerByAttribute_management(lyr, "CLEAR_SELECTION")
    arcpy.SelectLayerByLocation_management(lyr, "INTERSECT", lyr_range)
    HUC_ID_lst = field_to_lst(lyr, field) #list catchment IDs
    return (HUC_ID_lst)

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
        arcpy.AddMessage("Something went wrong with the field to list function")
        print("Something went wrong with the field to list function")
    return lst

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

"""Lists to ADD Field
Purpose: """
#Function Notes: table, list of new fields, list of listes of field values, list of field datatypes
def lst_to_AddField_lst(table, field_lst, list_lst, type_lst):
    if len(field_lst) != len(field_lst) or len(field_lst) != len(type_lst):
        message("ERROR: lists aren't the same length!")
    #"" defaults to "DOUBLE"
    type_lst = ["Double" if x == "" else x for x in type_lst]

    i = 0
    for field in field_lst:
        #add fields
        arcpy.AddField_management(table, field, type_lst[i])
        #add values
        lst_to_field(table, field, list_lst[i])
        i +=1
    
"""Unique Values
Purpose: returns a sorted list of unique values"""
#Function Notes: used to find unique field values in table column
def unique_values(table, field):
    with arcpy.da.SearchCursor(table, [field]) as cursor:
        return sorted({row[0] for row in cursor if row[0]})

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

###########MODULES############
##########FLOOD RISK##########
def FR_MODULE(PARAMS):
    start1 = time.clock() #start the clock (full module)
    start = time.clock() #start the clock (parts)

    addresses, popRast = PARAMS[0], PARAMS[1]
    flood_zone = PARAMS[2]
    ExistingWetlands, subs = PARAMS[3], PARAMS[4]
    Catchment, InputField = PARAMS[5], PARAMS[6]
    outTbl = PARAMS[7]

    path = os.path.dirname(outTbl) + os.sep
    ext = arcpy.Describe(outTbl).extension
    NHD_path = arcpy.Describe(Catchment).Path
    Flow = NHD_path.replace('\\NHDPlusCatchment','\\PlusFlow')

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
    message("Reducing flood zone to 2.5 Miles from sites...")
    arcpy.Clip_analysis(flood_areaB, flood_zone, flood_areaC)
    #3.2 - Step 3B: clip the buffered flood area to downstream basins (OPTIONAL?)
    #if Catchment is not None:
    message("Using {} to determine downstream areas of flood zone".format(Catchment))

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
            message("Determined catchments downstream for site {}, of {}".format(clip_rows, site_cnt))

    message("Finished reducing flood zone areas to downstream from sites...")

    #3.2 - Step 3C: calculate flood area as benefitting percentage
    message("Measuring flood zone area downstream of each site...")

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
    message("Counting people who benefit...")
    if addresses is not None:
        lst_flood_cnt = buffer_contains(str(flood_areaD), assets) #addresses in buffer/flood zone/downstream

    elif popRast is not None: #not yet tested
        lst_flood_cnt = buffer_population(flood_areaD, popRast) #population in buffer/flood zone/downstream 
        
    start=exec_time(start, "Flood Risk 3.2 How Many Benefit analysis")

    #3.3.A: SERVICE QUALITY
    message("Measuring area of each restoration site...")

    #calculate area of each restoration site
    siteAreaLst =[]
    with arcpy.da.SearchCursor(outTbl, ["SHAPE@"]) as cursor:
        for row in cursor:
            siteAreaLst.append(row[0].getArea("GEODESIC", "ACRES"))

    start = exec_time (start, "Flood Risk 3.3.A Service Quality analysis")

    #3.3.B: SUBSTITUTES
    if subs is not None:
        message("Estimating number of substitutes within 2.5 miles downstream of restoration site...")
        subs = checkSpatialReference(outTbl, subs)

        lst_subs_cnt = buffer_contains(str(flood_areaD), subs) #subs in buffer/flood/downstream

        #convert lst to binary list
        lst_subs_cnt_boolean = quant_to_qual_lst(lst_subs_cnt)

        start = exec_time (start, "Flood Risk 3.3.B Scarcity (substitutes - 'FR_3B_boo') analysis")
    else:
        message("Substitutes (dams and levees) input not specified, 'FR_sub' will all be '0' and 'FR_3B_boo' will be left blank.")
        lst_subs_cnt, lst_subs_cnt_boolean = [], []
            
    #3.3.B: SCARCITY
    if ExistingWetlands is not None:
        message("Estimating area of wetlands within 2.5 miles in both directions (5 miles total) of restoration site...")
        #lst_floodRet_Density = percent_cover(ExistingWetlands, flood_areaC) #analysis for scarcity
    #CONCERN- the above only looks at wetlands in the flood areas within 2.5 miles, the below does entire buffer.
    #Should this be restricted to upstream/downstream?
        lst_floodRet_Density = percent_cover(ExistingWetlands, flood_areaB) #analysis for scarcity
    #CONCERN: THIS IS WICKED SLOW
        start = exec_time (start, "Flood Risk 3.3.B Scarcity (scarcity - 'FR_3B_sca') analysis")
    else:
        message("Substitutes (existing wetlands) input not specified, 'FR_3B_sca' will all be '0'.")
        lst_floodRet_Density = []
        
    #FINAL STEP: move results to results file
    fields_lst = ["FR_2_cnt", "FR_zPct", "FR_zDown", "FR_zDoPct", "FR_3A_acr", "FR_3A_boo", "FR_sub",
                  "FR_3B_boo", "FR_3B_sca", "FR_3D_boo"]
    list_lst = [lst_flood_cnt, lst_floodzoneArea_pct, lst_floodzoneD, lst_floodzoneD_pct, siteAreaLst, [], lst_subs_cnt,
                lst_subs_cnt_boolean, lst_floodRet_Density, []]
    type_lst = ["", "", "", "", "", "Text", "", "Text", "", "Text"]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, type_lst)

    #cleanup
    #arcpy.Delete_management(flood_areaD_clip_single)
    #arcpy.Delete_management(flood_areaD_clip)
    #arcpy.Delete_management(str(flood_areaD))
    #arcpy.Delete_management(flood_areaC)
    #arcpy.Delete_management(flood_areaB)
    #arcpy.Delete_management(assets)
    arcpy.Delete_management("flood_zone_lyr")
    arcpy.Delete_management("flood_zone_down_lyr")
    arcpy.Delete_management("catchment_lyr")
    arcpy.Delete_management("polyLyr")
    arcpy.Delete_management("buffer_lyr")
                                       
    message("Flood Module Complete")
    start1=exec_time(start1, "full flood module")
    
##############################
#############VIEWS############
def View_MODULE(PARAMS):
    start = time.clock() #start the clock
    start1 = time.clock() #start the clock

    addresses, popRast = PARAMS[0], PARAMS[1]
    trails, roads = PARAMS[2], PARAMS[3]
    wetlandsOri = PARAMS[4]
    landuse = PARAMS[5]
    field, fieldLst = PARAMS[6], PARAMS[7]
    outTbl = PARAMS[8]

    path = os.path.dirname(outTbl) + os.sep
    ext = arcpy.Describe(outTbl).extension

    #set variables
    VA = path + "int_ViewArea" #naming convention for view intermediates
    view_50, view_100 = VA + "_50" + ext, VA + "_100" + ext #50 and 100m buffers
    view_100_int =  VA + "_100int" + ext
    view_200 = VA + "_200" + ext #200m buffer

    wetlands_dis = path + "wetland_dis" + ext #wetlands dissolved

    #create buffers 
    arcpy.Buffer_analysis(outTbl, view_50, "50 Meters") #buffer each site by 50-m
    buffer_donut(view_50, view_100, [50], "Meters") #distance past original buffer

    #calculate number benefitting in buffers
    if addresses is not None: #address based method
        lst_view_50 = buffer_contains(view_50, addresses)
        lst_view_100 = buffer_contains(view_100, addresses)
        start=exec_time(start, "scenic views analysis: 3.2 How Many Benefit? -analysis using addresses")
        #cleanup
        arcpy.Delete_management(view_50)
        arcpy.Delete_management(view_100)
        
    elif popRaster is not None: #population based method
        lst_view_50 = buffer_population(view_50, popRaster)
        lst_view_100 = buffer_population(view_100, popRaster)
        start=exec_time(start, "scenic views analysis: 3.2 How Many Benefit? - analysis using a population Raster")
        
    lst_view_score = view_score(lst_view_50, lst_view_100) #calculate weighted scores

    #generate a complete 100m buffer and determines if trails or roads cross through buffer
    arcpy.Buffer_analysis(outTbl, view_100_int, "100 Meters")
    rteLst = []

    if trails is not None:
        trails = checkSpatialReference(outTbl, trails) #check projections
        lst_view_trails_100 = buffer_contains(view_100_int, trails) #trails in buffer?
        if roads is not None:
            roads = checkSpatialReference(outTbl, roads) #check projections
            lst_view_roads_100 = buffer_contains(view_100_int, roads) #roads in buffer?
            i=0
            for item in lst_view_trails_100:
                if (lst_view_trails_100[i] == 0) and (lst_view_roads_100[i] == 0):
                    rteLst.append("NO")
                    i+=1
                else:
                    rteLst.append("YES")
                    i+=1
        else:
            rteLst = quant_to_qual_lst(lst_view_trails_100)   
    elif roads is not None:
        roads = checkSpatialReference(outTbl, roads) #check projections
        lst_view_roads_100 = buffer_contains(view_100_int, roads) #roads in buffer?
        rteLst = quant_to_qual_lst(lst_view_roads_100)
    else:
        message("No roads or trails specified")
    start=exec_time(start, "scenic views analysis: 3.2 How many benefit")

    #VIEW_MODULE3: Substitutes/Scarcity
    message("Scenic Views - 3.B Scarcity")
    if wetlandsOri is not None: 
    #make a 200m buffer that doesn't include the site
        arcpy.MultipleRingBuffer_analysis(outTbl, view_200, 200, "Meters", "Distance", "NONE", "OUTSIDE_ONLY")

    #FIX next line, cannot create output wetlands_dis (L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Test_Results\wetlands_dis.shp)#may require lyr input
        arcpy.Dissolve_management(wetlandsOri, wetlands_dis) #Dissolve wetlands fields
        wetlandsOri = wetlands_dis
        #wetlands in 200m
        lst_view_Density = percent_cover(wetlandsOri, view_200)
    else:
        message("No existing wetlands input specified")
        lst_view_Density = []
    start=exec_time(start, "scenic views analysis: 3.3B Scarcity")

    #VIEW_MODULE4: complements
    #PARAMS[landUse, fieldLst, field]
    message("Scenic Views - 3.C Complements")

    if landuse is not None:
        arcpy.MakeFeatureLayer_management(landuse, "lyr")
        whereClause = selectStr_by_list(field, fieldLst) #construct query from field list
        message(whereClause)
        arcpy.SelectLayerByAttribute_management("lyr", "NEW_SELECTION", whereClause) #reduce to desired LU
        landUse2 = os.path.splitext(outTbl)[0] + "_comp" + ext
        arcpy.Dissolve_management("lyr", landUse2, field) #reduce to unique

        #number of unique LU in LU list which intersect each buffer
        lst_comp = buffer_contains(view_200, landUse2)
        start=exec_time(start, "scenic views analysis: 3.3C Complements")
    else:
        message("No land use input specified")
        lst_comp = []

    #FINAL STEP: move results to results file
    fields_lst = ["V_2_50", "V_2_100", "V_2_score", "V_2_boo",
                  "V_3A_boo", "V_3B_scar", "V_3C_comp", "V_3D_boo"]
    list_lst = [lst_view_50, lst_view_100, lst_view_score, rteLst,
                [], lst_view_Density, lst_comp, []]
    type_lst = ["", "", "", "Text", "Text", "", "", "Text"]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, type_lst)

    #cleanup FC, then lyrs
    #arcpy.Delete_management(100int
    #arcpy.Delete_management(200sp
    #arcpy.Delete_management(wetland_dis?
    #arcpy.Delete_management("")

    message("Scenic View Module Complete")
    start1=exec_time(start1, "full view module")
    #return?
##############################
############ENV EDU###########
def Edu_MODULE(PARAMS):
    start = time.clock() #start the clock
    start1 = time.clock() #start the clock

    edu_inst = PARAMS[0]
    wetlandsOri = PARAMS[1]
    outTbl = PARAMS[2]

    path = os.path.dirname(outTbl) + os.sep
    ext = arcpy.Describe(outTbl).extension

    #set variables
    eduArea = path + "eduArea" + ext
    edu_2 = path + "edu_2" + ext #buffer 1/2 mile

    #3.2 - NUMBER WHO BENEFIT 
    if edu_inst is not None:
        edu_inst = checkSpatialReference(outTbl, edu_inst) #check spatial ref
        arcpy.Buffer_analysis(outTbl , eduArea, "0.25 Miles") #buffer each site by 0.25 miles
        lst_edu_cnt = buffer_contains(eduArea, edu_inst) #list how many schools in buffer
    else:
        message("No educational institutions specified")
        lst_edu_cnt = []
    start=exec_time(start, "Environmental Education analysis - 3.2 How Many benefit (educational institutions)")

    #3.3.B - Scarcity
    if wetlandsOri is not None:
        arcpy.Buffer_analysis(outTbl, edu_2, "0.5 Miles") #not a circle
        lst_edu_Density = percent_cover(wetlandsOri, edu_2) #analysis for scarcity
    else:
        message("No pre-existing wetlands specified to determine scarcity")
        lst_edu_Density = []
    start=exec_time(start, "Environmental Education analysis - 3.3B Scarcity (existing wetlands in 0.5 miles)")

    #Double fields to results table
    fields_lst = ["EE_2_cnt", "EE_3A_boo", "EE_3B_sca", "EE_3C_boo", "EE_3D_boo"]
    list_lst = [lst_edu_cnt, [], lst_edu_Density, [], []]
    type_lst = ["", "Text", "", "Text", "Text"]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, type_lst)

    #cleanup FC, then lyrs
    #arcpy.Delete_management(eduArea
    #arcpy.Delete_management(eduArea_2?
    #arcpy.Delete_management(edu_2
    #arcpy.Delete_management("")

    message("Environmental Education Module Complete")
    start1=exec_time(start1, "full Environmental Education module")
    
##############################
##############REC#############
def Rec_MODULE(PARAMS):
    start = time.clock() #start the clock

    addresses, popRast = PARAMS[0], PARAMS[1]
    trails, bus_Stp = PARAMS[2], PARAMS[3]
    wetlandsOri = PARAMS[4]
    landuse = PARAMS[5]
    field, fieldLst = PARAMS[6], PARAMS[7]
    outTbl = PARAMS[8]

    path = os.path.dirname(outTbl) + os.sep
    ext = arcpy.Describe(outTbl).extension

    #set variables
    recArea = path + "recArea"
    #buffer names
    rec_500m, rec_1000m, rec_10000m= recArea + "_03mi" + ext, recArea + "_05mi" + ext, recArea + "_6mi" + ext
    #scarcity buffer names
    rec_06, rec_1, rec12 = recArea + "_Add_06mi" + ext, recArea + "_Add_1mi" + ext, recArea + "_Add_12mi" + ext
    #dissolved landuse
    landuseTEMP = path + "landuse_temp" + ext

    #3.2 - NUMBER WHO BENEFIT     
    #3.2 - A: buffer each site by 500m, 1km, and 10km
    arcpy.Buffer_analysis(outTbl , rec_500m, "0.333333 Miles")
    buffer_donut(rec_500m, rec_1000m, [0.166667], "Miles")
    buffer_donut(rec_1000m , rec_10000m, [5.666667], "Miles")

    #3.2 - B: overlay population
    if addresses is not None: #address based method
        lst_rec_cnt_03 = buffer_contains(rec_500m, addresses)
        lst_rec_cnt_05 = buffer_contains(rec_1000m, addresses)
        lst_rec_cnt_6 = buffer_contains(rec_10000m, addresses)

        start=exec_time(start, "calculating number of addresses receiving recreation benefits (addresses in buffers)")

    elif popRast is not None: #check for population raster
        lst_rec_cnt_03 = buffer_population(rec_500m, popRast)
        lst_rec_cnt_05 = buffer_population(rec_1000m, popRast)
        lst_rec_cnt_6 = buffer_population(rec_10000m, popRast)

        start=exec_time(start, "calculating population receiving recreation benefits (raster population in buffer)")
    else: #this should never happen
        message("THIS SHOULDN'T HAPPEN...")
        lst_rec_cnt_03 = []
        lst_rec_cnt_05 = []
        lst_rec_cnt_6 = []

    #3.2 - C: overlay trails
    rteLst_rec_trails = []
    if trails is not None:
        lst_rec_trails = buffer_contains(rec_500m, trails) #bike trails in 500m
        rteLst_rec_trails = quant_to_qual_lst(lst_rec_trails) #if there are = YES
    else:
        message("No trails specified for determining if there are bike paths within 1/3 mi of site (R_2_03_tb)")
        lst_rec_trails = []
        rteLst_rec_trails = []
        
    #3.2 - C2: overlay bus stops
    rteLst_rec_bus = []
    if bus_Stp is not None:
        bus_Stp = checkSpatialReference(outTbl, bus_Stp) #check projections
        lst_rec_bus = buffer_contains(rec_500m, bus_Stp) #bus stops in 500m
        rteLst_rec_bus = quant_to_qual_lst(lst_rec_bus) #if there are = YES
    else:
        message("No bus stops specified for determining if there are bus stops within 1/3 mi of site (R_2_03_bb)")
        lst_rec_bus = []
        rteLst_rec_bus = []

    start=exec_time(start, "Recreation Benefits analysis - 3.2 How Many benefit")

    #3.3.A SERVICE QUALITY - Total area of green space around site ("R_3A_acr")
    lst_green_neighbor = []
    if landuse is not None:
        #reduce to desired LU
        arcpy.MakeFeatureLayer_management(landuse, "lyr")
        whereClause = selectStr_by_list(field, fieldLst)
        arcpy.SelectLayerByAttribute_management("lyr", "NEW_SELECTION", whereClause)
        arcpy.Dissolve_management("lyr", landuseTEMP, "", "", "SINGLE_PART")
        #make into selectable layer    
        arcpy.MakeFeatureLayer_management(landuseTEMP, "greenSpace_lyr")

        with arcpy.da.SearchCursor(outTbl, ["SHAPE@"]) as cursor:
            for site in cursor: #for each site
                var = Decimal(site[0].getArea("PLANAR", "ACRES")) #start with the site area
                #select green space that intersects the site
                arcpy.SelectLayerByLocation_management("greenSpace_lyr", "INTERSECT", site[0])
                with arcpy.da.SearchCursor("greenSpace_lyr", ["SHAPE@"]) as cursor2:
                    for row in cursor2:
                        #area of greenspace
                        areaGreen = Decimal(row[0].getArea("PLANAR", "ACRES"))
                        #part of greenspace already in site
                        overlap = site[0].intersect(row[0], 4)
                        #area of greenspace already in site
                        interArea = Decimal(overlap.getArea("PLANAR", "ACRES"))
                        #add area of greenspace - overlap to site and previous rows
                        var += areaGreen - interArea
                lst_green_neighbor.append(var)
    else:
        message("No landuse specified for determining area of green space around site (R_3A_acr)")
        
    start=exec_time(start, "Recreation benefits analysis: 3.3.A Service Quality")

    #3.3.B SCARCITY - green space within 2/3 mi, 1 mi and 12 mi of site
    if landuse is not None or wetlandsOri is not None:
        #sub are greenspace or wetlands?
        if landuse is not None:
            subs = landuseTEMP
        else:
            if wetlandsOri is not None:
                subs = wetlandsOri
                message("No landuse input specified, existing wetlands used for scarcity instead")

        #buffer each site by double original buffer
        arcpy.Buffer_analysis(outTbl, rec_06, "0.666666 Miles")
        arcpy.Buffer_analysis(outTbl, rec_1, "1 Miles")
        arcpy.Buffer_analysis(outTbl, rec12, "12 Miles")
        #overlay buffers with substitutes
        lst_rec_06_Density = percent_cover(subs, rec_06)
        lst_rec_1_Density = percent_cover(subs, rec_1)
        lst_rec_12_Density = percent_cover(subs, rec12)
    else:
        message("No substitutes (landuse or existing wetlands) inputs specified for recreation benefits.")
        lst_rec_06_Density = []
        lst_rec_1_Density = []
        lst_rec_12_Density = []
    start=exec_time(start, "Recreation analysis: 3.3B Scarcity")

    #Add results from lists
    fields_lst = ["R_2_03", "R_2_03_tb", "R_2_03_bb", "R_2_05", "R_2_6", "R_3A_acr", "R_3B_sc06", "R_3B_sc1", "R_3B_sc12", "R_3C_boo", "R_3D_boo"]
    list_lst = [lst_rec_cnt_03, rteLst_rec_trails, rteLst_rec_bus, lst_rec_cnt_05, lst_rec_cnt_6, lst_green_neighbor, lst_rec_06_Density, lst_rec_1_Density, lst_rec_12_Density, [], []]
    type_lst = ["", "Text", "Text", "", "", "", "", "", "", "Text", "Text"]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, type_lst)

    #cleanup FC, then lyrs
    #arcpy.Delete_management(eduArea

    message("Recreation benefits analysis complete.")
    
##############################
#############BIRD#############
def Bird_MODULE(PARAMS):
    start = time.clock() #start the clock

    addresses, popRast = PARAMS[0], PARAMS[1]
    trails, roads = PARAMS[2], PARAMS[3]
    outTbl = PARAMS[4]

    path = os.path.dirname(outTbl) + os.sep
    ext = arcpy.Describe(outTbl).extension

    #set variables
    birdArea = path + "birdArea" + ext

    #3.2 - NUMBER WHO BENEFIT
    arcpy.Buffer_analysis(outTbl , birdArea, "0.2 Miles") #buffer each site by 0.2 miles
    if addresses is not None:
        lst_bird_cnt = buffer_contains(birdArea, addresses)
        start=exec_time(start, "bird watching analysis: 3.2 How Many Benefit? - analysis using addresses")
    elif popRaster is not None:
        lst_bird_cnt = buffer_population(birdArea, popRaster)
        start=exec_time(start, "bird watching analysis: 3.2 How Many Benefit? - analysis using a population Raster")

    #3.2 - are there roads or trails that could see birds on the site?
    rteLstBird = []
    if trails is not None:
        lst_bird_trails = buffer_contains(birdArea, trails)
        if roads is not None:
            lst_bird_roads = buffer_contains(birdArea, roads)
            i=0
            for item in lst_bird_trails:
                if (lst_bird_trails[i] == 0) or (lst_bird_roads[i] == 0):
                    rteLstBird.append("NO")
                    i+=1
                else:
                    rteLstBird.append("YES")
                    i+=1       
        else:
            rteLstBird = quant_to_qual_lst(lst_bird_trails)  
    elif roads is not None:
        lst_bird_roads = buffer_contains(birdArea, roads)
        rteLstBird = quant_to_qual_lst(lst_bird_roads)
    else:
        message("No trails or roads specified to determine if birds at the site will be visible from these")

    #Add results from lists
    fields_lst = ["B_2_cnt", "B_2_boo", "B_3A_boo", "B_3C_boo", "B_3D_boo"]
    list_lst = [lst_bird_cnt, rteLstBird, [], [], []]
    type_lst = ["", "Text", "Text", "Text", "Text"]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, type_lst)

    #cleanup FC, then lyrs
    #arcpy.Delete_management(eduArea

    message("Bird Watching benefit assessment complete.")

##############################
##########SOC_EQUITY##########
def socEq_MODULE(PARAMS):
    #start = time.clock() #start the clock

    sovi = PARAMS[0]
    field, SoVI_High = PARAMS[1], PARAMS[2]
    bufferDist = PARAMS[3]
    outTbl = PARAMS[4]

    path = os.path.dirname(outTbl) + os.sep
    ext = arcpy.Describe(outTbl).extension

    #set variables
    tempPoly = path + "SoviTemp" + ext
    buf = path + "sovi_buffer" + ext

    sovi = checkSpatialReference(outTbl, sovi) #check projection

    arcpy.Buffer_analysis(outTbl, buf, bufferDist)

    #select sovi layer by buffer
    arcpy.MakeFeatureLayer_management(sovi, "soviLyr")
    arcpy.SelectLayerByLocation_management("soviLyr", "INTERSECT", buf)

    #list all the unique values in the specified field
    fieldLst = unique_values("soviLyr", field)
    message("There are " + str(len(fieldLst)) + " unique values for " + field + ".")
    if len(fieldLst) <6: #as long as they are reasonable determine percent cover for each 
        message("Creating new fields for each...")
        #add fields for each unique in field
        for val in fieldLst:
            if val == SoVI_High:
                name = "SoVI_High"
            else:
                name = val.replace(" ", "_")[0:9]
            print name
            arcpy.AddField_management(outTbl, name, "DOUBLE", "", "", "", val, "", "", "")
            whereClause = field + " = '" + val + "'"
            arcpy.SelectLayerByAttribute_management("soviLyr", "NEW_SELECTION", whereClause)
            pct_lst = percent_cover("soviLyr", buf)
            lst_to_field(outTbl, name, pct_lst)
    else:
        message("This is too many values to create unique fields for them all, just calculating {} coverage".format(SoVI_High))
        name = "SoVI_High"
        arcpy.AddField_management(outTbl, name, "DOUBLE", "", "", "", val, "", "", "")
        whereClause = field + " = '" + val + "'"
        arcpy.SelectLayerByAttribute_management("soviLyr", "NEW_SELECTION", whereClause)
        pct_lst = percent_cover("soviLyr", buf)
        lst_to_field(outTbl, name, pct_lst)

    message("Social Equity assessment complete.")
    
##############################
#########RELIABILITY##########
def reliability_MODULE(PARAMS):
    start = time.clock() #start the clock

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

    start=exec_time(start, "Percent conserved/threatened use types calculated")

    #move results to outTbl
    fields_lst = ["Conserved", "Threatene"]
    list_lst = [pct_consLst, pct_threatLst]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, ["", ""])

    message("Reliability assessment complete.")
    
##############################
#############MAIN#############
def main(params):
    start = time.clock() #start the clock
    start1 = time.clock() #start the clock

    message("Loading Variables...")
    #params = [sites, addresses, popRast, flood, view, edu, bird, rec, socEq, rel,
    #      edu_inst, bus_stp, trails, roads, preWetlands, landUse, fieldLULC, fieldVal, SocVul, SoVI_Field,
    #      socVal, distance, Conservation, Conserve_Field, useType, outTbl]
    ck=[]
    for i in range(3, 10):
        ck.append(params[i].value)
    flood, view, edu, rec, bird = ck[0], ck[1], ck[2], ck[3], ck[4]
    socEq, rel = ck[5], ck[6]
    
    sites = params[0].valueAsText #in_gdb  + "restoration_Sites"
    addresses = params[1].valueAsText #in_gdb + "e911_14_Addresses"
    popRast = params[2].valueAsText #None
    #flood_zone = params [0] #in_gdb + "FEMA_FloodZones_clp"
    ExistingWetlands = params[14].valueAsText #in_gdb + "NWI14"
    #subs = in_gdb + "dams"
    roads = params[13].valueAsText #in_gdb + "e911Roads13q2"
    trails = params[12].valueAsText #in_gdb + "bikepath"

    landuse = params[15].valueAsText #in_gdb + "rilu0304"
    field = params[16].valueAsText #"LCLU"
    fieldLst = params[17].values #[u'161', u'162', u'410', u'430']
    
    edu_inst = params[10].valueAsText #in_gdb + "schools08"
    bus_Stp = params[11].valueAsText #in_gdb + "RIPTAstops0116"

    buff_dist = params[21].valueAsText #"2.5 Miles"

    sovi = params[18].valueAsText #in_gdb + "SoVI0610_RI"
    sovi_field = params[19].valueAsText #"SoVI0610_1"
    sovi_High = params[20].values #"High" #this is now a list...

    conserved = params[22].valueAsText #in_gdb + "LandUse2025"
    rel_field = params[23].valueAsText #"Map_Legend"
    cons_fieldLst = params[24].values #['Conservation/Limited', 'Major Parks & Open Space', 'Narragansett Indian Lands', 'Reserve', 'Water Bodies']
    #all values from rel_field not in cons_fieldLst #['Non-urban Developed', 'Prime Farmland', 'Sewered Urban Developed', 'Urban Development']
    threat_fieldLst = [x for x in unique_values(conserved, rel_field) if x not in cons_fieldLst]

    Catchment = r"C:\ArcGIS\Local_GIS\NHD_Plus\NHDPlusNationalData\NHDPlusV21_National_Seamless.gdb\NHDPlusCatchment\Catchment"
    #NHDField = params[].valueAsText#InputField = "FEATUREID" #field from feature layer
    
    outTbl = params[25].valueAsText #r"L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Test_Results\IntermediatesFinal77.gdb\Results_full"
    start1 = exec_time(start1, "loading variables")            
    message("Checking input variables...")

    #Copy restoration wetlands in for results
    arcpy.CopyFeatures_management(sites, outTbl)

    #check spatial references for inputs
    #test? all require except edu
    if addresses is not None:
        addresses = checkSpatialReference(outTbl, addresses) #check spatial ref
        message("Addresses OK")
    elif popRast is not None: #NOT YET TESTED
        popRast = checkSpatialReference(outTbl, popRast) #check projection
        message("Population Raster OK")
    else:
        arcpy.AddError("No population inputs specified")
        print("No population inputs specified")
        raise arcpy.ExecuteError
    #benefits using Existing Wetlands
    if flood == True or view == True or edu == True: #benefits requiring existing wetlands
        if ExistingWetlands is not None: #if the dataset is specified
            OriWetlands = checkSpatialReference(outTbl, ExistingWetlands) #check spatial ref
            message("Existing wetlands OK")
        else:
            message("Existings wetlands input not specified, some fields will be left blank for selected benefits.")
    #benefits using landuse       
    if view == True or rec == True:
        if landuse is not None:
            landuse = checkSpatialReference(outTbl, landuse) #check spatial ref
            message("Landuse polygons OK")
        else:
            message("Landuse input not specified, some fields will be left blank for selected benefits.")
    #trails
    if view == True or bird == True or rec == True:
        if roads is not None:
            roads = checkSpatialReference(outTbl, roads) #check spatial ref
            message("Roads input OK")
        else:
            message("Roads input not specified, some fields will be left blank for selected benefits.")
    #roads
        if trails is not None:
            trails = checkSpatialReference(outTbl, trails) #check spatial ref
            message("Trails input OK")
        else:
            message("Trails input not specified, some fields will be left blank for selected benefits.")

    #message/time:
    start1 = exec_time(start1, "verify inputs")
    message("Running selected benefit modules...")

    #run modules based on checkboxes
    if flood == True:
        Flood_PARAMS = [addresses, popRast, flood_zone, OriWetlands, subs, Catchment, InputField, outTbl]
        FR_MODULE(Flood_PARAMS)
        start1 = exec_time(start1, "Flood Risk benefit assessment")
    else: #create and set all fields to none?
        message("Flood Risk Benefits not assessed")
        
    if view == True:
        View_PARAMS = [addresses, popRast, trails, roads, OriWetlands, landuse, field, fieldLst, outTbl]
        View_MODULE(View_PARAMS)
        start1 = exec_time(start1, "Scenic View benefit assessment")
    else: #create and set all fields to none?
        message("Scenic View Benefits not assessed")
                
    if edu == True:
        EDU_PARAMS = [edu_inst, OriWetlands, outTbl]
        Edu_MODULE(EDU_PARAMS)
        start1 = exec_time(start1, "Environmental Education benefit assessment")
    else: #create and set all fields to none?
        message("Environmental Education Benefits not assessed")

    if rec == True:
        REC_PARAMS = [addresses, popRast, trails, bus_Stp, OriWetlands, landuse, field, fieldLst, outTbl]
        Rec_MODULE(REC_PARAMS)
        start1 = exec_time(start1, "Recreation benefit assessment")
    else: #create and set all fields to none?
        message("Recreation Benefits not assessed")
                
    if bird == True:
        Bird_PARAMS = [addresses, popRast, trails, roads, outTbl]
        Bird_MODULE(Bird_PARAMS)
        start1 = exec_time(start1, "Bird Watching benefit assessment")
    else: #create and set all fields to none?
        message("Bird Watching Benefits not assessed")

    if socEq == True:
        soc_PARAMS = [sovi, sovi_field, sovi_High, buff_dist, outTbl]
        socEq_MODULE(soc_PARAMS)
        start1 = exec_time(start1, "Social Equity assessment")
    else: #create and set all fields to none?
        message("Social Equity of Benefits not assessed")
        
    if rel == True:
        Rel_PARAMS = [conserved, rel_field, cons_fieldLst, threat_fieldLst, buff_dist, outTbl]
        reliability_MODULE(Rel_PARAMS)
        start1 = exec_time(start1, "Reliability assessment")
    else: #create and set all fields to none?
        message("Reliability of Benefits not assessed")

    start = exec_time(start, "Benefts assessment complete.")
##############################
###########TOOLBOX############
class Toolbox(object):
    def __init__(self):
        self.label = "Indicator Tools"
        self.alias = "Tier_1"
        # List of tool classes associated with this toolbox
        self.tools= [Tier_1_Indicator_Tool]

############################# 
################################
#########INDICATOR_TOOL#########       
class Tier_1_Indicator_Tool (object):
    def __init__(self):
        self.label = "Tier 1 Indicator Tools" 
        self.description = "This tool performs the Tier 1 Indicators assessment on a desired" + \
                           "set of wetlands or wetlands restoration sites."

    def getParameterInfo(self):
    #Define IN/OUT parameters
        #sites = in_gdb  + "restoration_Sites"
        sites = setParam("Restoration Site Polygons", "in_poly", "", "", "")#sites
        #addresses = in_gdb + "e911_14_Addresses"
        addresses = setParam("Address Points", "in_pnts", "", "Optional", "")#beneficiaries points
        #popRast = None
        popRast = setParam("Population Raster", "popRast", "DERasterDataset", "Optional", "")#beneficiaries raster
        #check boxes for services the user wants to assess
        #flood, view, edu, rec, bird, socEq, rel = True, True, True, True, True, True, True
        serviceLst=["Reduced Flood Risk", "Scenic Views", "Environmental Education",
                    "Bird Watching", "Recreation", "Social Equity", "Reliability"]
        flood = setParam(serviceLst[0], "flood", "GPBoolean", "Optional", "")
        view = setParam(serviceLst[1], "view", "GPBoolean", "Optional", "")
        edu = setParam(serviceLst[2], "edu", "GPBoolean", "Optional", "")
        bird = setParam(serviceLst[3], "bird", "GPBoolean", "Optional", "")
        rec = setParam(serviceLst[4], "rec", "GPBoolean", "Optional", "")
        #other check boxes
        socEq = setParam(serviceLst[5], "socEq", "GPBoolean", "Optional", "")
        rel = setParam(serviceLst[6], "rel", "GPBoolean", "Optional", "")

        #special datasets (disabled initially)
        #flood_zone = in_gdb + "FEMA_FloodZones_clp"
        #flood_zone
        #subs = in_gdb + "dams"
        #dams
        #Catchment = r"C:\ArcGIS\Local_GIS\NHD_Plus\NHDPlusNationalData\NHDPlusV21_National_Seamless.gdb\NHDPlusCatchment\Catchment"
        #set default
        #Catchment =
        #InputField = "FEATUREID" #field from feature layer
        #NHD_field = 
        #edu_inst = in_gdb + "schools08"
        edu_inst = setParam("Educational Institution Points", "edu_inst", "", "Optional", "")
        edu_inst.enabled = False
        #bus_Stp = in_gdb + "RIPTAstops0116"
        bus_stp = setParam("Bus Stop Points", "bus_stp", "", "Optional", "") #could it accomodate lines too?
        bus_stp.enabled = False
        #trails = in_gdb + "bikepath"
        trails = setParam("Trails (hiking, biking, etc.)", "trails", "", "Optional", "")
        #roads = in_gdb + "e911Roads13q2"
        roads = setParam("Roads (streets, highways, etc.)", "roads", "", "Optional", "")
        #pre-existing wetlands #ExistingWetlands = in_gdb + "NWI14"
        preWetlands = setParam("Wetland Polygons", "in_wet", "", "Optional", "")#pre-existing wetlands

        #landuse = in_gdb + "rilu0304"
        landUse = setParam("Land use or greenspace Polygons", "land_use", "", "Optional", "")
        #field = "LCLU"
        fieldLULC = setParam("Landuse Field", "LULCFld", "Field", "Optional", "")
        #list of fields from table [430, 410, 162, 161]
        fieldVal = setParam("Greenspace Field Values", "grn_field_val", "GPVariant", "Optional", "", True)

        #sovi = in_gdb + "SoVI0610_RI"
        SocVul = setParam("SoVI", "sovi_poly", "", "Optional", "")
        #user must select 1 field to base calculation on #sovi_field = "SoVI0610_1"
        SoVI_Field = setParam("SoVI Score", "SoVI_ScoreFld","Field", "Optional", "")
        #sovi_High = "High"
        socVal = setParam("Vulnerable Field Values", "soc_field_val", "GPString", "Optional", "", True)
        
        #distance beneficiaries travel #buff_dist = "2.5 Miles"
        distance = setParam("Buffer Distance", "bufferUnits", "GPLinearUnit", "Optional", "")

        #conserved = in_gdb + "LandUse2025"
        Conservation = setParam("Conservation lands", "cons_poly", "", "Optional", "")
        #rel_field = "Map_Legend"
        Conserve_Field = setParam("Conservation Field", "Conservation_Field", "Field", "Optional", "")
        #user must select 1 field to base calculation on
        #cons_fieldLst = ['Conservation/Limited', 'Major Parks & Open Space', 'Narragansett Indian Lands', 'Reserve', 'Water Bodies']
        useType = setParam("Conservation Types", "Conservation_Type", "GPString", "Optional", "", True)

        #distance beneficiaries travel
        #distance2 = setParam("Buffer Distance", "bufferUnits", "GPLinearUnit", "", "")
                
        #outputs
        #outTbl = r"L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Test_Results\IntermediatesFinal77.gdb\Results_full"
        outTbl = setParam("Output", "outTable", "DETable", "", "Output")
        #could code this as a folder or updated wetland shp instead, info table?
        #could be made optional with an over write default

        #report = setParam("Report (optional)", "report", "DEMapDocument", "Optional", "Output")

        #set drop downs to be disabled initially
        disableParamLst([fieldLULC, fieldVal, SocVul, SoVI_Field, socVal, Conservation, Conserve_Field, useType])

        #dependencies
	#Set the FieldsList to be filtered by the list from the feature dataset
        fieldLULC.parameterDependencies = [landUse.name]
        fieldVal.parameterDependencies = [fieldLULC.name]
        fieldVal.filter.type = 'ValueList'
        
        SoVI_Field.parameterDependencies = [SocVul.name]
        socVal.parameterDependencies = [SoVI_Field.name]
        socVal.filter.type = 'ValueList'
        
        Conserve_Field.parameterDependencies = [Conservation.name]
        useType.parameterDependencies = [Conserve_Field.name]
        useType.filter.type = 'ValueList'
        
        #defaults
        ###SoVI_Field.defaultEnvironmentName = "SoVI0610_1"
        distance.parameterDependencies = [sites.name] #units based on spRef
        #distance2.parameterDependencies = [RestorationSites.name]

        params = [sites, addresses, popRast, flood, view, edu, bird, rec, socEq, rel,
                  edu_inst, bus_stp, trails, roads, preWetlands, landUse, fieldLULC, fieldVal, SocVul, SoVI_Field,
                  socVal, distance, Conservation, Conserve_Field, useType, outTbl]

        return params

    def isLicensed(self):
        return True
    def updateParameters(self, params):
        #Modify the values and properties of parameters before internal validation is performed.
        #Called whenever a parameter is changed.
        #only take points or raster
        if params[1].value != None:
            params[2].enabled = False
        else:
            params[2].enabled = True
        if params[2].value != None:
            params[1].enabled = False
        else:
            params[1].enabled = True
        #edu only inputs (edu_inst)
        if params[5].value == True:
            params[10].enabled = True
        else:
            params[10].enabled = False
        #rec only inputs (bus_stp)
        if params[7].value == True:
            params[11].enabled = True
        else:
            params[11].enabled = False
        #landuse required benefits (view & rec)
        if params[4].value == True or params[7].value == True:
            params[15].enabled = True
        else:
            params[15].enabled = False
        if params[15].altered:
            params[16].enabled = True
        if params[16].altered:
            in_poly = params[15].valueAsText
            TypeField = params[16].valueAsText
            params[17].enabled = True
            params[17].filter.list = unique_values(in_poly, TypeField)
        #social vulnerability & reliability
        if params[8].value == True or params[9].value ==True: #soc or rel
            params[21].enabled = True #distance
        else:
            params[21].enabled = False
        #social vulnerability inputs    
        if params[8].value == True:
            params[18].enabled = True #SocVul
        if params[18].altered:
            params[19].enabled = True
        if params[19].altered: #socVul_field
            in_poly = params[18].valueAsText
            TypeField = params[19].valueAsText
            params[20].enabled = True
            params[20].filter.list = unique_values(in_poly, TypeField)
        #reliability inputs
        if params[9].value == True:
            params[22].enabled = True #Conservation
        if params[22].altered:
            params[23].enabled = True #Conserve_Field
        if params[23].altered: 
            in_poly = params[22].valueAsText
            TypeField = params[23].valueAsText
            params[24].enabled = True
            params[24].filter.list = unique_values(in_poly, TypeField)
        return

    def updateMessages(self, params):
        """This method is called after internal validation."""
        #params[].setErrorMessage('') #use to validate inputs
        return
    
    def execute(self, params, messages):
        main(params)
