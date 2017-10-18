"""
# Name: Rapid Benefit Indicator Assessment - All Modules (Tier 1)
# Purpose: Calculate values for benefit indicators using wetland
#          restoration site polygons and a variety of other input data
# Author: Justin Bousquin
# Additional Author Credits: Michael Charpentier (Report generation)
# Additional Author Credits: Marc Weber and Tad Larsen (StreamCat)

# Version Notes:
# Developed in ArcGIS 10.3
# 0.1.0 Tool complete and ran for case study using this version
"""

import os
import time
import arcpy
import subprocess
from itertools import chain
from urllib import urlretrieve
from shutil import rmtree
from decimal import Decimal
from collections import deque, defaultdict


def create_outTbl(sites, outTbl):
    """create copy of sites to use for processing and results
    Notes: this also creates an "orig_ID" field to retain @OID
    """
    # Check if outTbl already exists, and delete if so
    del_exists(outTbl)
    arcpy.CopyFeatures_management(sites, outTbl)
    # Check if "orig_ID" field exists already
    if field_exists(outTbl, "orig_ID"):
        message("orig_ID field already exists in sites, it will be used " +
                "to maintain unique site IDs")
    else:
        # Create field for orig OID@
        arcpy.AddField_management(outTbl, "orig_ID", "Long")
        with arcpy.da.UpdateCursor(outTbl, ["OID@", "orig_ID"]) as cursor:
            for row in cursor:
                row[1] = row[0]
                cursor.updateRow(row)


def get_ext(FC):
    """get extension"""
    ext = arcpy.Describe(FC).extension
    if len(ext) > 0:
        ext = "." + ext
    return ext


def dec(x):
    """decimal.Decimal"""
    return Decimal(x)


def mean(l):
    "get mean of list"
    return sum(l)/float(len(l))


def deleteFC_Lst(lst):
    """delete listed feature classes or layers
    Purpose: delete feature classes or layers using a list."""
    for l in lst:
        if l is not None:
            arcpy.Delete_management(l)


def SocEqu_BuffDist(lst):
    """Buffer Distance for Social equity based on lst benefits
    Purpose: Returns a distance to use for the buffer based on which
             benefits are checked and how far those are delivered.
    """
    # ck[0, 4] = [flood, view, edu, rec, bird]
    if lst[0] is not None:
        buff_dist = "2.5 Miles"
    elif lst[3] is not None:
        buff_dist = "0.33 Miles"
    elif lst[2] is not None:
        buff_dist = "0.25 Miles"
    elif lst[4] is not None:
        buff_dist = "0.2 Miles"
    elif lst[1] is not None:
        buff_dist = "100 Meters"
    else:
        message("No benefits selected, default distance for Social Equity " +
                "will be 2.5 Miles")
        buff_dist = "2.5 Miles"
    return buff_dist


def exportReport(pdfDoc, pdf_path, pg_cnt, mxd):
    """pdf from mxd"""
    pdf = pdf_path + "report_page_" + str(pg_cnt) + ".pdf"
    del_exists(pdf)
    arcpy.mapping.ExportToPDF(mxd, pdf, "PAGE_LAYOUT")
    pdfDoc.appendPages(pdf)
    arcpy.Delete_management(pdf, "")


def textpos(theText, column, indnumber):
    """position text on report
    Author Credit: Mike Charpentier
    """
    if column == 1:
        theText.elementPositionX = 6.25
    else:
        theText.elementPositionX = 7.15
    ypos = 9.025 - ((indnumber - 1) * 0.2)
    theText.elementPositionY = ypos


def boxpos(theBox, column, indnumber):
    """position box on report
    Author Credit: Mike Charpentier
    """
    if column == 1:
        theBox.elementPositionX = 5.8
    else:
        theBox.elementPositionX = 6.7
    ypos = 9 - ((indnumber - 1) * 0.2)
    theBox.elementPositionY = ypos


def fldExists(fieldName, colNumber, rowNumber, fieldInfo, blackbox):
    """report
    Author Credit: Mike Charpentier
    """
    fldIndex = fieldInfo.findFieldByName(fieldName)
    if fldIndex > 0:
        return True
    else:
        newBox = blackbox.clone("_clone")
        boxpos(newBox, colNumber, rowNumber)
        return False


def proctext(fieldVal, fieldType, ndigits, ltorgt, aveVal, colNum, rowNum,
             allNos, mxd):
    """Author Credit: Mike Charpentier
    """
    # Map elements
    graphic = "GRAPHIC_ELEMENT"
    txt = "TEXT_ELEMENT"
    bluebox = arcpy.mapping.ListLayoutElements(mxd, graphic, "bluebox")[0]
    redbox = arcpy.mapping.ListLayoutElements(mxd, graphic, "redbox")[0]
    graybox = arcpy.mapping.ListLayoutElements(mxd, graphic, "graybox")[0]
    blackbox = arcpy.mapping.ListLayoutElements(mxd, graphic, "blackbox")[0]
    indtext = arcpy.mapping.ListLayoutElements(mxd, txt, "IndText")[0]

    # Process the box first so that text draws on top of box
    if fieldVal is None or fieldVal == '':
        newBox = blackbox.clone("_clone")
    else:
        if fieldType == "Num":  # Process numeric fields
            if ltorgt == "lt":
                if fieldVal < aveVal:
                    newBox = bluebox.clone("_clone")
                else:
                    newBox = redbox.clone("_clone")
            else:
                if fieldVal > aveVal:
                    newBox = bluebox.clone("_clone")
                else:
                    newBox = redbox.clone("_clone")
        else:  # Process text fields (booleans)
            if allNos == 1:
                newBox = graybox.clone("_clone")
            else:
                if fieldVal == aveVal:
                    newBox = bluebox.clone("_clone")
                else:
                    newBox = redbox.clone("_clone")
    boxpos(newBox, colNum, rowNum)
    # Process the text
    if not (fieldVal is None or fieldVal == ' '):
        newText = indtext.clone("_clone")
        if fieldType == "Num":  # process numeric fields
            if fieldVal == 0:
                newText.text = "0"
            else:
                if ndigits == 0:
                    if fieldVal > 10:
                        rndnumber = round(fieldVal, 0)
                        intnumber = int(rndnumber)
                        newnum = format(intnumber, ",d")
                        newText.text = newnum
                    else:
                        newText.text = str(round(fieldVal, 1))
                else:
                    newText.text = str(round(fieldVal, ndigits))
        else:  # boolean fields
            if allNos == 1:
                newText.text = "No"
            else:
                if fieldVal == "YES":
                    newText.text = "Yes"
                else:
                    newText.text = "No"
        textpos(newText, colNum, rowNum)


def tbl_fieldType(table, field):
    """Return data type for a field in a table"""
    fields = arcpy.ListFields(table)
    for f in fields:
        if f.name == field:
            return f.type
            break


def ListType_fromField(typ, lst):
    """list type from field
    Purpose: map python list type based on field.type
    Example: lst = type_fromField(params[1].type, params[2].values)
             where (field Obj; list of unicode values).
    """
    if typ in ["Single", "Float", "Double"]:
        return map(float, lst)
    elif typ in ["SmallInteger", "Integer"]:  # "Short" or "Long"
        return map(int, lst)
    else:  # String #Date?
        try:
            return map(str, lst)
        except:
            message("Could not recongnize field type")


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
    
    # Prep catchments
    Catchment = checkSpatialReference(outTbl, catchment)
    arcpy.MakeFeatureLayer_management(Catchment, "catchment")
    arcpy.SelectLayerByLocation_management("catchment", "INTERSECT", outTbl)
    # Count selected catchments
    numCat = int(arcpy.GetCount_management("catchment").getOutput(0))
    if numCat > 0:
        message("NHD Plus Catchments overlap some sites")
        return Catchment, joinField, relTbl
    else:
        raise Exception("No overlapping NHD Plus Catchments found." + errMsg)


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


def children(token, tree):
    """List children
    Purpose: returns list of all children"""
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


def HTTP_download(request, directory, filename):
    """Download HTTP request to filename
    Param request: HTTP request link ending in "/"
    Param directory: Directory where downloaded file will be saved
    Param filename: Name of file for download request and saving
    """
    host = "http://www.horizon-systems.com/NHDPlus/NHDPlusV2_data.php"
    # Add dir to var zipfile is saved as
    f = directory + os.sep + filename
    r = request + filename
    try:
        urlretrieve(r, f)
        message("HTTP downloaded successfully as:\n" + str(f))
    except:
        message("Error downloading from: " + '\n' + str(r))
        message("Try manually downloading from: " + host)


def WinZip_unzip(directory, zipfile):
    """Use program WinZip in C:\Program Files\WinZip to unzip .7z"""
    message("Unzipping download...")
    message("Winzip may open. If file already exists you will be prompted...")
    d = directory
    z = directory + os.sep + zipfile
    try:
        zipExe = r"C:\Program Files\WinZip\WINZIP64.EXE"
        args = zipExe + ' -e ' + z + ' ' + d
        subprocess.call(args, stdout=subprocess.PIPE)
        message("Successfully extracted NHDPlus data to:\n" + d)
        os.remove(z)
        message("Deleted zipped NHDPlus file")
    except:
        message("Unable to extract NHDPlus files. " +
                "Try manually extracting the files from:\n" + z)
        message("Software to extract '.7z' files can be found at: " +
                "http://www.7-zip.org/download.html")


def append_to_default(out_file, in_file, msg):
    """Pull downloaded catchments/flow tables into defaults in gdb
    """
    folder = os.path.dirname(in_file)
    gdb = os.path.dirname(out_file)
    f = os.path.basename(out_file)
    # Check that sub-folder exists in download
    if os.path.isdir(folder):
        # Find the file in that folder
        if arcpy.Exists(in_file):
            # Find the default Feature Class or table
            if arcpy.Exists(out_file):
                # Append the downloaded into the default
                arcpy.Append_management(in_file, out_file, "NO_TEST")
                message("Downloaded {} added to:\n{}".format(msg, out_file))
                # Delete downloaded
                try:
                    rmtree(folder)
                    message("Downloaded {} folder deleted".format(msg))
                except:
                    message("Unable to delete {} download folder".format(msg))
            else:
                message("Expected '{}' not found in '{}'".format(f, gdb))
        else:
            message("Expected download file '{}' not found".format(in_file))
    else:
        message("Expected download folder '{}' not found".format(folder))


