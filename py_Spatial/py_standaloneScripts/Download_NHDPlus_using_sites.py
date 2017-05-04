"""Download_NHDPlus_using_sites
Author: Justin Bousquin
bousquin.justin@epa.gov
"""


import arcpy
#import urllib
import os
import subprocess
from urllib import urlretrieve
from shutil import rmtree
#from ftplib import FTP

# User Defined Parameters
# Restoration sites
sites = arcpy.GetParameterAsText(0)
#sites = r"C:\Users\jbousqui\Desktop\Review\Test_Inputs_Review.gdb\VBU_testPoints_islands"
# NHDPlus boundaries
NHD_VUB = arcpy.GetParameterAsText(1)
# Location to save catchments
local = arcpy.GetParameterAsText(2)
# Defaults
#NHD_VUB, local = None, None

# Functions
def message(string):
    """Generic message
    Purpose: prints string message in py or pyt.
    """
    arcpy.AddMessage(string)
    print(string)


def HTTP_download(request, directory, filename):
    """Download HTTP request to filename
    Param request: HTTP request link ending in "/"
    Param directory: Directory where downloaded file will be saved
    Param filename: Name of file for download request and saving
    """
    host = "http://www.horizon-systems.com/NHDPlus/NHDPlusV2_data.php"
    #add dir to var zipfile is saved as
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
        
def get_ext(FC):
    """get extension"""
    ext = arcpy.Describe(FC).extension
    if len(ext)>0:
        ext = "." + ext
    return ext


def field_exists(table, field):
    """Check if field exists in table
    Notes: return true/false
    """
    fieldList = [f.name for f in arcpy.ListFields(table)]
    return True if field in fieldList else False


def checkSpatialReference(alphaFC, otherFC, output = None):
    """Check Spatial Reference
    Purpose: Checks that a second spatial reference matches the first and
             re-projects if not.
    Function Notes: Either the original FC or the re-projected one is returned
    """
    alphaSR = arcpy.Describe(alphaFC).spatialReference
    otherSR = arcpy.Describe(otherFC).spatialReference
    if alphaSR.name != otherSR.name:
        #e.g. .name = u'WGS_1984_UTM_Zone_19N' for WGS_1984_UTM_Zone_19N
        message("Spatial reference for '{}' does not match.".format(otherFC))
        try:
            path = os.path.dirname(alphaFC)
            p_ext = "_prj" + get_ext(alphaFC)
            newName = os.path.basename(otherFC)
            if output is None:
                output = path + os.sep + os.path.splitext(newName)[0] + p_ext
            arcpy.Project_management(otherFC, output, alphaSR)
            fc = output
            message("File was re-projected and saved as: " + fc)
        except:
            message("Warning: spatial reference could not be updated.")
            fc = otherFC
    else:
        fc = otherFC
    return fc


def field_to_lst(table, field):
    """Read Field to List
    Purpose:
    Notes: if field is: string, 1 field at a time;
                        list, 1 field at a time or 1st field is used to sort
    Example: lst = field_to_lst("table.shp", "fieldName")
    """
    lst = []
    #check that field exists in table
    if field_exists(table, field) == True:
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
                order = []
                with arcpy.da.SearchCursor(table, field) as cursor:
                    for row in cursor:
                        order.append(row[0])
                        lst.append(row[1])
                order, lst = (list(x) for x in zip(*sorted(zip(order, lst))))
        else:
            message("Something went wrong with the field to list function")
    else:
        message(str(field) + " could not be found in " + str(table))
        message("Empty values will be returned.")
    return lst


# Default destination
script_dir = os.path.dirname(os.path.realpath(__file__))
if os.path.basename(script_dir) == 'py_standaloneScripts':
    # Move up one folder if standalone script
    script_dir = os.path.dirname(script_dir) + os.sep
else:
    script_dir = script_dir + os.sep
    
if local is None:
    local = script_dir + "NHDPlusV21"
    message("Download will be saved to default location:\n" + local)
else:
    message("Download will be saved to user location:\n" + local)
    
# Default boundary file
if NHD_VUB is None:
    NHD_VUB = script_dir + "NHDPlusV21" + os.sep + "BoundaryUnit.shp"
    if arcpy.Exists(NHD_VUB):
        message("NHDPlus Boundaries found in default location:\n" + NHD_VUB)
    else:
        arcpy.AddError("No NHDPlus Boundaries specified")
        print("No NHDPlus Boundaries specified")
        raise arcpy.ExecuteError
else:
    message("NHDPlus Boundaries found in user location:\n" + NHD_VUB)
    
# ftp://www.horizon-systems.com/NHDPlus/NHDPlusV21/Data/NHDPlus
v2_dir = "/{0}Data/{0}V21/Data/{0}".format("NHDPlus")
NHD_ftp = "ftp.horizon-systems.com"
# http://www.horizon-systems.com/NHDPlusData/NHDPlusV21/Data/NHDPlus
NHD_http = "http://www" + NHD_ftp[3:] + v2_dir
distance = "5 Miles"

# Check projection.
NHD_VUB = checkSpatialReference(sites, NHD_VUB)

# Make layer.
arcpy.MakeFeatureLayer_management(NHD_VUB, "VUB")

