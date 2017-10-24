"""
# Name: Rapid Benefit Indicator Assessment - Flood Module
# Purpose: Download NHDPlus using sites
# Author: Justin Bousquin
# bousquin.justin@epa.gov
#
# Version Notes:
# Developed in ArcGIS 10.3
#0.1.0 converted from .pyt
"""
###########IMPORTS###########
import os
import arcpy
from decimal import Decimal
from itertools import chain
from collections import deque, defaultdict

arcpy.env.parallelProcessingFactor = "100%" #use all available resources
arcpy.env.overwriteOutput = True #overwrite existing files

##########USER INPUTS#########
addresses = ""
popRast = ""
flood_zone = ""
OriWetlands = ""
subs = ""
Catchment = ""
InputField = ""
relTbl = ""
outTbl = ""
###############################
#inputs gdb
#in_gdb = r"~\Code\Python\Python_Addins\Tier1_pyt\Test_Inputs.gdb"
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
#Catchment = r"~\NHD_Plus\NHDPlusNationalData\NHDPlusV21_National_Seamless.gdb\NHDPlusCatchment\Catchment"
#InputField = "FEATUREID" #field from feature layer
#UpDown = "Downstream" #alt = "Upstream"
#output table (not the gdb it is in)
#outTbl = params[6].valueAsText
#outTbl = r"~\Code\Python\Python_Addins\Tier1_pyt\Test_Results\Intermediates2.gdb\Results"
#NHD_path = arcpy.Describe(Catchment).Path
#Flow = NHD_path.replace('\\NHDPlusCatchment','\\PlusFlow')
##############################
###########FUNCTIONS##########
def exec_time(start, task):
    """Global Timer
    Purpose: Returns the time since the last function assignment,
             and a task message.
    Notes: used during testing to compare efficiency of each step
    """
    end = time.clock()
    comp_time = time.strftime("%H:%M:%S", time.gmtime(end-start))
    message("Run time for " + task + ": " + str(comp_time))
    start = time.clock()
    return start

def message(string, severity = 0):
    """Generic message
    Purpose: prints string message in py or pyt.
    """
    print(string)
    if severity == 1:
        arcpy.AddWarning(string)
    else:
        arcpy.AddMessage(string)

def dec(x):
    """decimal.Decimal"""
    return Decimal(x)


def get_ext(FC):
    """get extension"""
    ext = arcpy.Describe(FC).extension
    if len(ext) > 0:
        ext = "." + ext
    return ext


def del_exists(item):
    """ Delete if exists
    Purpose: if a file exists it is deleted and noted in a message.
    """
    if arcpy.Exists(item):
        try:
            arcpy.Delete_management(item)
            message("'{}' already exists and will be replaced.".format(item))
        except:
            message("'{}' exists but could not be deleted.".format(item))


def field_exists(table, field):
    """Check if field exists in table
    Notes: return true/false
    """
    fieldList = [f.name for f in arcpy.ListFields(table)]
    return True if field in fieldList else False


def find_ID(table):
    """return an ID field where orig_ID > ORIG_FID > OID@
    """
    if field_exists(table, "orig_ID"):
        return "orig_ID"
    elif field_exists(table, "ORIG_FID"):
        return "ORIG_FID"
    else:
        return arcpy.Describe(table).OIDFieldName 