def view_score(lst_50, lst_100):
    """Calculate Weighted View Score
    Purpose: list of weighted view scores.
    Notes: Does not currently test that the lists are of equal length.
    """
    lst = []
    # add test for equal length of lists? (robust check, but shouldn't happen)
    for i, item in enumerate(lst_50):
        lst.append(item * 0.7 + lst_100[i] * 0.3)
    return lst


def setParam(str1, str2, str3, str4="", str5="", multiValue=False):
    """Set Input Parameter
    Purpose: Returns arcpy.Parameter for provided string,
             setting defaults for missing.
    """
    lst = [str1, str2, str3, str4, str5]
    defLst = ["Input", "name", "GpFeatureLayer", "Required", "Input"]
    for i, str_ in enumerate(lst):
        if str_ == "":
            lst[i] = defLst[i]
    return arcpy.Parameter(
        displayName=lst[0],
        name=lst[1],
        datatype=lst[2],
        parameterType=lst[3],
        direction=lst[4],
        multiValue=multiValue)


def disableParamLst(lst):
    """Disable Parameter List
    Purpose: disables input fields for a list of parameters.
    """
    for field in lst:
        field.enabled = False


def message(string, severity = 0):
    """Generic message
    Purpose: prints string message in py or pyt.
    """
    print(string)
    if severity == 1:
        arcpy.AddWarning(string)
    else:
        arcpy.AddMessage(string)


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


def field_exists(table, field):
    """Check if field exists in table
    Notes: return true/false
    """
    fieldList = [f.name for f in arcpy.ListFields(table)]
    return True if field in fieldList else False


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


def check_vars(outTbl, addresses, popRast):
    """Check variables
    Purpose: make sure population var has correct spatial reference.
    """
    if addresses is not None:
        # Check spatial ref
        addresses = checkSpatialReference(outTbl, addresses)
        message("Addresses OK")
        return addresses, None
    elif popRast is not None:
        popRast = checkSpatialReference(outTbl, popRast)  # check projection
        message("Population Raster OK")
        return None, popRast
    else:
        arcpy.AddError("No population inputs specified!")
        print("No population inputs specified!")
        raise arcpy.ExecuteError


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


def buffer_donut(FC, outFC_name, buffer_distance):
    """Donut Buffer
    Purpose: Takes inside buffer and creates outside buffers.
             Ensures sort is done on find_ID(), since FID/OID may change.
    Note: Same results as MultipleRingBuffer_analysis(FC, outFC, buf,
          units, "", "None", "OUTSIDE_ONLY") - just faster.
    """
    # Make complete buffer first
    outFC = simple_buffer(FC, outFC_name, buffer_distance)

    # Make sure it has ID field (should always anyway)
    field = find_ID(FC)
    if not field_exists(outFC, field):
        arcpy.AddField_management(outFC, field)

    # Make layer for inner area to remove
    arcpy.MakeFeatureLayer_management(FC, "lyr")
    sel = "NEW_SELECTION"  # selection type

    # Use shape token tokens to remove inner from outter
    with arcpy.da.UpdateCursor(outFC, ["SHAPE@", field]) as cursor:
        for buf in cursor:
            # Select FC based on field
            wC = "{} = {}".format(field, buf[1])  # where clause
            arcpy.SelectLayerByAttribute_management("lyr", sel, wC)
            with arcpy.da.SearchCursor("lyr", ["SHAPE@"]) as cursor2:
                for row in cursor2:
                    buf[0] = buf[0].difference(row[0])
            cursor.updateRow(buf)
    arcpy.Delete_management("lyr")  # delete
    return outFC


def simple_buffer(outTbl, tempName, bufferDist):
    """ Create buffer using tempName"""
    path = os.path.dirname(outTbl) + os.sep
    buf = path + tempName + get_ext(outTbl) # Set temp file name
    del_exists(buf)
    arcpy.Buffer_analysis(outTbl, buf, bufferDist)
    return buf


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


def find_ID(table):
    """return an ID field where orig_ID > ORIG_FID > OID@
    """
    if field_exists(table, "orig_ID"):
        return "orig_ID"
    elif field_exists(table, "ORIG_FID"):
        return "ORIG_FID"
    else:
        return arcpy.Describe(table).OIDFieldName


def fieldName(name):
    """return acceptable field name from string
    """
    Fname = name[0:8]  # Correct length <9
    for char in ['.', ' ', ',', '!', '@', '#', '$', '%', '^', '&', '*']:
        if char in Fname:
            Fname = Fname.replace(char, "_")
    return Fname


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


def list_buffer(lyr, field, lyr_range):
    """List values for field from layer intersecting layer range
    Purpose: generates a list of catchments in buffer"""
    arcpy.SelectLayerByAttribute_management(lyr, "CLEAR_SELECTION")
    arcpy.SelectLayerByLocation_management(lyr, "INTERSECT", lyr_range)
    return field_to_lst(lyr, field)  # list field values


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


def field_to_lst(table, field):
    """Read Field to List
    Purpose:
    Notes: if field is: string, 1 field at a time;
                        list, 1 field at a time or 1st field is used to sort
    Example: lst = field_to_lst("table.shp", "fieldName")
    """
    lst = []
    if type(field) == list:
        if len(field) == 1:
            field = field[0]
        elif len(field) > 1:
            # First field is used to sort, second field returned as list
            order = []
            # Check for fields in table
            if field_exists(table, field[0]) and field_exists(table, field[1]):
                with arcpy.da.SearchCursor(table, field) as cursor:
                    for row in cursor:
                        order.append(row[0])
                        lst.append(row[1])
                order, lst = (list(x) for x in zip(*sorted(zip(order, lst))))
                return lst
            else:
                message(str(field) + " could not be found in " + str(table))
                message("Empty values will be returned.")
        else:
            message("Something went wrong with the field to list function")
            message("Empty values will be returned.")
            return []
    if type(field) == str:
        # Check that field exists in table
        if field_exists(table, field) is True:
            with arcpy.da.SearchCursor(table, [field]) as cursor:
                for row in cursor:
                    lst.append(row[0])
            return lst
        else:
            message(str(field) + " could not be found in " + str(table))
            message("Empty values will be returned.")
    else:
        message("Something went wrong with the field to list function")


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


def unique_values(table, field):
    """Unique Values
    Purpose: returns a sorted list of unique values
    Notes: used to find unique field values in table column
    """
    with arcpy.da.SearchCursor(table, [field]) as cursor:
        return sorted({row[0] for row in cursor if row[0]})


def buffer_contains_multiset(dataset1, dataset2, bufferFC):
    """make qual list based on 2 datasets"""
    lst = []
    if dataset1 is not None:
        # Dataset in buffer?
        lst_1 = buffer_contains(bufferFC, dataset1)
        if dataset2 is not None:
            # Dataset2 in buffer?
            lst_2 = buffer_contains(bufferFC, dataset2)
            for i, item in enumerate(lst_1):
                if 0 in [item] and 0 in[lst_2[i]]:
                    lst.append("NO")
                else:
                    lst.append("YES")
            return lst
        else:
            return quant_to_qual_lst(lst_1)
    elif dataset2 is not None:
        lst_2 = buffer_contains(bufferFC, dataset2)
        return quant_to_qual_lst(lst_2)
    else:
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


