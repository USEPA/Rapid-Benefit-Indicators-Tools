"""
# Name: Tier 1 Rapid Benefit Indicator Assessment- Flood Module
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
    #add test for equal length of lists?
    #if len(lst_50) != len(lst_100):
    #   arcpy.AddMessage("Error in view score function, unequal list lengths")
    #   break
    for item in lst_50:
       lst.append(lst_50[i] * 0.7 + lst_100[i] * 0.3)
       i+=1
    return lst

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

"""Generic message
Purpose: prints string message in py or pyt"""
def message(string):
    arcpy.AddMessage(string)
    print(string)

"""Custom Error Message
Purpose: error message shortcut"""
def error_message(text):
    arcpy.AddMessage("ERROR occured while " + text + ".")

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

"""Donut Buffer
Purpose: takes inside buffer and creates outside buffers. Ensures ORIG_FID is correct."""
#Function Notes: there can be multiple buffer distances, but must be list
def buffer_donut(FC, outFC, buf, units):
    FCsort = FC[:-4] + "_2.shp" #the buffers should all be in the outTbl folder
    arcpy.Sort_management(FC, FCsort, [["ORIG_FID", "ASCENDING"]]) #sort FC by ORGI_FID
    arcpy.MultipleRingBuffer_analysis(FCsort, outFC, buf, units, "Distance", "NONE", "OUTSIDE_ONLY") #new buffer
    arcpy.Delete_management(FCsort) #Delete intermediate FC
    return outFC

"""Buffer Contains
Purpose: returns number of points in buffer as list"""
#Function Notes:
#Example: lst = buffer_contains(view_50, addresses)
def buffer_contains(poly, pnts):
    lst = []
    #poly_out = poly[:-4] + "_2.shp" #check to be sure this is created in outTbl folder
    poly_out = poly + "_2" #if this is created in outTbl GDB
    arcpy.SpatialJoin_analysis(poly, pnts, poly_out, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "INTERSECT", "", "")
    #lst = field_to_lst(poly_out, ["ORIG_FID", "Join_Count"])
    #sort on poly shouldn't be needed, I'm wondering why I did this. Sort on pnts would be strange if not bad
    lst = field_to_lst(poly_out, ["OID@", "Join_Count"]) #polygon OID token (works for .shp or FC)
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
        exp += '"' + field + '" = ' + str(item) + " OR "
    return (exp[:-4])

"""Where clause from list
Purpose: Create where clause using a list of fields"""
def clause_from_list(fieldLst, field):
    start_qry = '"' + field + '" = '
    end_qry = ' OR '
    qry = ''
    for item in fieldLst:
        qry_item = start_qry + str(item) + end_qry
        qry = qry + qry_item
    whereClause = qry[:-4]
    return whereClause

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

"""Unique Values
Purpose: returns a sorted list of unique values"""
#Function Notes: used to find unique field values in table column
def unique_values(table, field):
    with arcpy.da.SearchCursor(table, [field]) as cursor:
        return sorted({row[0] for row in cursor if row[0]})

###########MODULES############
##########FLOOD RISK##########
def FR_MODULE(PARAMS):
    start = time.clock() #start the clock

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
            message("Determine catchments downstream for row {}, of {}".format(clip_rows, site_cnt))

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
        lst_subs_cnt_boolean = []
        for item in lst_subs_cnt:
              if item >0:
                  lst_subs_cnt_boolean.append("YES")
              else:
                  lst_subs_cnt_boolean.append("NO")

        start = exec_time (start, "Flood Risk 3.3.B Scarcity (substitutes) analysis")
            
    #3.3.B: SCARCITY
    if ExistingWetlands is not None:
        message("Estimating area of wetlands within 2.5 miles in both directions (5 miles total) of restoration site...")
        ExistingWetlands = checkSpatialReference(outTbl, ExistingWetlands) #check spatial ref
        #lst_floodRet_Density = percent_cover(ExistingWetlands, flood_areaC) #analysis for scarcity
    #CONCERN- the above only looks at wetlands in the flood areas within 2.5 miles, the below does entire buffer.
    #Should this be restricted to upstream/downstream?
        lst_floodRet_Density = percent_cover(ExistingWetlands, flood_areaB) #analysis for scarcity
    #CONCERN: THIS IS WICKED SLOW
        start = exec_time (start, "Flood Risk 3.3.B Scarcity analysis")
                                              
    #FINAL STEP: move results to results file
    fields_lst = ["FR_2_cnt", "FR_zPct", "FR_zDown", "FR_zDoPct", "FR_3A_acr", "FR_sub", "FR_3B_sca"]
    list_lst = [lst_flood_cnt, lst_floodzoneArea_pct, lst_floodzoneD, lst_floodzoneD_pct, siteAreaLst, lst_subs_cnt, lst_floodRet_Density]

    i = 0
    for item in fields_lst
            arcpy.AddField_management(outTbl, item, "Double")
            lst_to_field(outTbl, item, list_lst[i])

    #subs at each site Y/N = lst_subs_cnt_boolean
    arcpy.AddField_management(outTbl, "FR_3B_boo", "Text")
    lst_to_field(outTbl, "FR_3B_boo", lst_subs_cnt_boolean)

    #cleanup
    arcpy.Delete_management(flood_areaD_clip_single)
    arcpy.Delete_management(flood_areaD_clip)
    arcpy.Delete_management(str(flood_areaD))
    arcpy.Delete_management(flood_areaC)
    arcpy.Delete_management(flood_areaB)
    arcpy.Delete_management(assets)
                                       
    message("Flood Module Complete")
    start=exec_time(start, "flood module")
##############################
#############VIEWS############
def View_MODULE(PARAMS):
    start = time.clock() #start the clock

    addresses, popRast = PARAMS[0], PARAMS[1]
    trails, roads = PARAMS[2], PARAMS[3]
    wetlandsOri = PARAMS[4]
    outTbl = PARAMS[5]

    path = os.path.dirname(outTbl) + os.sep
    ext = arcpy.Describe(outTbl).extension

    wetlandsOri = checkSpatialReference(outTbl, wetlandsOri) #check projections
    landUse = checkSpatialReference(outTbl, landUse) #check projections

    #set variables
    VA = path + "int_ViewArea" #naming convention for view intermediates
    view_50, view_100 = VA + "_50" + ext, VA + "_100" + ext #50 and 100m buffers
    view_100_int =  VA + "_100int" + ext
    view_200 = VA + "_200sp" + ext #200m buffer

    wetlands_dis = path + "wetland_dis" +ext #wetlands dissolved
    
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

#create buffers around the site and determines if trails or roads cross through those buffers
    rteLst = []
    #generate a complete 100m buffer
    arcpy.Buffer_analysis(outTbl, view_100_int, "100 Meters")

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
            for item in lst_view_trails_100:
                if (item == 0):
                    rteLst.append("NO")
                else:
                    rteLst.append("YES")     
    elif roads is not None:
        roads = checkSpatialReference(outTbl, roads) #check projections
        lst_view_roads_100 = buffer_contains(view_100_int, roads) #roads in buffer?

    for i in lst_view_roads_100:
        if (i == 0):
            rteLst.append("NO")
        else:
            rteLst.append("YES")

#VIEW_MODULE3: Substitutes/Scarcity
    message("Scenic Views - 3.B Scarcity
    #FIX next line, cannot create output wetlands_dis (L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Test_Results\wetlands_dis.shp)
    arcpy.Dissolve_management(wetlandsOri, wetlands_dis) #Dissolve wetlands fields
    wetlandsOri = wetlands_dis

    #make a 200m buffer that doesn't include the site
    arcpy.MultipleRingBuffer_analysis(outTbl, view_200, 200, "Meters", "Distance", "NONE", "OUTSIDE_ONLY")
    lst_view_Density = percent_cover(wetlandsOri, view_200) #wetlands in 200m
    start=exec_time(start, "scenic views analysis: 3.3B Scarcity")

#VIEW_MODULE4: complements
#PARAMS[landUse, fieldLst, field]
    message("Scenic Views - 3.C Complemenets")
    
    #if view_200 is None: #create buffer called view_200 if it doesn't already exist
    #    view_200 = outTbl[:-4] + "view200.shp"
    #    arcpy.MultipleRingBuffer_analysis(outTbl, view_200, 200, "Meters", "Distance", "NONE", "OUTSIDE_ONLY")

    arcpy.MakeFeatureLayer_management(landUse, "lyr")
    whereClause = clause_from_list(fieldLst, field) #construct query from field list
    arcpy.SelectLayerByAttribute_management("lyr", "NEW_SELECTION", whereClause) #reduce to desired LU
    landUse2 = outTbl[:-4] + "_comp.shp"
    arcpy.Dissolve_management("lyr", landUse2, field) #reduce to unique

    #number of unique LU in LU list which intersect each buffer
    lst_comp = buffer_contains(view_200, landUse2)
fields_lst = ["FR_2_cnt", "FR_zPct", "FR_zDown", "FR_zDoPct", "FR_3A_acr", "FR_sub", "FR_3B_sca"]
    #FINAL STEP: move results to results file
    fields_lst = ["V_2_50", "V_2_100", "V_2_score", "V_3B_scar", "V_3C_comp"]
    list_lst = [lst_view_50, lst_view_100, lst_view_score, lst_view_Density, lst_comp]

    i = 0
    for item in fields_lst
            arcpy.AddField_management(outTbl, item, "Double")
            lst_to_field(outTbl, item, list_lst[i])

    #subs at each site Y/N = lst_subs_cnt_boolean
    arcpy.AddField_management(outTbl, "SV_2_boo", "Text")
    lst_to_field(outTbl, "SV_2_boo", rteLst)
    #return 

    #arcpy.AddField_management(outTbl, "VCnt_100", "Double") #lst_view_100
    #arcpy.AddField_management(outTbl, "VCnt_50", "Double") #lst_view_50
    #arcpy.AddField_management(outTbl, "VScore", "Double") #lst_view_score
    #arcpy.AddField_management(outTbl, "V_YN_3_2", "TEXT") #rteLst
    #arcpy.AddField_management(outTbl, "Vscarcity", "Double") #lst_view_Density
    #arcpy.AddField_management(outTbl, "Vcomp_cnt", "Double") #lst_comp


##############################
############ENV EDU###########


##############################
##############REC#############


##############################
#############BIRD#############


##############################
#############MAIN#############
start = time.clock() #start the clock
#inputs gdb
in_gdb = r"L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Test_Inputs.gdb"
wetlands = in_gdb + os.sep + "restoration_Sites"
addresses = in_gdb+ os.sep + "e911_14_Addresses"
popRast = None
flood_zone = in_gdb + os.sep + "FEMA_FloodZones_clp"
ExistingWetlands = in_gdb + os.sep + "NWI14"
subs = in_gdb + os.sep + "dams"
Catchment = r"C:\ArcGIS\Local_GIS\NHD_Plus\NHDPlusNationalData\NHDPlusV21_National_Seamless.gdb\NHDPlusCatchment\Catchment"
InputField = "FEATUREID" #field from feature layer
outTbl = r"L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Test_Results\Intermediates2.gdb\Results"

trails = ""
roads = ""

message("Checking input variables...")

#Copy restoration wetlands in for results
arcpy.CopyFeatures_management(wetlands, outTbl)

#check spatial references
if addresses is not None:
    addresses = checkSpatialReference(outTbl, addresses) #check spatial ref
elif popRast is not None: #NOT YET TESTED
    #check projection
else:
    arcpy.AddError("No population inputs specified")
    print("No population inputs specified")
    raise arcpy.ExecuteError

if flood == True:
    Flood_PARAMS = [addresses, popRast, flood_zone, ExistingWetlands, subs, Catchment, InputField, outTbl]
    FR_MODULE(Flood_PARAMS)
else: #create and set all fields to none?
    message("Flood Risk benefits not assessed")
    
if view == True:
    View_PARAMS = [addresses, popRast, trails, roads, ExistingWetlands, outTbl]
    View_MODULE(View_PARMAS)
else: #create and set all fields to none?
    message("Scenic View Benefits not assessed")
            
if edu == True:
    EDU_PARAMS = []
    Edu_MODULE(EDU_PARAMS)
else: #create and set all fields to none?
    message("Environmental Education Benefits not assessed")

if REC == True:
    REC_PARAMS = []
    Rec_MODULE(REC_PARAMS)
else: #create and set all fields to none?
    message("Recreation Benefits not assessed")
            
if Bird == True:
    Bird_PARAMS = []
    Bird_MODULE(Bird_PARAMS)
else: #create and set all fields to none?
    message("Bird Watching Benefits not assessed")