def checkSpatialReference(match_dataset, in_dataset, output=None):
    """Check Spatial Reference
    Purpose: Checks that in_dataset spatial reference name matches
             match_dataset and re-projects if not.
    Inputs: \n match_dataset(Feature Class/Feature Layer/Feature Dataset):
            The dataset with the spatial reference that will be matched.
            in_dataset (Feature Class/Feature Layer/Feature Dataset):
            The dataset that will be projected if it does not match.
    output: \n Path, filename and extension for projected in_dataset
            Defaults to match_dataset location.
    Return: \n Either the original FC or the projected 'output' is returned.
    """
    matchSR = arcpy.Describe(match_dataset).spatialReference
    otherSR = arcpy.Describe(in_dataset).spatialReference
    if matchSR.name != otherSR.name:
        message("'{}' Spatial reference does not match.".format(in_dataset))
        try:
            if output is None:
                # Output defaults to match_dataset location
                path = os.path.dirname(match_dataset) + os.sep
                ext = get_ext(match_dataset)
                out_name = os.path.splitext(os.path.basename(in_dataset))[0]
                output = path + out_name + "_prj" + ext
            del_exists(output)  # delete if output exists
            # Project (doesn't work on Raster)
            arcpy.Project_management(in_dataset, output, matchSR)
            message("File was re-projected and saved as:\n" + output)
            return output
        except:
            message("Warning: spatial reference could not be updated.", 1)
            return in_dataset
    else:
        return in_dataset


def nhdPlus_check(catchment, joinField, relTbl, outTbl):
    """check NHD+ inputs
    Purpose: Assigns defaults and/or checks the NHD Plus inputs.
    Errors out of the flood module if an error occurs
    """
    script_dir = os.path.dirname(os.path.realpath(__file__)) + os.sep
    NHD_gdb = "NHDPlusV21" + os.sep + "NHDPlus_Downloads.gdb" + os.sep
    errMsg = "\nCheck NHD Plus inputs and download using " + "'Part - Flood Data Download' tool if necessary."
    # Check catchment file
    if catchment is None:
        catchment = script_dir + NHD_gdb + "Catchment"
    if arcpy.Exists(catchment):
        message("Catchment file found:\n{}".format(catchment))
        # Field from catchment
        if joinField is None:
            joinField = "FEATUREID"
        else:
            joinField = str(joinField)
        # Check catchment for field
        if not field_exists(catchment, joinField):
            raise Exception("'{}' field not be found in:\n{}{}".format(
                joinField, catchment, errMsg))
        else:
            message("'{}' field found in {}".format(joinField, catchment))
    else:
        raise Exception("'Catchment' file not found in:\n" + catchment + errMsg)

    # Check flow table    
    if relTbl is None:
        relTbl = script_dir + NHD_gdb + "PlusFlow"
    if arcpy.Exists(relTbl):
        message("Downstream relationships table found:\n{}".format(relTbl))
        # Check relationship table for field "FROMCOMID" & "TOCOMID"
        for targetField in ["FROMCOMID", "TOCOMID"]:
            if not field_exists(relTbl, targetField):
                raise Exception("'{}' field not found in:\n{}{}".format(
                    targetField, relTbl, errMsg))
    else:
        raise Exception("Default relationship file not found in:\n" +
                            relTbl + errMsg)
    message("All NHD Plus Inputs located")


def setNHD_dict(Flow):
    """Read in NHD Relates
    Purpose: read the upstream/downstream table to memory"""
    UpCOMs = defaultdict(list)
    DownCOMs = defaultdict(list)
    message("Gathering info on upstream / downstream relationships")
    with arcpy.da.SearchCursor(Flow, ["FROMCOMID", "TOCOMID"]) as cursor:
        for row in cursor:
            FROMCOMID = row[0]
            TOCOMID = row[1]
            if TOCOMID != 0:
                UpCOMs[TOCOMID].append(TOCOMID)
                DownCOMs[FROMCOMID].append(TOCOMID)
    return (UpCOMs, DownCOMs)


def list_downstream(lyr, field, COMs):
    """List catchments downstream of catchments in layer
    Notes: can be re-written to work for upstream
    """
    # List lyr IDs
    HUC_ID_lst = field_to_lst(lyr, field)
    # List catchments downstream of site
    downCatchments = []
    for ID in set(HUC_ID_lst):
        downCatchments.append(children(ID, COMs))
        # upCatchments.append(children(ID, UpCOMs))
        # list catchments upstream of site #alt
    # Flatten list and remove any duplicates
    downCatchments = set(list(chain.from_iterable(downCatchments)))
    return(list(downCatchments))