def NHD_get_MODULE(PARAMS):
    """Download NHD Plus Data"""

    sites = PARAMS[0]
    NHD_VUB = PARAMS[1]
    local = PARAMS[2]

    # Assign default destination if not user specified
    script_dir = os.path.dirname(os.path.realpath(__file__))
    if os.path.basename(script_dir) == 'py_standaloneScripts':
        # Move up one folder if standalone script
        script_dir = os.path.dirname(script_dir) + os.sep
    else:
        script_dir = script_dir + os.sep
    if local is None:
        local = script_dir + "NHDPlusV21"
        message("Files will be Downloaded to default location:\n" + local)
    else:
        message("Files will be Downloaded to user location:\n" + local)

    # Default file location to copy downloads to
    local_gdb = local + os.sep + "NHDPlus_Downloads.gdb"
    if os.path.isdir(local_gdb) and get_ext(local_gdb) == ".gdb":
        message("Downloaded files will be added to default file geodatabase")
    else:
        message("Unable to find Default file geodatabase:\n" + local_gdb)
        message("Files will be downloaded but must be combined manually.")

    # Assign default boundary file if not user specified
    if NHD_VUB is None:
        NHD_VUB = local_gdb + os.sep + "BoundaryUnit"
        loc = "default location:\n" + NHD_VUB
    else:
        loc = "user specified location:\n" + NHD_VUB

    # Check boundary file
    if arcpy.Exists(NHD_VUB):
            message("NHDPlus Boundaries found in " + loc)
    else:
        arcpy.AddError("NHDPlus Boundaries could not be found in " + loc)
        print("NHDPlus Boundaries could not be found in " + loc)
        raise arcpy.ExecuteError

    # Check projection.
    if get_ext(local) == '.gdb':  # filename if re-projected in geodatabase
        out_prj = local + os.sep + 'VUB_prj'
    else:  # filename if re-projected in folder
        out_prj = local + os.sep + 'VUB_prj.shp'
    NHD_VUB = checkSpatialReference(sites, NHD_VUB, out_prj)

    # Select NHDPlus vector unit boundaries
    arcpy.MakeFeatureLayer_management(NHD_VUB, "VUB")  # make layer.
    overlap = "WITHIN_A_DISTANCE"
    dis = "5 Miles"  # distance within
    arcpy.SelectLayerByLocation_management("VUB", overlap, sites, dis, "", "")

    # http://www.horizon-systems.com/NHDPlusData/NHDPlusV21/Data/NHDPlus
    sub_link = "/{0}Data/{0}V21/Data/{0}".format("NHDPlus")
    NHD_http = "http://www.horizon-systems.com" + sub_link

    # Gather info from fields to construct request
    ID_list = field_to_lst("VUB", "UnitID")
    d_list = field_to_lst("VUB", "DrainageID")

    for i, DA in enumerate(d_list):
        # Give progress update
        message("Downloading region {} of {}".format(str(i+1), len(d_list)))

        # Zipfile names
        ID = ID_list[i]
        ext = ".7z"

        # Componentname is the name of the NHDPlusV2 component in the file
        f_comp = "NHDPlusCatchment"
        ff_comp = "NHDPlusAttributes"
        
        # Version dictionary, ID [Catchments, Attributes]
        vv_dict = {"01": ["01", "08"],
                   "02": ["01", "07"],
                   "03N": ["01", "06"],
                   "03S": ["01", "06"],
                   "03W": ["01", "06"],
                   "04": ["01", "06"],
                   "05": ["01", "08"],
                   "06": ["05", "09"],
                   "07": ["01", "09"],
                   "08": ["01", "08"],
                   "09": ["01", "06"],
                   "10L": ["01", "11"],
                   '10U': ["02", "09"],
                   "11": ["01", "06"],
                   "12": ["01", "08"],
                   '13': ["02", "06"],
                   "14": ["01", "09"],
                   "15": ["01", "08"],
                   "16": ["01", "05"],
                   '17': ["02", "09"],
                   "18": ["01", "07"],               
                   "20": ["01", "02"],
                   "21": ["01", "02"],
                   "22AS": ["01", "02"],
                   "22GU": ["01", "02"],
                   "22MP": ["01", "02"]
                   }
        
        # Assign zipfile data content version
        f_vv = vv_dict[ID][0]
        ff_vv = vv_dict[ID][1]

        # Set http zipfile is requested from
        if DA in ["SA", "MS", "CO", "PI"]:  # regions with sub-regions
            request = NHD_http + DA + "/" + "NHDPlus" + ID + "/"
        else:
            request = NHD_http + DA + "/"

        # Download child destination folder
        ID_folder = local + os.sep + "NHDPlus" + DA + os.sep + "NHDPlus" + ID

        # Assign catchment filenames
        f = "NHDPlusV21_{}_{}_{}_{}{}".format(DA, ID, f_comp, f_vv, ext)

        # Download catchment
        HTTP_download(request, local, f)
        # unzip catchment file using winzip
        WinZip_unzip(local, f)
        # Pull catchments into gdb
        cat_folder = ID_folder + os.sep + f_comp
        cat_shp = cat_folder + os.sep + "Catchment.shp"
        local_catchment = local_gdb + os.sep + "Catchment"
        append_to_default(local_catchment, cat_shp, "catchment")

        # Assign flow table filename
        flow_f = "NHDPlusV21_{}_{}_{}_{}{}".format(DA, ID, ff_comp, ff_vv, ext)
        # Download flow table
        HTTP_download(request, local, flow_f)
        # Unzip flow table using winzip
        WinZip_unzip(local, flow_f)
        # Pull flow table into gdb
        flow_folder = ID_folder + os.sep + ff_comp
        flow_dbf = flow_folder + os.sep + "PlusFlow.dbf"
        local_flow = local_gdb + os.sep + "PlusFlow"
        append_to_default(local_flow, flow_dbf, "flow table")


def View_MODULE(PARAMS):
    """Scenic View Benefits"""
    start1 = time.clock()  # start the clock

    mod_str = "Scenic View Benefits analysis"
    message(mod_str + "...")

    addresses, popRast = PARAMS[0], PARAMS[1]
    trails, roads = PARAMS[2], PARAMS[3]
    wetlandsOri = PARAMS[4]
    landuse = PARAMS[5]
    field, fieldLst = PARAMS[6], PARAMS[7]
    outTbl = PARAMS[8]

    # Wetlands Dissolved
    path = os.path.dirname(outTbl) + os.sep
    wetlands_dis = path + "wetland_dis" + get_ext(outTbl)

    # 3.2 How Many Benefit
    start = time.clock()
    step_str = "3.2 How Many Benefit?"
    message(mod_str + " - " + step_str)

    # Create 50m buffer
    view50 = simple_buffer(outTbl, "int_ViewArea_50", "50 Meters")
    # Create 50m to 100m buffer
    view100 = buffer_donut(view50, "int_ViewArea_100", "50 Meters")

    # Calculate number benefitting in buffers
    if addresses is not None:  # address based method
        lst_view50 = buffer_contains(view50, addresses)
        lst_view100 = buffer_contains(view100, addresses)
        msg = "{} - {} (from addresses)".format(mod_str, step_str)

    elif popRast is not None:  # population based method
        lst_view50 = buffer_population(view50, popRast)
        lst_view100 = buffer_population(view100, popRast)
        msg = "{} - {} (from population raster)".format(mod_str, step_str)
    start = exec_time(start, msg)

    # Calculate weighted scores
    lst_view_scr = view_score(lst_view50, lst_view100)

    # Generate a complete 100m buffer and determine if trails/roads interstect
    view100_int = simple_buffer(outTbl, "int_ViewArea_100int", "100 Meters")
    # Generate a Yes/No list from trails and roads
    if trails is not None or roads is not None:
        rteLst = buffer_contains_multiset(trails, roads, view100_int)
    else:
        message("No roads or trails specified")
        rteLst = []

    msg = "{} - {} ".format(mod_str, step_str)
    start = exec_time(start, msg + "(from trails or roads)")
    start1 = exec_time(start1, msg + "Total")

    # 3.3.B Substitutes/Scarcity
    step_str = "3.3.B Scarcity"
    message(mod_str + " - " + step_str)

    if wetlandsOri is not None:
        # Make a 200m buffer that doesn't include the site
        view200 = buffer_donut(outTbl, "int_ViewArea_200", "200 Meters")

        # lyr input may speed this up
        del_exists(wetlands_dis)
        arcpy.Dissolve_management(wetlandsOri, wetlands_dis)
        wetlandsOri = wetlands_dis
        # Wetlands in 200m
        lst_3B = percent_cover(wetlandsOri, view200)
    else:
        message("No existing wetlands input specified")
        view200 = None
        lst_3B = []
    start = exec_time(start, "{} - {}".format(mod_str, step_str))

    # 3.3.C Complements
    step_str = "3.3.C Complements"
    message(mod_str + " - " + step_str)

    if landuse is not None:
        arcpy.MakeFeatureLayer_management(landuse, "lyr")
        # Construct query from field list
        whereClause = selectStr_by_list(field, fieldLst)
        sel = "NEW_SELECTION"
        # Reduce to desired LU
        arcpy.SelectLayerByAttribute_management("lyr", sel, whereClause)
        ext = get_ext(outTbl)
        out_name = os.path.splitext(os.path.basename(landuse))[0]
        landUse2 = path + out_name + "_comp" + ext
        del_exists(landUse2)
        arcpy.Dissolve_management("lyr", landUse2, field)  # reduce to unique
        arcpy.Delete_management("lyr")  # done with lyr

        # Number of unique LU in LU list which intersect each buffer
        if view200 is None:  # create if it doesn't already exist
            view200 = buffer_donut(outTbl, "int_ViewArea_200", "200 Meters")
        lst_comp = buffer_contains(view200, landUse2)
        start = exec_time(start, "{} - {}".format(mod_str, step_str))
    else:
        message("No land use input specified")
        landUse2 = None
        view200 = None
        lst_comp = []

    message("Saving {} results to Output...".format(mod_str))
    # FINAL STEP: move results to results file
    fields_lst = ["V_2_50", "V_2_100", "V_2_score", "V_2_boo",
                  "V_3A_boo", "V_3B_scar", "V_3C_comp", "V_3D_boo"]
    list_lst = [lst_view50, lst_view100, lst_view_scr, rteLst,
                [], lst_3B, lst_comp, []]
    type_lst = ["", "", "", "Text", "Text", "", "", "Text"]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, type_lst)

    # Cleanup
    deleteFC_Lst([view50, view100, view100_int, view200, wetlands_dis,
                  landUse2])

    message(mod_str + " complete")


def Edu_MODULE(PARAMS):
    """ Environmental Education Benefits"""
    start = time.clock()  # start the clock
    mod_str = "Environmental Education Benefits analysis"
    message(mod_str + "...")

    edu_inst = PARAMS[0]
    wetlandsOri = PARAMS[1]
    outTbl = PARAMS[2]

    # 3.2 How Many Benefit
    step_str = "3.2 How Many Benefit?"
    message(mod_str + " - " + step_str)

    if edu_inst is not None:
        edu_inst = checkSpatialReference(outTbl, edu_inst)  # check spatial ref
        # Buffer each site by 0.25 miles
        buf25 = simple_buffer(outTbl, "eduArea", "0.25 Miles")
        # List how many schools in buffer
        lst_edu_cnt = buffer_contains(buf25, edu_inst)
    else:
        message("No educational institutions specified")
        buf25 = None
        lst_edu_cnt = []
    msg = "{} - {} (Institutions)".format(mod_str, step_str)
    start = exec_time(start, msg)

    # 3.B Substitutes/Scarcity
    step_str = "3.3.B Scarcity"
    message(mod_str + " - " + step_str)

    if wetlandsOri is not None:
        # Buffer each site by 0.25 miles
        buf50 = simple_buffer(outTbl, "edu_2", "0.5 Miles")
        # Wetland scarcity in buffer
        lst_edu_33B = percent_cover(wetlandsOri, buf50)
    else:
        message("No pre-existing wetlands specified to determine scarcity")
        buf50 = None
        lst_edu_33B = []
    start = exec_time(start, "{} - {}".format(mod_str, step_str))

    # Final Step - move results to results file
    message("Saving {} results to Output...".format(mod_str))
    fields_lst = ["EE_2_cnt", "EE_3A_boo", "EE_3B_sca",
                  "EE_3C_boo", "EE_3D_boo"]
    list_lst = [lst_edu_cnt, [], lst_edu_33B, [], []]
    type_lst = ["", "Text", "", "Text", "Text"]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, type_lst)

    # Cleanup FC
    deleteFC_Lst([buf25, buf50])

    message(mod_str + " complete")