# Select NHDPlus vector unit boundaries
overlap = "WITHIN_A_DISTANCE"
arcpy.SelectLayerByLocation_management("VUB", overlap, sites, distance, "", "")

# Gather info from fields to construct request
ID_list = field_to_lst("VUB", "UnitID")
drain_list = field_to_lst("VUB", "DrainageID")

# List to make sure a catchment isn't copied twice
added_lst = []

for i, DA in enumerate(drain_list):
    # Give progress update
    message("Downloading region {} of {}".format(str(i+1), len(drain_list)))

    # Zipfile names
    ID = ID_list[i]
    ext = ".7z"

    # Componentname is the name of the NHDPlusV2 component in the file
    f_comp = "NHDPlusCatchment"
    ff_comp = "NHDPlusAttributes"
    
    # Some Zipfiles had different vv, data content versions
    f_vv = "01" #Catchments
    if ID == "06":
        f_vv = "05"
    if ID in ['10U', '13', '17']:
        f_vv = "02"
        
    ff_vv = "01" #Attributes
    if ID in ["20", "21", "22AS", "22GU", "22MP"]:
        ff_vv = "02"
    if ID in ["03N", "03S", "03W", "13", "16"]:
        ff_vv = "05"
    if ID in ["02", "09", "11", "18"]:
        ff_vv = "06"
    if ID in ["01", "08", "12"]:
        ff_vv = "07"
    if ID in ["05", "15", "17"]:
        ff_vv = "08"
    if ID in ["06", "07", "10U", "14"]:
        ff_vv = "09"
    if ID == "10L":
        ff_vv = "11" 
    if ID == "04":
        ff_vv = "12"
        
    # Assign filenames
    f = "NHDPlusV21_{}_{}_{}_{}{}".format(DA, ID, f_comp, f_vv, ext)
    flow_f = "NHDPlusV21_{}_{}_{}_{}{}".format(DA, ID, ff_comp, ff_vv, ext)
    # Fix the one They mis-named
    if ID == "04":
        f = f[:-6] + "s_05.7z"
    
    # Set http zipfile is requested from
    if DA in ["SA", "MS", "CO", "PI"]: #regions with sub-regions
        request = NHD_http + DA + "/" + "NHDPlus" + ID + "/"
    else:
        request = NHD_http + DA + "/"

    # Download catchment
    HTTP_download(request, local, f)
    # unzip catchment file using winzip
    WinZip_unzip(local, f)

    # Download flow table
    HTTP_download(request, local, flow_f)
    # unzip flow table using winzip
    WinZip_unzip(local, flow_f)

    # Unzip destination folders and files
    d_folder = local + os.sep + "NHDPlus" + DA
    ID_folder = d_folder + os.sep + "NHDPlus" + ID
    cat_folder = ID_folder + os.sep + f_comp
    cat_shp = cat_folder + os.sep + "Catchment.shp"
    flow_folder = ID_folder + os.sep + ff_comp
    flow_dbf = flow_folder + os.sep + "PlusFlow.dbf"

    # Default file location to copy downloads to
    local_gdb = local + os.sep + "NHDPlus_Downloads.gdb"
    if os.path.isdir(local_gdb):
        message("Downloaded files will be added to default file geodatabase")
        
        # Pull catchments into gdb
        if os.path.isdir(cat_folder):
            # Find the Catchment shapefile in that folder
            if arcpy.Exists(cat_shp):
                # Find the default Catchment Feature Class
                local_cat = local_gdb + os.sep + "Catchment"
                if arcpy.Exists(local_cat):
                    # Append the downloaded into the default
                    arcpy.Append_management(cat_shp, local_cat, "NO_TEST")
                    message("Downloaded catchments added to default:\n" +
                            str(local_cat))
                    # Delete downloaded
                    try:
                        rmtree(cat_folder)
                        message("Original downloaded catchment folder deleted")
                    except:
                        message("Unable to delete downloaded catchment folder")
                else:
                    message("Expected default Catchment file '{}' not found".format(local_cat))
            else:
                message("Expected file '{}' not found".format(cat_shp))
        else:
            message("Expected folder '{}' not found".format(cat_folder))
            
        # Pull flow table into gdb
        if os.path.isdir(flow_folder):
            # Find the flow table in that folder
            if arcpy.Exists(flow_dbf):
                # Find the default flow table
                local_flow = local_gdb + os.sep + "PlusFlow"
                if arcpy.Exists(local_flow):
                    # Append the downloaded into the default
                    arcpy.Append_management(flow_dbf, local_flow, "NO_TEST")
                    message("Downloaded flow table added to default:\n" +
                            str(local_flow))
                    # Delete downloaded
                    try:
                        rmtree(flow_folder)
                        message("Original downloaded flow table folder deleted")
                    except:
                        message("Unable to delete downloaded flow table folder")
                else:
                    message("Expected default flow table '{}' not found".format(local_flow))
            else:
                message("Expected file '{}' not found".format(flow_dbf))
            
        else:
            message("Expected folder '{}' not found".format(flow_folder))
    else:
        message("Default file geodatabase not found. Files must be combined manually.")
    

        
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
#>>> f = r"C:\Users\jbousqui\Desktop\NHD"
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