def selectStr_by_list(field, lst):
    """Selection Query String from list
    Purpose: return a string for a where clause from a list of field values
    """
    exp = ''
    for item in lst:
        if type(item) in [str, unicode]:  # sequence
            exp += "{} = '{}' OR ".format(field, item)
        elif type(item) == float:
            decP = len(repr(item).split(".")[1])  # decimal places
            if decP >= 15:
                exp += 'ROUND({},{}) = {} OR '.format(field, decP, repr(item))
            else:
                exp += '{} = {} OR '.format(field, repr(item))
        elif type(item) in [int, long]:  # numeric
            exp += '"{}" = {} OR '.format(field, item)
        else:
            message("'{}' in list, unknown type '{}'".format(item, type(item)))
    return (exp[:-4])


def simple_buffer(outTbl, tempName, bufferDist):
    """ Create buffer using tempName"""
    path = os.path.dirname(outTbl) + os.sep
    buf = path + tempName + get_ext(outTbl) # Set temp file name
    del_exists(buf)
    arcpy.Buffer_analysis(outTbl, buf, bufferDist)
    return buf


def percent_cover(poly, bufPoly, units="SQUAREMETERS"):
    """Percent Cover
    Purpose:"""
    arcpy.MakeFeatureLayer_management(poly, "polyLyr")
    lst = []
    orderLst = []
    # ADD handle for when no overlap?
    # Check for "orig_ID" then "ORIG_FID" then use OID@
    field = find_ID(bufPoly)
    with arcpy.da.SearchCursor(bufPoly, ["SHAPE@", field]) as cursor:
        for row in cursor:
            totalArea = dec(row[0].getArea("PLANAR", units))
            match = "INTERSECT"  # default
            arcpy.SelectLayerByLocation_management("polyLyr", match, row[0])
            lyrLst = []
            with arcpy.da.SearchCursor("polyLyr", ["SHAPE@"]) as cursor2:
                for row2 in cursor2:
                    p = 4  # dimension = polygon
                    interPoly = row2[0].intersect(row[0], p)
                    interArea = dec(interPoly.getArea("PLANAR", units))
                    lyrLst.append((interArea/totalArea)*100)
            lst.append(sum(lyrLst))
            orderLst.append(row[1])
    arcpy.Delete_management("polyLyr")
    # Sort by ID field
    orderLst, lst = (list(x) for x in zip(*sorted(zip(orderLst, lst))))
    return lst


def lst_to_AddField_lst(table, field_lst, list_lst, type_lst):
    """Lists to ADD Field
    Purpose:
    Notes: Table, list of new fields, list of listes of field values,
           list of field datatypes.
    """
    if len(field_lst) != len(list_lst) or len(field_lst) != len(type_lst):
        message("ERROR: lists aren't the same length!")
    #  "" defaults to "DOUBLE"
    type_lst = ["Double" if x == "" else x for x in type_lst]

    for i, field in enumerate(field_lst):
        # Add fields
        arcpy.AddField_management(table, field, type_lst[i])
        # Add values
        lst_to_field(table, field, list_lst[i])


def lst_to_field(table, field, lst):
    """Add List to Field
    Purpose:
    Notes: 1 field at a time
    Example: lst_to_field(featureClass, "fieldName", lst)
    """
    if len(lst) == 0:
        message("No values to add to '{}'.".format(field))
    elif field_exists(table, field):   
        with arcpy.da.UpdateCursor(table, [field]) as cursor:
            # For row in cursor:
            for i, row in enumerate(cursor):
                    row[0] = lst[i]
                    cursor.updateRow(row)
    else:
        message("{} field not found in {}".format(field, table))