def Rec_MODULE(PARAMS):
    """Recreation Benefits"""
    start1 = time.clock()  # start the clock
    mod_str = "Recreation Benefits analysis"
    message(mod_str + "...")

    addresses, popRast = PARAMS[0], PARAMS[1]
    trails, bus_Stp = PARAMS[2], PARAMS[3]
    wetlandsOri = PARAMS[4]
    landuse = PARAMS[5]
    field, fieldLst = PARAMS[6], PARAMS[7]
    outTbl = PARAMS[8]

    # Dissolved landuse
    path = os.path.dirname(outTbl) + os.sep
    landuseTEMP = path + "landuse_temp" + get_ext(outTbl)

    # 3.2 How Many Benefit
    start = time.clock()
    step_str = "3.2 How Many Benefit?"
    message(mod_str + " - " + step_str)

    # Buffer each site by 500m, 1km, and 10km
    rec_500m = simple_buffer(outTbl, "recArea_03mi", "0.333333 Miles")  # walk
    rec_1000m = simple_buffer(outTbl, "recArea_05mi", "0.5 Miles")  # drive
    rec_10000m = buffer_donut(rec_1000m, "recArea_6mi", "5.5 Miles")  # drive

    # Overlay population
    if addresses is not None:  # address based method
        lst_rec_cnt_03 = buffer_contains(rec_500m, addresses)
        lst_rec_cnt_05 = buffer_contains(rec_1000m, addresses)
        lst_rec_cnt_6 = buffer_contains(rec_10000m, addresses)

        msg = "{} - {} (from addresses)".format(mod_str, step_str)
        start = exec_time(start, msg)

    elif popRast is not None:  # check for population raster
        lst_rec_cnt_03 = buffer_population(rec_500m, popRast)
        lst_rec_cnt_05 = buffer_population(rec_1000m, popRast)
        lst_rec_cnt_6 = buffer_population(rec_10000m, popRast)

        msg = "{} - {} (raster population)".format(mod_str, step_str)
        start = exec_time(start, msg)
    else:  # this should never happen
        message("Neither addresses or a population raster were found.")
        lst_rec_cnt_03, lst_rec_cnt_05, lst_rec_cnt_6 = [], [], []

    # Overlay trails
    if trails is not None:
        # Bike trails within 500m -> 'YES'
        lst_rec_trails = buffer_contains(rec_500m, trails)
        rLst_rec_trails = quant_to_qual_lst(lst_rec_trails)
    else:
        message("No trails specified for determining if there are bike " +
                "paths within 1/3 mi of site (R_2_03_tb)")
        rLst_rec_trails = []

    # Overlay bus stops
    if bus_Stp is not None:
        bus_Stp = checkSpatialReference(outTbl, bus_Stp)  # check projections
        lst_rec_bus = buffer_contains(rec_500m, bus_Stp)  # bus stops in 500m
        rLst_rec_bus = quant_to_qual_lst(lst_rec_bus)  # if there are = YES
    else:
        message("No bus stops specified for determining if there are bus " +
                "stops within 1/3 mi of site (R_2_03_bb)")
        rLst_rec_bus = []

    msg = "{} - {} ".format(mod_str, step_str)
    start = exec_time(start, msg + "(from trails and bus stops)")
    start1 = exec_time(start1, msg + "Total")

    # 3.3.A Service Quality
    step_str = "3.3.A Service Quality"
    message(mod_str + " - " + step_str)

    # Total area of green space around site ("R_3A_acr")
    lst_rec_3A = []
    if landuse is not None:
        # Reduce to desired LU
        WC1 = selectStr_by_list(field, fieldLst)  # WhereClause
        name = os.path.basename(landuseTEMP)
        del_exists(landuseTEMP)
        arcpy.FeatureClassToFeatureClass_conversion(landuse, path, name, WC1)
        # Make into selectable layer
        glyr = "greenLyr"
        arcpy.MakeFeatureLayer_management(landuseTEMP, glyr)

        with arcpy.da.SearchCursor(outTbl, ["SHAPE@"]) as cursor:
            for site in cursor:  # for each site
                # Start with site area
                var = dec(site[0].getArea("PLANAR", "ACRES"))
                # Select green space that intersects the site
                oTyp = "INTERSECT"  # Overlap Type
                arcpy.SelectLayerByLocation_management(glyr, oTyp, site[0])
                with arcpy.da.SearchCursor(glyr, ["SHAPE@"]) as cursor2:
                    for row in cursor2:
                        # Area of greenspace
                        areaGreen = dec(row[0].getArea("PLANAR", "ACRES"))
                        # Part of greenspace already in site
                        overlap = site[0].intersect(row[0], 4)
                        # Area of greenspace already in site
                        interArea = dec(overlap.getArea("PLANAR", "ACRES"))
                        # area of greenspace - overlap to site
                        var += areaGreen - interArea
                lst_rec_3A.append(var)
        arcpy.Delete_management(glyr)
    else:
        message("No landuse specified for determining area of green space " +
                "around site (R_3A_acr)")

    start = exec_time(start, "{} - {} ".format(mod_str, step_str))

    # 3.3.B Substitutes/Scarcity
    step_str = "3.3.B Scarcity"
    message(mod_str + " - " + step_str)

    # Green space within 2/3 mi, 1 mi and 12 mi of site
    if landuse is not None or wetlandsOri is not None:
        # Sub are greenspace or wetlands?
        if landuse is not None:
            subs = landuseTEMP
        else:
            if wetlandsOri is not None:
                subs = wetlandsOri
                message("No landuse input specified, existing wetlands used" +
                        " for scarcity instead")

        # Buffer each site by double original buffer
        rec_06 = simple_buffer(outTbl, 'recArea_Add_06mi', "0.666666 Miles")
        rec_1 = simple_buffer(outTbl, 'recArea_Add_1mi', "1 Miles")
        rec12 = simple_buffer(outTbl, 'recArea_Add_126mi', "12 Miles")

        # Overlay buffers with substitutes
        lst_rec06_3B = percent_cover(subs, rec_06)
        lst_rec1_3B = percent_cover(subs, rec_1)
        lst_rec12_3B = percent_cover(subs, rec12)
    else:
        message("No substitutes (landuse or existing wetlands) inputs" +
                " specified for recreation benefits.")
        rec_06, rec_1, rec12 = None, None, None
        lst_rec06_3B, lst_rec1_3B, lst_rec12_3B = [], [], []

    start = exec_time(start, "{} - {} ".format(mod_str, step_str))

    # Final Step - move results to results file
    message("Saving {} results to Output...".format(mod_str))
    fields_lst = ["R_2_03", "R_2_03_tb", "R_2_03_bb", "R_2_05", "R_2_6",
                  "R_3A_acr", "R_3B_sc06", "R_3B_sc1", "R_3B_sc12",
                  "R_3C_boo", "R_3D_boo"]
    list_lst = [lst_rec_cnt_03, rLst_rec_trails, rLst_rec_bus,
                lst_rec_cnt_05, lst_rec_cnt_6, lst_rec_3A,
                lst_rec06_3B, lst_rec1_3B, lst_rec12_3B, [], []]
    type_lst = ["", "Text", "Text", "", "", "", "", "", "", "Text", "Text"]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, type_lst)

    # Cleanup
    deleteFC_Lst([landuseTEMP, rec_500m, rec_1000m, rec_10000m,
                  rec_06, rec_1, rec12])

    message(mod_str + " complete")


def Bird_MODULE(PARAMS):
    """Bird Watching Benefits"""
    start = time.clock()  # start the clock
    mod_str = "Bird Watching Benefits analysis"
    message(mod_str + "...")

    addresses, popRast = PARAMS[0], PARAMS[1]
    trails, roads = PARAMS[2], PARAMS[3]
    outTbl = PARAMS[4]

    # 3.2 How Many Benefit
    step_str = "3.2 How Many Benefit?"
    message(mod_str + " - " + step_str)

    # Buffer sites by 0.2 miles.
    buf = simple_buffer(outTbl, "birdArea", "0.2 Miles")

    if addresses is not None:
        lst_bird_cnt = buffer_contains(buf, addresses)
        msg = "(from addresses)"
    elif popRast is not None:
        lst_bird_cnt = buffer_population(buf, popRast)
        msg = "(from population Raster)"
    start = exec_time(start, "{} - {} {}".format(mod_str, step_str, msg))

    # Are there roads or trails that could see birds on the site?
    if trails is not None or roads is not None:
        rteLstBird = buffer_contains_multiset(trails, roads, buf)
    else:
        message("No trails or roads specified to determine if birds at the " +
                "site will be visible from these")
        rteLstBird = []
    msg = "(from trails or roads)"
    start = exec_time(start, "{} - {} {}".format(mod_str, step_str, msg))

    # Final Step - move results to results file
    message("Saving {} results to Output...".format(mod_str))
    fields_lst = ["B_2_cnt", "B_2_boo", "B_3A_boo", "B_3C_boo", "B_3D_boo"]
    list_lst = [lst_bird_cnt, rteLstBird, [], [], []]
    type_lst = ["", "Text", "Text", "Text", "Text"]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, type_lst)

    arcpy.Delete_management(buf)

    message(mod_str + " complete")


