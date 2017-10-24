"""
# Name: Rapid Benefit Indicator Assessment - Download NHDPlus Data
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
import subprocess
from urllib import urlretrieve
from shutil import rmtree

arcpy.env.parallelProcessingFactor = "100%" #use all available resources
arcpy.env.overwriteOutput = True #overwrite existing files

#######USER PARAMETERS#######
# Restoration sites
sites = arcpy.GetParameterAsText(0)
#sites = r"~\Test_Inputs_Review.gdb\VBU_testPoints_islands"
# NHDPlus boundaries
NHD_VUB = arcpy.GetParameterAsText(1)
# Location to save catchments
local = arcpy.GetParameterAsText(2)
# Defaults
#NHD_VUB, local = None, None

###########FUNCTIONS###########
def message(string, severity = 0):
    """Generic message
    Purpose: prints string message in py or pyt.
    """
    print(string)
    if severity == 1:
        arcpy.AddWarning(string)
    else:
        arcpy.AddMessage(string)


def get_ext(FC):
    """get extension"""
    ext = arcpy.Describe(FC).extension
    if len(ext) > 0:
        ext = "." + ext
    return ext


def field_exists(table, field):
    """Check if field exists in table
    Notes: return true/false
    """
    fieldList = [f.name for f in arcpy.ListFields(table)]
    return True if field in fieldList else False


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


#def NHD_get_MODULE(PARAMS):
"""Download NHD Plus Data"""

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
               "04": ["05", "13"],
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

        
#########NOTES########
#import ftplib
#
#host = 'ftp.horizon-systems.com'
#ftp = ftplib.FTP('ftp.horizon-systems.com')

#sub_dir = "/NHDPlus/NHDPlusV21/Data/NationalData/"

#files
#PR = "NHDPlusV21_NationalData_National_HI_PR_VI_PI_Seamless_Geodatabase_03.7z"
#CONUS = "NHDPlusV21_NationalData_CONUS_Seamless_Geodatabase_04.7z"
#Cat = "NHDPlusV21_NationalData_NationalCat_02.7z"

#>>> import arcpy
#>>> import urllib
#>>> f = r"C~\Desktop\NHD"
#>>> link = "ftp://www.horizon-systems.com/NHDPlus/NHDPlusV21/Data/NationalData/NHDPlusV21_NationalData_CONUS_Seamless_Geodatabase_04.7z"
#>>> urllib.urlretrieve(link, f)


###WATERS SERVER###
#service_url = 'https://ofmpub.epa.gov/waters10/'

    #try downloading from ftp
    #try:
        #ftp = FTP(NHD_ftp)
        #ftp.login()
        #ftp.cwd(v2_dir + ID + "/")
        #outfile = open(local + f, 'wb')
        #ftp.retrbinary('RETR ' + f, outfile.write)
        #ftp.quit()
        #outfile.close()
        #message("FTP download successful: " + str(local_f))
    #if that doesn't work try downloading from http
    # If that folder exists
    
##    if os.path.isdir(d_folder):
##        dir_lst = [x[0] for x in os.walk(d_folder)]
##        for folder in dir_lst:
##            # Find the NHDPlusCatchment folder within child folder list
##            if os.path.basename(folder) == 'NHDPlusCatchment':
##                # Find the Catchment shapefile in that folder
##                cat_shp = folder + os.sep + "Catchment.shp"
##                if arcpy.Exists(cat_shp):
##                    message("Located a 'Catchment.shp' file")
##                    # Make sure it hasn't been added already
##                    if cat_shp not in added_lst:
##                        local_cat = local + os.sep + "Catchment.shp"
##                        if arcpy.Exists(local_cat):
##                            arcpy.Append_management([cat_shp], local_cat)
##                            added_lst.append(cat_shp)
##                            message("Combined new Catchement file with existing")
##                            try:
##                                os.remove(cat_shp)
##                            except:
##                                print(cat_shp + " was problem")
##                        else:
##                            arcpy.CopyFeatures_management(cat_shp, local_cat)
##                            added_lst.append(cat_shp)
##                            message("Copied new Catchment file: " + local_cat)
##                            try:
##                                os.remove(cat_shp)
##                            except:
##                                print(cat_shp + " was problem")
##                    else:
##                        #do something if file added but not deleted?
##                        try:
##                            os.remove(cat_shp)
##                            print(cat_shp + " removed later")
##                        except:
##                            message("Please delete: " + cat_shp)      
##                    try:
##                        shutil.rmtree(d_folder)
##                        message("Original downloaded files deleted")
##                    except:
##                        message("Unable to delete downloaded catchment file")
##                # When Catchment shapefile can no be found
##                else:
##                    message("Could not find 'Catchment.shp' file in " + folder)
##
##    else:
##        message("Expected folder {} not found".format(d_folder))