def buffer_population(poly, popRast):
    """Buffer Population
    Purpose: Returns sum of raster cells in buffer as list.
    Notes: Currently works on raster of population total (not density)
    Notes: Requires Spatial Analyst (look into rasterstats as alternative?)
           https://pcjericks.github.io/py-gdalogr-cookbook/raster_layers.html
    Notes: Reserved fields are used for Zone Field, which causes problems
           when reading the results table because the new field with counts
           can't have the same name as the reserved field, which is where fld2
           comes into use.
    Notes: If poly has overlapping polygons, the analysis will not be performed
           for each individual polygon, because poly is converted to a raster
           so each location can have only one value.
    """
    lst = [] # defined so an empty set is returned on failure
    if len(get_ext(poly)) == 0:  # in GDB
        DBF = poly + "_popTable"
    else:  # DBF
        DBF = os.path.splitext(poly)[0] + "_pop.dbf"
    del_exists(DBF)  # delete intermediate if it exists
    # Make sure Spatial Analyst is available.
    sa_Status = arcpy.CheckOutExtension("Spatial")
    if sa_Status == "CheckedOut":
        # Check for "orig_ID" then "ORIG_FID" then use OID@
        try:
            fld = find_ID(poly)
            arcpy.sa.ZonalStatisticsAsTable(poly, fld, popRast, DBF, "", "ALL")
            # check if fld is a reserved field that would be renamed
            if fld == str(arcpy.Describe(poly).OIDFieldName):
                fld2 = fld + "_"  # hoping the assignment is consistent
            else:
                fld2 = fld
            lst = field_to_lst(DBF, [fld2, "SUM"])  # Count based method
            # The following is a density based method, uses projection units
            #lst = [a * m for a,m in zip(field_to_lst(DBF, [fld2, "AREA"]),
            #                            field_to_lst(DBF, [fld2, "MEAN"]))]
            arcpy.Delete_management(DBF)
        except Exception:
            message("Unable to perform analysis on Raster of population", 1)
            e = sys.exc_info()[1]
            message(e.args[0], 1)
    else:
        message("Spatial Analyst is " + sa_Status)
        message("Population in area could not be estimated.", 1)
    return lst


def buffer_contains(poly, pnts):
    """Buffer Contains
    Purpose: Returns number of points in buffer as list.
    Notes: When a buffer is created for a site it may get a new OBJECT_ID, but
           the site OID@ is maintained as ORIG_FID, buffer OID@ returns the
           new ID. Since results are joined back to the site they must be
           sorted in site order. The outTbl the buffer is created from was
           assigned "orig_ID" which is preffered, then ORIG_FID, then OID@.
    Example: lst = buffer_contains(view_50, addresses).
    """
    ext = get_ext(poly)
    plyOut = os.path.splitext(poly)[0] + "_2" + ext
    del_exists(plyOut)  # delete intermediate if it exists
    # Use spatial join to count points in buffers.
    join = "JOIN_ONE_TO_ONE"  # one line for each buffer
    match = "INTERSECT"  # pnts matched if they intersect target poly
    arcpy.SpatialJoin_analysis(poly, pnts, plyOut, join, "", "", match, "", "")
    # Check for fields to sort with, then "Join_Count" is the number of pnts
    field = find_ID(plyOut)
    lst = field_to_lst(plyOut, [field, "Join_Count"])
    arcpy.Delete_management(plyOut)
    return lst


def list_buffer(lyr, field, lyr_range):
    """List values for field from layer intersecting layer range
    Purpose: generates a list of catchments in buffer"""
    arcpy.SelectLayerByAttribute_management(lyr, "CLEAR_SELECTION")
    arcpy.SelectLayerByLocation_management(lyr, "INTERSECT", lyr_range)
    return field_to_lst(lyr, field)  # list field values


def list_areas(table, units="SQUAREMETERS", typ="PLANAR"):
    """return list of polygon areas"""
    lst = []
    if units is None:  # use SHAPE@AREA token
        with arcpy.da.SearchCursor(table, ["SHAPE@AREA"]) as cursor:
            for row in cursor:
                lst.append(row[0].area)  # units based on spatial refenerence
    else:
        with arcpy.da.SearchCursor(table, ["SHAPE@"]) as cursor:
            for row in cursor:
                lst.append(float(row[0].getArea(typ, units)))
    return lst