def socEq_MODULE(PARAMS):
    """Social Equity of Benefits"""
    mod_str = "Social Equity of Benefits analysis"
    message(mod_str + "...")

    sovi = PARAMS[0]
    field, SoVI_High = PARAMS[1], PARAMS[2]
    bufferDist = PARAMS[3]
    outTbl = PARAMS[4]

    message("Checking input variables...")
    sovi = checkSpatialReference(outTbl, sovi)  # check projection
    message("Input variables OK")

    # Buffer sites by specified distance
    buf = simple_buffer(outTbl, "sovi_buffer", bufferDist)

    # List all the unique values in the specified field
    arcpy.MakeFeatureLayer_management(sovi, "lyr")
    full_fieldLst = unique_values("lyr", field)

    # Add field for SoVI_High
    name = "Vul_High"
    f_type = "DOUBLE"
    if not field_exists(outTbl, name):
        arcpy.AddField_management(outTbl, name, f_type,
                                  "", "", "", "", "", "", "")
    else:
        message("'{}' values overwritten in table:\n{}".format(name, outTbl))

    # Populate new field
    sel = "NEW_SELECTION"
    wClause = selectStr_by_list(field, SoVI_High)
    arcpy.SelectLayerByAttribute_management("lyr", sel, wClause)
    pct_lst = percent_cover("lyr", buf)
    lst_to_field(outTbl, name, pct_lst)

    # Add fields for the rest of the possible values if 6 or less
    fieldLst = [x for x in full_fieldLst if x not in SoVI_High]
    message("There are {} unique values for '{}'".format(len(fieldLst), field))
    if len(fieldLst) < 6:
        message("Creating new fields for each...")
        # Add fields for each unique in field
        for val in fieldLst:
            name = fieldName("sv_" + str(val))
            if not field_exists(outTbl, name):
                arcpy.AddField_management(outTbl, name, f_type, "", "", "",
                                          val, "", "", "")
            else:  # field already existed
                message("'{}' values overwritten in table:\n{}".format(name,
                                                                       outTbl))
            wClause = selectStr_by_list(field, [val])
            arcpy.SelectLayerByAttribute_management("lyr", sel, wClause)
            pct_lst = percent_cover("lyr", buf)
            lst_to_field(outTbl, name, pct_lst)
    else:
        message("This is too many values to create unique fields for each, " +
                "just calculating {} coverage".format(SoVI_High))

    arcpy.Delete_management(buf)
    arcpy.Delete_management("lyr")
    message(mod_str + " complete")


def reliability_MODULE(PARAMS):
    """Reliability of Benefits"""
    # start = time.clock() #start the clock
    mod_str = "Reliability of Benefits analysis"
    message(mod_str + "...")

    cons_poly = PARAMS[0]
    field = PARAMS[1]
    consLst, threatLst = PARAMS[2], PARAMS[3]
    bufferDist = PARAMS[4]
    outTbl = PARAMS[5]

    message("Checking input variables...")
    # Remove None/0 from lists
    if consLst is not None:
        consLst = [x for x in consLst if x is not None]
        threatLst = [x for x in threatLst if x is not None]
        cons_poly = checkSpatialReference(outTbl, cons_poly)
        message("Input variables OK")
    else:
        message("Reliability inputs failed: no Conservation Types selected")

    # Buffer site by user specified distance
    buf = simple_buffer(outTbl, "conservation", bufferDist)

    # Make selection from FC based on fields to include
    sel = "NEW_SELECTION"
    arcpy.MakeFeatureLayer_management(cons_poly, "lyr")
    whereClause = selectStr_by_list(field, consLst)
    arcpy.SelectLayerByAttribute_management("lyr", sel, whereClause)
    # Determine percent of buffer which is each conservation type
    pct_consLst = percent_cover("lyr", buf)
    try:
        # Make list based on threat use types
        whereThreat = selectStr_by_list(field, threatLst)
        arcpy.SelectLayerByAttribute_management("lyr", sel, whereThreat)
        pct_threatLst = percent_cover("lyr", buf)
    except Exception:
        message("Error occured determining percent non-conserved areas.", 1)
        traceback.print_exc()
        pass

    # Final Step - move results to results file
    message("Saving {} results to 'Conserved' in Output...".format(mod_str))
    fields_lst = ["Conserved", "Threatene"]
    list_lst = [pct_consLst, pct_threatLst]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, ["", ""])

    arcpy.Delete_management(buf)
    arcpy.Delete_management("lyr")
    message(mod_str + " complete")


def Report_MODULE(PARAMS):
    """Report Generation"""
    start = time.clock()  # start the clock
    message("Generating report...")
    # Report_PARAMS = [outTbl, siteName, mxd, pdf]

    outTbl = PARAMS[0]
    siteNameFld = str(PARAMS[1])
    mxd = arcpy.mapping.MapDocument(PARAMS[2])
    # Set file name, ext, and remove file if it already exists
    pdf = PARAMS[3]
    if os.path.splitext(pdf)[1] == "":
        pdf += ".pdf"
    if os.path.exists(pdf):
        os.remove(pdf)
    # Set path for intermediate pdfs
    pdf_path = os.path.dirname(pdf) + os.sep

    # Create the file and append pages in the cursor loop
    pdfDoc = arcpy.mapping.PDFDocumentCreate(pdf)

    graphic = "GRAPHIC_ELEMENT"
    blackbox = arcpy.mapping.ListLayoutElements(mxd, graphic, "blackbox")[0]
    graybox = arcpy.mapping.ListLayoutElements(mxd, graphic, "graybox")[0]

    # dictionary for field, type, ltorgt, numDigits, allnos, & average
    fld_dct = {'field': ['FR_2_cnt', 'FR_3A_acr', 'FR_3A_boo', 'FR_3B_boo',
                         'FR_3B_sca', 'FR_3D_boo', 'V_2_50', 'V_2_100',
                         'V_2_score', 'V_2_boo', 'V_3A_boo', 'V_3B_scar',
                         'V_3C_comp', 'V_3D_boo', 'EE_2_cnt', 'EE_3A_boo',
                         'EE_3B_sca', 'EE_3C_boo', 'EE_3D_boo', 'R_2_03',
                         'R_2_03_tb', 'R_2_03_bb', 'R_2_05', 'R_2_6',
                         'R_3A_acr', 'R_3B_sc06', 'R_3B_sc1', 'R_3B_sc12',
                         'R_3C_boo', 'R_3D_boo', 'B_2_cnt', 'B_2_boo',
                         'B_3A_boo', 'B_3C_boo', 'B_3D_boo', 'Vul_High',
                         'Conserved']}
    txt, dbl = 'Text', 'Double'
    fld_dct['type'] = [dbl, dbl, txt, txt, dbl, txt, dbl, dbl, dbl, txt, txt,
                       dbl, dbl, txt, dbl, txt, dbl, txt, txt, dbl, txt,
                       txt, dbl, dbl, dbl, dbl, dbl, dbl, txt, txt, dbl,
                       txt, txt, txt, txt, dbl, dbl]
    fld_dct['ltorgt'] = ['gt', 'gt', '', '', 'lt', '', 'gt', 'gt', 'gt', '',
                         '', 'lt', 'gt', '', 'gt', '', 'lt', '', '', 'gt', '',
                         '', 'gt', 'gt', 'gt', 'lt', 'lt', 'lt', '', '', 'gt',
                         '', '', '', '', 'gt', 'gt']
    fld_dct['aveBool'] = ['', '', 'YES', 'NO', '', 'YES', '', '', '', 'YES',
                          'YES', '', '', 'YES', '', 'YES', '', 'YES', 'YES',
                          '', 'YES', 'YES', '', '', '', '', '', '', 'YES',
                          'YES', '', 'YES', 'YES', 'YES', 'YES', '', '']
    fld_dct['numDigits'] = [0, 2, 0, 0, 2, 0, 0, 0, 1, 0, 0,
                            1, 0, 0, 0, 0, 1, 0, 0, 0, 0,
                            0, 0, 0, 0, 1, 1, 1, 0, 0, 0,
                            0, 0, 0, 0, 2, 2]
    fld_dct['rowNum'] = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12,
                         13, 14, 15, 16, 17, 18, 19, 20, 21, 22,
                         23, 24, 25, 26, 27, 28, 29, 30, 31, 32,
                         33, 34, 36, 37, 38, 39]
    fld_dct['allnos'] = [''] * 37
    fld_dct['average'] = [''] * 37

    # Make table layer from results table
    arcpy.MakeTableView_management(outTbl, "rptbview")
    desc = arcpy.Describe("rptbview")
    fieldInfo = desc.fieldInfo
    cnt_rows = str(arcpy.GetCount_management(outTbl))

    for field in fld_dct['field']:  # loop through fields
        idx = fld_dct['field'].index(field)
        # Check to see if field exists in results
        fldIndex = fieldInfo.findFieldByName(fld_dct['field'][idx])
        if fldIndex > 0:  # exists
            if fld_dct['type'][idx] == 'Text':  # narrow to yes/no
                # Copy text field to list by field index
                fld_dct[idx] = field_to_lst(outTbl, field)
                # Check if all 'NO'
                if fld_dct[idx].count("NO") == int(cnt_rows):
                    fld_dct['allnos'][idx] = 1
            else:  # type = Double
                l = [x for x in field_to_lst(outTbl, field) if x is not None]
                if l != []:  # if not all null
                    # Get average values
                    fld_dct['average'][idx] = mean(l)

    start = exec_time(start, "loading data for report")

    i = 1
    pg_cnt = 1
    siterows = arcpy.SearchCursor(outTbl, "")  # may be slow, use "rptbview"?
    siterow = siterows.next()

    while siterow:

        oddeven = i % 2
        if oddeven == 1:
            column = 1
            siteText = "SiteLeftText"
            site_Name = "SiteLeftName"
        else:
            column = 2
            siteText = "SiteRightText"
            site_Name = "SiteRightName"
        TE = "TEXT_ELEMENT"
        siteText = arcpy.mapping.ListLayoutElements(mxd, TE, siteText)[0]
        siteText.text = "Site " + str(i)

        # Text element processing
        siteName = arcpy.mapping.ListLayoutElements(mxd, TE, site_Name)[0]
        fldNameValue = "siterow." + siteNameFld
        if fieldInfo.findFieldByName(siteNameFld) > 0:
            if eval(fldNameValue) == ' ':
                siteName.text = "No name"
            else:
                siteName.text = eval(fldNameValue)
        else:
            siteName.text = "No name"

        # loop through expected fields in fld_dct['field']
        for field in fld_dct['field']:
            idx = fld_dct['field'].index(field)
            # Check to see if field exists in results
            # if it doesn't color = black
            if fldExists(field, column, fld_dct['rowNum'][idx], fieldInfo, blackbox):
                fldVal = "siterow." + field
                if fld_dct['type'][idx] == 'Double':  # is numeric
                    proctext(eval(fldVal), "Num", fld_dct['numDigits'][idx],
                             fld_dct['ltorgt'][idx], fld_dct['average'][idx],
                             column, fld_dct['rowNum'][idx],
                             fld_dct['allnos'][idx], mxd)
                else:  # is boolean
                    proctext(eval(fldVal), "Boolean", 0,
                             "", fld_dct['aveBool'][idx],
                             column, fld_dct['rowNum'][idx],
                             fld_dct['allnos'][idx],mxd)
        if oddeven == 0:
            exportReport(pdfDoc, pdf_path, pg_cnt, mxd)
            start = exec_time(start, "Page " + str(pg_cnt) + " generation")
            pg_cnt += 1

        i += 1
        siterow = siterows.next()

    # If you finish a layer with an odd number of records,
    # last record was not added to the pdf.
    if oddeven == 1:
        # Blank out right side
        siteText = arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT",
                                                    "SiteRightText")[0]
        siteText.text = " "
        # Fill right side with gray empty boxes
        for i in range(39):
            # Not set up to process the Social Equity or Reliability scores
            newBox = graybox.clone("_clone")
            boxpos(newBox, 2, i + 1)
        exportReport(pdfDoc, pdf_path, pg_cnt, mxd)

    del siterow
    del siterows

    arcpy.Delete_management("rptbview", "")

    pdfDoc.saveAndClose()

    mxd_result = os.path.splitext(pdf)[0] + ".mxd"
    if arcpy.Exists(mxd_result):
        arcpy.Delete_management(mxd_result)

    mxd.saveACopy(mxd_result)  # save last page just in case

    del mxd
    del pdfDoc
    mxd_name = os.path.basename(mxd_result)
    message("Created PDF report: {} and {}".format(pdf, mxd_name))


