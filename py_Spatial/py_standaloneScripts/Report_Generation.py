"""
# Name: Rapid Benefit Indicator Assessment - Report Generation
# Purpose: Calculate reliabilty of site benefit product into the future
# Author: Justin Bousquin
# bousquin.justin@epa.gov
#
# Version Notes:
# Developed in ArcGIS 10.3
#0.1.0 converted from .pyt
"""
###########IMPORTS###########
import os
import time
import arcpy

arcpy.env.parallelProcessingFactor = "100%" #use all available resources
arcpy.env.overwriteOutput = True #overwrite existing files

########USER PARAMETERS########
outTbl = '' #table to convert
siteName = '' #optional field in outTbl
mxd = '' #report layout .mxd
pdf = '' #report name
###############################
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


def mean(l):
    "get mean of list"
    return sum(l)/float(len(l))


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


###########REPORT#############
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
    message("Created PDF Report: {} and {}".format(pdf, mxd_name))

##############################
###########EXECUTE############
try:
    start = time.clock()
    Report_MODULE([outTbl, siteName, mxd, pdf])
    start = exec_time(start, "Report Generation")
except Exception:
    message("Error occured during assessment.", 1)
    traceback.print_exc()