def quant_to_qual_lst(lst):
    """Quantitative List to Qualitative List
    Purpose: convert counts of >0 to YES"""
    qual_lst = []
    for i in lst:
        if (i == 0):
            qual_lst.append("NO")
        else:
            qual_lst.append("YES")
    return qual_lst

        
def deleteFC_Lst(lst):
    """delete listed feature classes or layers
    Purpose: delete feature classes or layers using a list."""
    for l in lst:
        if l is not None:
            arcpy.Delete_management(l)
        
###########FLOODING###########
def FR_MODULE(PARAMS):
    """Flood Risk Benefits"""
    start = time.clock()  # start the clock
    mod_str = "Flood Risk Reduction Benefits analysis"
    message(mod_str + "...")

    addresses, popRast = PARAMS[0], PARAMS[1]
    flood_zone = PARAMS[2]
    OriWetlands, subs = PARAMS[3], PARAMS[4]
    Catchment, InputField, Flow = PARAMS[5], PARAMS[6], PARAMS[7]
    outTbl = PARAMS[8]

    path = os.path.dirname(outTbl) + os.sep
    ext = get_ext(outTbl)

    # Check NHD+ inputs
    Catchment, InputField, Flow = nhdPlus_check(Catchment, InputField,
                                                Flow, outTbl)
    
    # Check for "orig_ID" then "ORIG_FID" then use OID@
    OID_field = find_ID(outTbl)

    # Naming convention for flood intermediates
    FA = path + "temp_FloodArea_"
    # Name intermediate files
    assets = "{}assets{}".format(FA, ext)  # addresses/population in flood zone
    fld_A2 = "{}2_zone{}".format(FA, ext)  # flood zone in buffer
    fld_A3 = "{}3_downstream{}".format(FA, ext)  # flood zone downstream

    # Check that there are assets in the flood zone.
    if flood_zone is not None:
        # check spatial ref
        flood_zone = checkSpatialReference(outTbl, flood_zone)
        if addresses is not None:  # if using addresses
            del_exists(assets)
            arcpy.Clip_analysis(addresses, flood_zone, assets)
            total_cnt = arcpy.GetCount_management(assets)  # count addresses
            # If there are no addresses in flood zones stop analysis.
            if int(total_cnt.getOutput(0)) <= 0:
                raise Exception("No addresses within the flooded area.")
        elif popRast is not None:
            # This clip is inexact, loosing cells that overlap the flood zone
            #minimally. It is not used in results, only to test overlap.
            #geo = "NONE" # use flood_zone extent to clip
            geo = "ClippingGeometry"  # use flood_zone geometry to clip
            e = "NO_MAINTAIN_EXTENT"  # maintain cells, no resampling
            del_exists(assets)
            arcpy.Clip_management(popRast, "", assets, flood_zone, "", geo, e)
            # If there are no people in flood zones stop analysis
            m = "MAXIMUM"
            rMax = arcpy.GetRasterProperties_management(assets, m).getOutput(0)
            if rMax <= 0:
                raise Exception("Input raster not inside flooded area extent.")
    else:
        if addresses is not None:
            assets = addresses
        message("WARNING: No flood zone entered, results will be analyzed " +
                "using the complete area instead of just areas that flood.", 1)
        #raise Exception("No flood zone entered")

    start = exec_time(start, "intiating variables for " + mod_str)

    # Buffer each site by 2.5 mile radius
    fld_A1 = simple_buffer(outTbl, "temp_FloodArea_1_buffer", "2.5 Miles")

    # Clip the buffer to flood polygon
    message("Reducing flood zone to 2.5 Miles from sites...")
    if flood_zone is not None:
        del_exists(fld_A2)
        arcpy.Clip_analysis(fld_A1, flood_zone, fld_A2)
    else:
        fld_A2 = fld_A1

    # Clip the buffered flood area to downstream basins
    message("Determining downstream flood zone area from:\n" + Catchment)

    # Copy flood zone in buffer to clip by downstream catchments
    del_exists(fld_A3)
    arcpy.CopyFeatures_management(fld_A2, fld_A3)
    if field_exists(fld_A3, OID_field) is False:  # Add OID field
        arcpy.AddField_management(fld_A3, OID_field, "LONG")

    arcpy.MakeFeatureLayer_management(fld_A1, "buffer")
    arcpy.MakeFeatureLayer_management(fld_A2, "flood_lyr")
    arcpy.MakeFeatureLayer_management(Catchment, "catchment")
    arcpy.MakeFeatureLayer_management(fld_A3, "down_lyr")

    UpCOMs, DownCOMs = setNHD_dict(Flow)  # REDUCE TO DownCOMs ONLY

    site_cnt = arcpy.GetCount_management(outTbl)
    sel = "NEW_SELECTION"
    with arcpy.da.SearchCursor(outTbl, ["SHAPE@", OID_field]) as cursor:
        for j, site in enumerate(cursor):
            # Select buffer and flood zone for site
            wClause = "{} = {}".format(OID_field, site[1])
            arcpy.SelectLayerByAttribute_management("buffer", sel, wClause)
            arcpy.SelectLayerByAttribute_management("down_lyr", sel, wClause)

            # List catchments in buffer
            bufferCatchments = list_buffer("catchment", InputField, "buffer")

            # Subset DownCOMs to only those in buffer (helps limit coast)
            shortDownCOMs = defaultdict(list)
            for i in set(bufferCatchments):
                shortDownCOMs[i].append(DownCOMs[i])
                shortDownCOMs[i] = list(chain.from_iterable(shortDownCOMs[i]))

            # Select catchment(s) where the restoration site overlaps
            oTyp = "INTERSECT"  # overlap type
            arcpy.SelectLayerByLocation_management("catchment", oTyp, site[0])

            #check that site overlaps catchment
            if int(arcpy.GetCount_management("catchment").getOutput(0))>0:

                # List Subset catchments downstream selection
                downCatch = list_downstream("catchment", InputField, shortDownCOMs)
                # Catchments in both downCatch and bufferCatchments
                # Redundant, the last catchment will already be outside the buffer
                catchment_lst = list(set(downCatch).intersection(bufferCatchments))
                # SELECT downstream catchments in catchment_lst
                qryDown = selectStr_by_list(InputField, catchment_lst)
                arcpy.SelectLayerByAttribute_management("catchment", sel, qryDown)

                # Clip corresponding flood zone to selected catchments
                with arcpy.da.UpdateCursor("down_lyr", ["SHAPE@"]) as cursor2:
                    for zone in cursor2:
                        geo = {}
                        with arcpy.da.SearchCursor("catchment", ["SHAPE@"]) as c3:
                            for row in c3:
                                if geo == {}:
                                    geo = row[0]
                                else:
                                    geo = row[0].union(geo)
                        # Update flood zone geometry
                        zone[0] = zone[0].intersect(geo, 4)
                        cursor2.updateRow(zone)

                message("Determined catchments downstream for site " +
                        "{}, of {}".format(j+1, site_cnt))
            else:
                message("Catchments don't overlap site {}: {}.".format(
                    j+1, wClause), 1)
                message("Results for site {} not limied to downstream.".format(
                    j+1), 1)

    start = exec_time(start, "reducing flood zones to downstream from sites")
    # 3.2 How Many Benefit - Area
    step_str = "3.2 How Many Benefit?"
    message("{} - {}".format(mod_str, step_str))

    # Get areas for buffer
    lst_FA1_area = list_areas(fld_A1)
    # Get areas for flood zones in buffer
    lst_FA2_area = list_areas(fld_A2)
    # Get areas for downstream flood zones in buffer
    lst_FA3_areaD = list_areas(fld_A3)

    # Percent of buffer in flood zone
    lst_FA2_pct = [a/b for a, b in zip(lst_FA2_area, lst_FA1_area)]
    # Percent of flood zone downstream
    lst_FA3_Dpct = [a/b for a, b in zip(lst_FA3_areaD, lst_FA2_area)]

    # 3.2 How Many Benefit - People
    message("Counting people who benefit...")
    if addresses is not None:
        # Addresses in buffer/flood zone/downstream.
        lst_flood_cnt = buffer_contains(fld_A3, assets)

    elif popRast is not None:
        # Population in buffer/flood zone/downstream
        lst_flood_cnt = buffer_population(fld_A3, popRast)

    start = exec_time(start, "{} - {}".format(mod_str, step_str))

    # 3.3.A SERVICE QUALITY
    step_str = "3.3.A Service Quality"
    message("{} - {}".format(mod_str, step_str))
    # Calculate area of each restoration site
    lst_siteArea = list_areas(outTbl, "ACRES", "GEODESIC")
    start = exec_time(start, "{} - {}".format(mod_str, step_str))

    # 3.3.B: SUBSTITUTES
    if subs is not None:
        step_str = "3.3.B Scarcity"
        message("{} - {}".format(mod_str, step_str))
        message("Estimating substitutes within 2.5 miles downstream")
        subs = checkSpatialReference(outTbl, subs)

        # Subs in buffer/flood/downstream
        lst_subs_cnt = buffer_contains(fld_A3, subs)
        # Convert lst to binary list
        lst_subs_cnt_boo = quant_to_qual_lst(lst_subs_cnt)

        start = exec_time(start, "{} - {} - 'FR_3B_boo'".format(mod_str,
                                                                step_str))
    else:
        message("No Substitutes (dams & levees) specified")
        lst_subs_cnt, lst_subs_cnt_boo = [], []

    # 3.3.B: SCARCITY
    # This uses the complete buffer (fld_A1), alternatively,
    # this could be restricted to the flood zone or upstream/downstream.
    if OriWetlands is not None:
        message("Estimating area of wetlands within 2.5 miles in both " +
                "directions (5 miles total) of restoration sites...")
        lst_FR_3B = percent_cover(OriWetlands, fld_A1)
    else:
        message("Substitutes (existing wetlands) input not specified, " +
                "'FR_3B_sca' will all be '0'.")
        lst_FR_3B = []
    start = exec_time(start, "{} - {} - 'FR_3B_sca'".format(mod_str, step_str))

    # FINAL STEP: move results to results file
    message("Saving {} results to Output...".format(mod_str))
    fields_lst = ["FR_2_cnt", "FR_zPct", "FR_zDown", "FR_zDoPct", "FR_3A_acr",
                  "FR_3A_boo", "FR_sub", "FR_3B_boo", "FR_3B_sca", "FR_3D_boo"]
    list_lst = [lst_flood_cnt, lst_FA2_pct, lst_FA3_areaD,
                lst_FA3_Dpct, lst_siteArea, [], lst_subs_cnt,
                lst_subs_cnt_boo, lst_FR_3B, []]
    type_lst = ["", "", "", "", "", "Text", "", "Text", "", "Text"]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, type_lst)

    # Cleanup
    if assets in [addresses, popRast]:
        assets = None  # avoid deleting
    deleteFC_Lst([fld_A3, fld_A2, fld_A1, assets])
    deleteFC_Lst(["buffer", "flood_lyr", "catchment", "down_lyr", "VUB"])

    message(mod_str + " complete")

#########################
#########EXECUTE#########
try:
    start = time.clock()
    FR_MODULE([addresses, popRast, flood_zone, OriWetlands, subs, Catchment, InputField, relTbl, outTbl])
    start = exec_time(start, "Flood Risk Benefit assessment")
except Exception:
    message("Error occured during assessment.", 1)
    traceback.print_exc()