def absTest_MODULE(PARAMS):
    """Presence Absence Test"""

    outTbl, field = PARAMS[0], PARAMS[1]
    FC = PARAMS[2]
    buff_dist = PARAMS[3]

    # Check spatial ref
    FC = checkSpatialReference(outTbl, FC)

    # Create buffers for each site by buff_dist.
    buf = simple_buffer(outTbl, "feature_buffer", buff_dist)

    # If feature not present "NO", else "YES"
    booleanLst = quant_to_qual_lst(buffer_contains(buf, FC))

    # Move results to outTbl.field
    lst_to_AddField_lst(outTbl, [field], [booleanLst], ["Text"])
    arcpy.Delete_management(buf)


def main(params):
    """Main"""
    start = time.clock()  # start the clock
    start1 = time.clock()  # start the 2nd clock
    blank_warn = " some fields may be left blank for selected benefits."

    message("Loading Variables...")
    # params = [sites, addresses, popRast, flood, view, edu, rec, bird, socEq,
    #          rel, flood_zone, dams, edu_inst, bus_stp, trails, roads,
    #          OriWetlands, landUse, LULC_field, landVal, socVul, soc_Field,
    #          socVal, conserve, conserve_Field, useVal, outTbl, pdf]
    ck = []
    for i in range(3, 10):
        ck.append(params[i].value)
    flood, view, edu, rec, bird = ck[0], ck[1], ck[2], ck[3], ck[4]
    socEq, rel = ck[5], ck[6]

    sites = params[0].valueAsText
    addresses = params[1].valueAsText
    popRast = params[2].valueAsText

    flood_zone = params[10].valueAsText
    subs = params[11].valueAsText
    edu_inst = params[12].valueAsText
    bus_Stp = params[13].valueAsText
    trails = params[14].valueAsText
    roads = params[15].valueAsText
    OriWetlands = params[16].valueAsText

    landuse = params[17].valueAsText
    field = params[18].valueAsText
    fieldLst = params[19].values
    if fieldLst is not None:
        # Coerce/map unicode list using field in table
        typ = tbl_fieldType(landuse, field)
        fieldLst = ListType_fromField(typ, fieldLst)
    else:  # no greenspace list
        message("No greenspace field values specified")

    sovi = params[20].valueAsText
    sovi_field = params[21].valueAsText
    sovi_High = params[22].values
    if sovi_High is not None:
        # Coerce/map unicode list using field in table
        typ = tbl_fieldType(sovi, sovi_field)
        sovi_High = ListType_fromField(typ, sovi_High)
    else:  # no svi list
        message("Social Equity of benefits will not be assessed")
        socEq = None

    conserved = params[23].valueAsText
    rel_field = params[24].valueAsText
    cons_fLst = params[25].values
    if cons_fLst is not None:
        # Convert unicode lists to field.type
        typ = tbl_fieldType(conserved, rel_field)
        cons_fLst = ListType_fromField(typ, cons_fLst)
        # All values from rel_field not in cons_fLst
        uq_lst = unique_values(conserved, rel_field)
        threat_fieldLst = [x for x in uq_lst if x not in cons_fLst]
    else:  # no reliability value list
        message("Reliability of benefits will not be assessed")
        rel = None

    outTbl = params[26].valueAsText
    pdf = params[27].valueAsText

    # DEFAULTS
    # set buffers based on inputs
    if socEq is True:
        buff_dist = SocEqu_BuffDist(ck[0:5])
        message("Default buffer distance of {} used".format(buff_dist) +
                " for Social Equity")
    if rel is True:
        rel_buff_dist = "500 Feet"
        message("Default buffer distance of {} used".format(rel_buff_dist) +
                " for Benefit Reliability")

    # Package dir path (based on where this file is)
    script_dir = os.path.dirname(os.path.realpath(__file__)) + os.sep
    # Check for report layout file
    if pdf is not None:
        mxd_name = "report_layout.mxd"
        mxd = script_dir + mxd_name
        if arcpy.Exists(mxd):
            message("Using " + mxd + " report layout file")
        else:
            message("Default report layout file not available in expected" +
                    "location:\n{}".format(mxd))
            message("A PDF report will not be generated from results")
            pdf = None

    # Copy restoration wetlands in for results
    create_outTbl(sites, outTbl)

    start1 = exec_time(start1, "loading variables")
    message("Checking input variables...")
    BA = "Benefit assessment"
    # Check spatial references for inputs
    # All require pop except edu
    if True in [flood, view, rec, bird]:
        addresses, popRast = check_vars(outTbl, addresses, popRast)
    # Trails
    if True in [view, bird, rec]:
        if trails is not None:
            trails = checkSpatialReference(outTbl, trails)
            message("Trails input OK")
        else:
            message("Trails input not specified, " + blank_warn)
    # Roads
        if roads is not None:
            roads = checkSpatialReference(outTbl, roads)
            message("Roads input OK")
        else:
            message("Roads input not specified, " + blank_warn)

    # Benefits requiring existing wetlands
    if True in [flood, view, edu, rec]:
        if OriWetlands is not None:  # if the dataset is specified
            # Check spatial ref
            OriWetlands = checkSpatialReference(outTbl, OriWetlands)
            message("Existing wetlands OK")
        else:
            message("Existings wetlands input not specified, " + blank_warn)
    # Benefits using landuse
    if True in [view, rec]:
        if landuse is not None:
            landuse = checkSpatialReference(outTbl, landuse)
            message("Landuse polygons OK")
        else:
            message("Landuse input not specified, " + blank_warn)
    # Message/time:
    start1 = exec_time(start1, "verify inputs")
    message("Running selected benefit modules...")

    # Run modules based on inputs
    if flood is True:
        Flood_PARAMS = [addresses, popRast, flood_zone, OriWetlands, subs,
                        None, None, None, outTbl]
        try:
            FR_MODULE(Flood_PARAMS)
        # Geoprocessing errors
        except Exception as e:
            message(e.message, 1)
            message("Reduced Flood Risk Indicators will not be calculated.", 1)
        start1 = exec_time(start1, "Flood Risk " + BA)
    else:  # create and set all fields to none?
        message("Flood Risk Benefits not assessed")

    if view is True:
        View_PARAMS = [addresses, popRast, trails, roads, OriWetlands, landuse,
                       field, fieldLst, outTbl]
        View_MODULE(View_PARAMS)
        start1 = exec_time(start1, "Scenic View " + BA)
    else:  # create and set all fields to none?
        message("Scenic View Benefits not assessed")

    if edu is True:
        EDU_PARAMS = [edu_inst, OriWetlands, outTbl]
        Edu_MODULE(EDU_PARAMS)
        start1 = exec_time(start1, "Environmental Education " + BA)
    else:  # create and set all fields to none?
        message("Environmental Education Benefits not assessed")

    if rec is True:
        REC_PARAMS = [addresses, popRast, trails, bus_Stp, OriWetlands,
                      landuse, field, fieldLst, outTbl]
        Rec_MODULE(REC_PARAMS)
        start1 = exec_time(start1, "Recreation " + BA)
    else:  # create and set all fields to none?
        message("Recreation Benefits not assessed")

    if bird is True:
        Bird_PARAMS = [addresses, popRast, trails, roads, outTbl]
        Bird_MODULE(Bird_PARAMS)
        start1 = exec_time(start1, "Bird Watching " + BA)
    else:  # create and set all fields to none?
        message("Bird Watching Benefits not assessed")

    if socEq is True:
        soc_PARAMS = [sovi, sovi_field, sovi_High, buff_dist, outTbl]
        socEq_MODULE(soc_PARAMS)
        start1 = exec_time(start1, "Social Equity assessment")
    else:  # create and set all fields to none?
        message("Social Equity of Benefits not assessed")

    if rel is True:
        Rel_PARAMS = [conserved, rel_field, cons_fLst, threat_fieldLst,
                      rel_buff_dist, outTbl]
        reliability_MODULE(Rel_PARAMS)
        start1 = exec_time(start1, "Reliability assessment")
    else:  # create and set all fields to none?
        message("Reliability of Benefits not assessed")

    if pdf is not None:
        # siteName defaults to OID unless there is a field named "siteName"
        lstFields = arcpy.ListFields(outTbl)
        siteName = find_ID(outTbl)
        for fld in lstFields:
            if fld.name == "siteName":
                siteName = fld.name
        Report_PARAMS = [outTbl, siteName, mxd, pdf]
        Report_MODULE(Report_PARAMS)
        start1 = exec_time(start1, "Compiling assessment report")
    else:
        message("pdf Report not generated")

    start = exec_time(start, "complete " + BA)


class Toolbox(object):
    def __init__(self):
        self.label = "RBI Spatial Analysis Tools"
        self.alias = "RBI"
        # List of tool classes associated with this toolbox
        self.tools = [Full_Indicator_Tool, FloodTool, Report, reliability,
                      socialVulnerability, presence_absence,
                      FloodDataDownloader]


class presence_absence(object):
    def __init__(self):
        self.label = "Part - Presence/Absence to Yes/No"
        self.description = "Use the presence or absence of some spatial" + \
                           " feature within a range of the site to" + \
                           " determine if that metric is YES or NO"

    def getParameterInfo(self):
        sName = "Restoration Site Polygons (Required)"
        sites = setParam(sName, "in_poly", "", "", "")
        # Field in outTbl
        field = setParam("Field Name", "siteFld", "Field", "", "")
        FC = setParam("Features", "feat", "", "", "")
        buff_dist = setParam("Buffer Distance", "bufferUnits", "GPLinearUnit",
                             "", "")

        outTbl = setParam("Output", "outTable", "DEFeatureClass", "", "Output")

        field.parameterDependencies = [sites.name]

        params = [sites, field, FC, buff_dist, outTbl]
        return params

    def isLicensed(self):
        return True

    def updateParameters(self, params):
        return

    def updateMessages(self, params):
        return

    def execute(self, params, messages):
        start1 = time.clock()  # start the clock

        sites = params[0].valueAsText
        field = params[1].valueAsText
        FC = params[2].valueAsText
        buff_dist = params[3].valueAsText
        outTbl = params[4].valueAsText

        create_outTbl(sites, outTbl)

        abs_test_PARAMS = [outTbl, field, FC, buff_dist]
        absTest_MODULE(abs_test_PARAMS)
        start1 = exec_time(start1, "Presence/Absence assessment")


class socialVulnerability (object):
    def __init__(self):
        self.label = "Part - Social Equity of Benefits"
        self.description = "Assess the social vulnerability of those" + \
                           " benefitting to identify social equity issues."

    def getParameterInfo(self):
        sName = "Restoration Site Polygons (Required)"
        sites = setParam(sName, "in_poly", "", "", "")
        poly = setParam("Social Vulnerability", "soc_vul_poly", "", "", "")
        poly_field = setParam("Vulnerability Field", "soc_field", "Field",
                              "", "")
        field_value = setParam("Vulnerable Field Values", "soc_field_val",
                               "GPString", "", "", True)
        buff_dist = setParam("Buffer Distance", "bufferUnits", "GPLinearUnit",
                             "", "")
        outTbl = setParam("Output", "outTable", "DEFeatureClass", "", "Output")

        # Disable params until source available
        disableParamLst([poly_field, field_value])
        poly_field.parameterDependencies = [poly.name]
        field_value.parameterDependencies = [poly_field.name]
        field_value.filter.type = 'ValueList'

        params = [sites, poly, poly_field, field_value, buff_dist, outTbl]
        return params

    def isLicensed(self):
        return True

    def updateParameters(self, params):
        # Social vulnerability inputs
        if params[1].altered:
            params[2].enabled = True
        if params[2].altered:  # socVul_field
            in_poly = params[1].valueAsText
            TypeField = params[2].valueAsText
            params[3].enabled = True
            params[3].filter.list = unique_values(in_poly, TypeField)
        return

    def updateMessages(self, params):
        return

    def execute(self, params, messages):
        start1 = time.clock()  # start the clock

        sites = params[0].valueAsText
        outTbl = params[5].valueAsText

        create_outTbl(sites, outTbl)

        sovi = params[1].valueAsText
        sovi_field = params[2].valueAsText
        sovi_High = params[3].values
        buff_dist = params[4].valueAsText

        if sovi_High is not None:
            # Coerce/map unicode list using field in table
            sovi_High = ListType_fromField(tbl_fieldType(sovi, sovi_field),
                                           sovi_High)

        soc_PARAMS = [sovi, sovi_field, sovi_High, buff_dist, outTbl]
        socEq_MODULE(soc_PARAMS)
        start1 = exec_time(start1, "Social Equity assessment")


class reliability (object):
    def __init__(self):
        self.label = "Part - Benefit Reliability"
        self.description = "Assess the site's ability to produce services " + \
                           "and provide benefits into the future."

    def getParameterInfo(self):
        sName = "Restoration Site Polygons (Required)"
        sites = setParam(sName, "in_poly", "", "", "")
        poly = setParam("Conservation Lands", "cons_poly", "", "", "")
        poly_field = setParam("Conservation Field", "Conservation_Field",
                              "Field", "", "")
        in_lst = setParam("Conservation Types", "Conservation_Type",
                          "GPString", "", "", True)
        buff_dist = setParam("Buffer Distance", "bufferUnits", "GPLinearUnit",
                             "", "")
        outTbl = setParam("Output", "outTable", "DEFeatureClass", "", "Output")

        # Disable until source available
        disableParamLst([poly_field, in_lst])
        poly_field.parameterDependencies = [poly.name]
        in_lst.parameterDependencies = [poly_field.name]
        in_lst.filter.type = 'ValueList'

        params = [sites, poly, poly_field, in_lst, buff_dist, outTbl]
        return params

    def isLicensed(self):
        return True

    def updateParameters(self, params):
        if params[1].altered:
            params[2].enabled = True
        if params[2].altered:  # socVul_field
            in_poly = params[1].valueAsText
            TypeField = params[2].valueAsText
            params[3].enabled = True
            params[3].filter.list = unique_values(in_poly, TypeField)
        return

    def updateMessages(self, params):
        return

    def execute(self, params, messages):
        start1 = time.clock()  # start the clock
        sites = params[0].valueAsText
        outTbl = params[5].valueAsText

        create_outTbl(sites, outTbl)

        conserved = params[1].valueAsText
        field = params[2].valueAsText
        cons_fieldLst = params[3].values
        buff_dist = params[4].valueAsText

        if cons_fieldLst is not None:
            # Convert unicode lists to field.type
            typ = tbl_fieldType(conserved, field)
            cons_fieldLst = ListType_fromField(typ, cons_fieldLst)
            # All values from rel_field not in cons_fieldLst
            uq_vals = unique_values(conserved, field)
            threat_fieldLst = [x for x in uq_vals if x not in cons_fieldLst]

        Rel_PARAMS = [conserved, field, cons_fieldLst, threat_fieldLst,
                      buff_dist, outTbl]
        try:
            reliability_MODULE(Rel_PARAMS)
            start1 = exec_time(start1, "Reliability assessment")
        except Exception:
            message("Error occured during Reliability assessment.", 1)
            traceback.print_exc()


class Report (object):
    def __init__(self):
        self.label = "Part - Report Generation"
        self.description = "Tool to create formated summary pdf report of" + \
                           " indicator results"

    def getParameterInfo(self):
        outTbl = setParam("Results Table", "outTable", "", "", "")
        siteName = setParam("Site Names Field", "siteNameField", "Field", "",
                            "")
        siteName.enabled = False
        mxd = setParam("Mapfile with report layout", "mxd", "DEMapDocument",
                       "", "")
        pdf = setParam("pdf Report", "outReport", "DEFile", "", "Output")

        siteName.parameterDependencies = [outTbl.name]

        params = [outTbl, siteName, mxd, pdf]
        return params

    def isLicensed(self):
        return True

    def updateParameters(self, params):
        if params[0].value is not None:
            params[1].enabled = True
        else:
            params[1].enabled = False
        return

    def updateMessages(self, params):
        return

    def execute(self, params, messages):
        start1 = time.clock()  # start the clock

        outTbl = params[0].valueAsText
        siteName = params[1].valueAsText
        mxd = params[2].valueAsText
        pdf = params[3].valueAsText

        Report_PARAMS = [outTbl, siteName, mxd, pdf]
        Report_MODULE(Report_PARAMS)
        start1 = exec_time(start1, "Compile assessment report")


class FloodTool (object):
    def __init__(self):
        self.label = "Part - Flood Risk Reduction "
        self.description = "This tool assesses Flood Risk Reduction Benefits"

    def getParameterInfo(self):
        # Define IN/OUT parameters
        sites = setParam("Restoration Site Polygons (Required)", "in_poly", "",
                         "", "")
        addresses = setParam("Address Points", "in_pnts", "", "Optional", "")
        popRast = setParam("Population Raster", "popRast", "DERasterDataset",
                           "Optional", "")

        flood_zone = setParam("Flood Zone Polygons", "flood_zone", "", "", "")
        dams = setParam("Dams/Levee", "flood_sub", "", "", "")
        OriWetlands = setParam("Wetland Polygons", "in_wet", "", "", "")
        catchment = setParam("Catchments", "NHD_catchment", "",
                             "Optional", "")
        FloodField = setParam("Catchment Join Field", "inputField", "Field",
                              "Optional", "")
        relateTable = setParam("Flow Table", "Flow", "GPTableView",
                               "Optional", "")
        outTbl = setParam("Output", "outTable", "DEFeatureClass", "", "Output")

        # Set field values based on catchment fields
        FloodField.parameterDependencies = [catchment.name]

        params = [sites, addresses, popRast, flood_zone, dams, OriWetlands,
                  catchment, FloodField, relateTable, outTbl]
        return params

    def isLicensed(self):
        return True

    def updateParameters(self, params):
        # Take only addresses or raster
        if params[1].value is not None:
            params[2].enabled = False
        else:
            params[2].enabled = True
        if params[2].value is not None:
            params[1].enabled = False
        else:
            params[1].enabled = True
        #field selected from catchment table
        if params[6].value is not None:
            params[7].enabled = True
        else:
            params[7].enabled = False
        return

    def updateMessages(self, params):
        return

    def execute(self, params, messages):
        start1 = time.clock()  # start the clock
        sites = params[0].valueAsText
        outTbl = params[9].valueAsText

        addresses = params[1].valueAsText
        popRast = params[2].valueAsText

        flood_zone = params[3].valueAsText
        subs = params[4].valueAsText
        OriWetlands = params[5].valueAsText
        catchment = params[6].valueAsText
        inputField = params[7].valueAsText
        rel_Tbl = params[8].valueAsText

        create_outTbl(sites, outTbl)
        # Check spatial ref
        addresses, popRast = check_vars(outTbl, addresses, popRast)

        if OriWetlands is not None:  # if the dataset is specified
            # Check spatial ref
            OriWetlands = checkSpatialReference(outTbl, OriWetlands)
            message("Existing wetlands OK")
        else:
            message("Existing wetlands input not specified, some fields " +
                    "may be left blank for selected benefits.")

        Flood_PARAMS = [addresses, popRast, flood_zone, OriWetlands, subs,
                        catchment, inputField, rel_Tbl, outTbl]
        FR_MODULE(Flood_PARAMS)
        start1 = exec_time(start1, "Flood Risk benefit assessment")


class FloodDataDownloader(object):
    def __init__(self):
        self.label = "Part - Flood Data Download"
        self.description = "Download NHD Plus data. Requires web access."

    def getParameterInfo(self):
        sName = "Restoration Site Polygons (Required)"
        sites = setParam(sName, "in_poly", "", "", "")
        # NHDPlus boundaries
        NHD_VUB = setParam("NHD Plus Vector Processing Unit", "VUB", "",
                           "Optional", "")
        # Location to save catchments
        local = setParam("Download Folder", "outTable", "DEFeatureClass",
                         "Optional", "Output")

        params = [sites, NHD_VUB, local]
        return params

    def isLicensed(self):
        return True

    def updateParameters(self, params):
        return

    def updateMessages(self, params):
        return

    def execute(self, params, messages):
        start = time.clock()  # start the clock

        sites = params[0].valueAsText
        NHD_VUB = params[1].valueAsText
        local = params[2].valueAsText

        NHD_PARAMS = [sites, NHD_VUB, local]
        NHD_get_MODULE(NHD_PARAMS)

        start = exec_time(start, "Downloading NHD Plus Stream Data")


class Full_Indicator_Tool (object):
    def __init__(self):
        self.label = "Full Indicator Assessment"
        self.description = "This tool performs the Tier 1 Indicators" + \
                           " assessment on a desired set of wetlands" + \
                           " or wetlands restoration sites."

    def getParameterInfo(self):
        # Define IN/OUT parameters
        opt = "Optional"
        GP_s = "GPString"
        GP_b = "GPBoolean"
        fld = "Field"
        sName = "Restoration Site Polygons (Required)"
        sites = setParam(sName, "in_poly", "", "", "")
        addresses = setParam("Address Points", "in_pnts", "", opt, "")
        popRast = setParam("Population Raster", "popRast", "DERasterDataset",
                           opt, "")
        # Check boxes for services the user wants to assess
        # flood, view, edu, rec, bird, socEq, rel = True
        serviceLst = ["Reduced Flood Risk", "Scenic Views",
                      "Environmental Education", "Recreation",
                      "Bird Watching", "Social Equity", "Reliability"]
        flood = setParam(serviceLst[0], "flood", GP_b, opt, "")
        view = setParam(serviceLst[1], "view", GP_b, opt, "")
        edu = setParam(serviceLst[2], "edu", GP_b, opt, "")
        rec = setParam(serviceLst[3], "rec", GP_b, opt, "")
        bird = setParam(serviceLst[4], "bird", GP_b, opt, "")
        socEq = setParam(serviceLst[5], "socEq", GP_b, opt, "")
        rel = setParam(serviceLst[6], "rel", GP_b, opt, "")

        flood_zone = setParam("Flood Zone Polygons", "flood_zone", "", opt, "")
        dams = setParam("Dams/Levees", "flood_sub", "", opt, "")
        edu_inst = setParam("Educational Institution Points",
                            "edu_inst", "", opt, "")
        bus_stp = setParam("Bus Stop Points",
                           "bus_stp", "", opt, "")
        trails = setParam("Trails (hiking, biking, etc.)",
                          "trails", "", opt, "")
        roads = setParam("Roads (streets, highways, etc.)",
                         "roads", "", opt, "")
        OriWetlands = setParam("Wetland Polygons", "in_wet", "", opt, "")

        landUse = setParam("Landuse/Greenspace Polygons",
                           "land_use", "", opt, "")
        LULC_field = setParam("Greenspace Field", "LULCFld", fld, opt, "")
        landVal = setParam("Greenspace Field Values",
                           "grn_field_val", GP_s, opt, "", True)

        socVul = setParam("Social Vulnerability", "soc_vul_poly", "", opt, "")
        soc_Field = setParam("Vulnerability Field",
                             "soc_field", fld, opt, "")
        socVal = setParam("Vulnerable Field Values",
                          "soc_field_val", GP_s, opt, "", True)

        conserve = setParam("Conservation Lands", "cons_poly", "", opt, "")
        conserve_Field = setParam("Conservation Field",
                                  "Conservation_Field", fld, opt, "")
        useVal = setParam("Conservation Types",
                          "Conservation_Type", GP_s, opt, "", True)

        # Outputs
        outTbl = setParam("Output (Required)", "outTable", "DEFeatureClass",
                          "", "Output")
        pdf = setParam("PDF Report", "outReport", "DEFile", opt, "Output")

        # Set inputs to be disabled until benefits are selected
        disableParamLst([flood_zone, dams, edu_inst, bus_stp, trails, roads,
                         OriWetlands, landUse, LULC_field, landVal, socVul,
                         soc_Field, socVal, conserve, conserve_Field, useVal])

        # Filter FieldsLists by field from the feature dataset
        LULC_field.parameterDependencies = [landUse.name]
        landVal.parameterDependencies = [LULC_field.name]
        landVal.filter.type = 'ValueList'

        soc_Field.parameterDependencies = [socVul.name]
        socVal.parameterDependencies = [soc_Field.name]
        socVal.filter.type = 'ValueList'

        conserve_Field.parameterDependencies = [conserve.name]
        useVal.parameterDependencies = [conserve_Field.name]
        useVal.filter.type = 'ValueList'

        params = [sites, addresses, popRast, flood, view, edu, rec, bird,
                  socEq, rel, flood_zone, dams, edu_inst, bus_stp, trails,
                  roads, OriWetlands, landUse, LULC_field, landVal, socVul,
                  soc_Field, socVal, conserve, conserve_Field, useVal, outTbl,
                  pdf]

        return params

    def isLicensed(self):
        return True

    def updateParameters(self, params):
        # Modify the values and properties of parameters before internal
        # validation is performed. Called whenever a parameter is changed.
        p = params
        # Only take points or raster
        if p[1].value is not None:
            p[2].enabled = False
        else:
            p[2].enabled = True
        if p[2].value is not None:
            p[1].enabled = False
        else:
            p[1].enabled = True
        # Flood only inputs (flood zone & dams)
        if p[3].value is True:  # option button
            p[10].enabled = True  # zone
            p[11].enabled = True  # dams
        else:
            p[10].enabled = False
            p[11].enabled = False
        # edu only inputs (edu_inst)
        if p[5].value is True:
            p[12].enabled = True
        else:
            p[12].enabled = False
        # rec only inputs (bus_stp)
        if p[6].value is True:
            p[13].enabled = True
        else:
            p[13].enabled = False
        # trails required benefits (view, rec, bird)
        if True in set([p[4].value, p[6].value, p[7].value]):
            p[14].enabled = True
        else:
            p[14].enabled = False
        # roads required benefits (view, bird)
        if True in [params[4].value, params[7].value]:
            p[15].enabled = True
        else:
            p[15].enabled = False
        # Wetlands required benefits (flood, view, edu, rec).
        lst = [p[3].value, p[4].value, p[5].value, p[6].value]
        if True in set(lst):
            p[16].enabled = True
        else:
            p[16].enabled = False
        # landuse required benefits (view & rec).
        if True in [p[4].value, p[6].value]:
            p[17].enabled = True
        else:
            p[17].enabled = False
        if p[17].altered:
            p[18].enabled = True
        if p[18].altered:
            in_poly = p[17].valueAsText
            TypeField = p[18].valueAsText
            p[19].enabled = True
            p[19].filter.list = unique_values(in_poly, TypeField)
        # Social vulnerability inputs
        if p[8].value is True:
            p[20].enabled = True
        else:
            p[20].enabled = False
        if p[20].altered:
            p[21].enabled = True
        if p[21].altered:  # field
            in_poly = p[20].valueAsText
            TypeField = p[21].valueAsText
            p[22].enabled = True
            p[22].filter.list = unique_values(in_poly, TypeField)
        # Reliability inputs
        if p[9].value is True:
            p[23].enabled = True
        else:
            p[23].enabled = False
        if p[23].altered:
            p[24].enabled = True  # field
        if p[24].altered:
            in_poly = p[23].valueAsText
            TypeField = p[24].valueAsText
            p[25].enabled = True
            p[25].filter.list = unique_values(in_poly, TypeField)
        return

    def updateMessages(self, params):
        """This method is called after internal validation."""
        # params[].setErrorMessage('') #use to validate inputs
        return

    def execute(self, params, messages):
        main(params)
