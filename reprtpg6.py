##
##   reprtpg6.py
##
##   arcpy mapping code to create a report using a layout in an mxd
##   and moving the appropriate boxes and text onto / off of the layout
##
##   December 20, 2016
##   Mike Charpentier
##
import arcpy, sys, string, os, time
from time import localtime, strftime

print "Starting reprtpg6.py at " + strftime("%H:%M:%S", localtime())

workdir = "D:\\Projects\\mazzotta\\siterprt\\"
ldrive = "L:\\Public\\jbousqui\\AED\\GIS\\For_Mike\\"

#Set file name and remove if it already exists
pdfPath = "D:\\Projects\\mazzotta\\siterprt\\combine1.pdf"
if os.path.exists(pdfPath):
    os.remove(pdfPath)

#Create the file and append pages in the cursor loop
pdfDoc = arcpy.mapping.PDFDocumentCreate(pdfPath)

try:
    #
    def textpos(theText,column,indnumber):
        if column == 1:
            theText.elementPositionX = 6.25
        else:
            theText.elementPositionX = 7.15
        ypos = 9.025 - ((indnumber - 1) * 0.2)
        theText.elementPositionY = ypos
    #
    def boxpos(theBox,column,indnumber):
        if column == 1:
            theBox.elementPositionX = 5.8
        else:
            theBox.elementPositionX = 6.7
        ypos = 9 - ((indnumber - 1) * 0.2)
        theBox.elementPositionY = ypos

    #
    def fldExists(fieldName,colNumber,rowNumber):
        fldIndex = fieldInfo.findFieldByName(fieldName)
        if fldIndex > 0:
            return True
        else:
            newBox = blackbox.clone("_clone")
            boxpos(newBox,colNumber,rowNumber)
            return False

    def proctext(fieldValue,fieldType,ndigits,ltorgt,aveValue,colNumber,rowNumber,allNos):
        # Process the box first so that text draws on top of box
        if fieldValue is None or fieldValue == ' ':
            newBox = blackbox.clone("_clone")
        else:
            if fieldType == "Number":  # Process numeric fields
                if ltorgt == "lt":
                    if fieldValue < aveValue:
                        newBox = bluebox.clone("_clone")
                    else:
                        newBox = redbox.clone("_clone")
                else:
                    if fieldValue > aveValue:
                        newBox = bluebox.clone("_clone")
                    else:
                        newBox = redbox.clone("_clone")
            else: # Process text fields (booleans)
                if allNos == 1:
                    newBox = graybox.clone("_clone")
                else:
                    if fieldValue == aveValue:
                        newBox = bluebox.clone("_clone")
                    else:
                        newBox = redbox.clone("_clone")
        boxpos(newBox,colNumber,rowNumber)
        # Process the text
        if not (fieldValue is None or fieldValue == ' '):
            newText = indtext.clone("_clone")
            if fieldType == "Number":  # Process numeric fields
                if fieldValue == 0:
                    newText.text = "0"
                else:
                    if ndigits == 0:
                        if fldValue > 10:
                            rndnumber = round(fieldValue,0)
                            intnumber = int(rndnumber)
                            newnum = format(intnumber, ",d")
                            #rndnumber = str(round(fieldValue,0))
                            #decind = str(rndnumber).find(".0")
                            #newnum = str(rndnumber)[0:decind]
                            newText.text = newnum
                        else:
                            newText.text = str(round(fieldValue,1))
                    else:
                        newText.text = str(round(fieldValue,ndigits))
            else:
                if allNos == 1:
                    newText.text = "No"
                else:
                    if fieldValue == "YES":
                        newText.text = "Yes"
                    else:
                        newText.text = "No"
            textpos(newText,colNumber,rowNumber)

    #
    mxd = arcpy.mapping.MapDocument("D:\\Projects\\mazzotta\\siterprt\\report11.mxd")
    bluebox = arcpy.mapping.ListLayoutElements(mxd, "GRAPHIC_ELEMENT", "bluebox")[0]
    redbox = arcpy.mapping.ListLayoutElements(mxd, "GRAPHIC_ELEMENT", "redbox")[0]
    graybox = arcpy.mapping.ListLayoutElements(mxd, "GRAPHIC_ELEMENT", "graybox")[0]
    blackbox = arcpy.mapping.ListLayoutElements(mxd, "GRAPHIC_ELEMENT", "blackbox")[0]
    indtext = arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT", "IndText")[0]

    #lyrinput = workdir + "ResultsMike.shp"
    lyrinput = ldrive + "Output_Fin77.shp"
    #lyrinput = workdir + "ResultsMik2.shp"

    arcpy.MakeTableView_management(lyrinput,"rptbview")
    desc = arcpy.Describe("rptbview")
    fieldInfo = desc.fieldInfo
    #fldIndex = fieldInfo.findFieldByName("UpstM_mc")
    #if not fldIndex > 0:
    #    arcpy.AddField_management(wetfrgdb + "mcfactors", "UpstM_mc", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    #arcpy.Delete_management("rptbview", "")

    # First do a check to see if any text fields have a value of "NO" for all records.  If so use a gray box with "No" in report.
    # dbf file containing field names, types, ltorgt, aveValue, ndigits
    cknorows = arcpy.UpdateCursor(workdir + "flddata.dbf","DataType = 'Text'")
    cknorow = cknorows.next()
    while cknorow:
        cknorow.allnos = 0
        fldIndex = fieldInfo.findFieldByName(cknorow.FieldName) # Check to see if field exists
        if fldIndex > 0:
            if arcpy.Exists(workdir + "checkno.dbf"):
               arcpy.Delete_management(workdir + "checkno.dbf", "")
            arcpy.Frequency_analysis(lyrinput, workdir + "checkno.dbf", cknorow.FieldName, "")
            if int(arcpy.GetCount_management(workdir + "checkno.dbf").getOutput(0)) == 1:
                #fld2chek = eval(cknorow.FieldName)
                fld2chek = "checkrow." + cknorow.FieldName
                checkrows = arcpy.SearchCursor(workdir + "checkno.dbf","")
                checkrow = checkrows.next()
                if eval(fld2chek) == "NO":
                    cknorow.allnos = 1
                del checkrow
                del checkrows
        cknorows.updateRow(cknorow)
        cknorow = cknorows.next()
    del cknorow
    del cknorows

    counter = 1
    pagecnt = 1
    #
    siterows = arcpy.SearchCursor(lyrinput,"")
    siterow = siterows.next()
    #while siterow and counter < 4: # Testing
    while siterow:

        oddeven = counter % 2
        if oddeven == 1:
            column = 1
        else:
            column = 2

        if oddeven == 1:
            siteText = arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT", "SiteLeftText")[0]
        else:
            siteText = arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT", "SiteRightText")[0]
        siteText.text = "Site " + str(counter)

        # Text element processing
        if oddeven == 1:
            siteName = arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT", "SiteLeftName")[0]
            if fieldInfo.findFieldByName("siteName") > 0:
                if siterow.siteName == ' ':
                    siteName.text = "No name"
                else:
                    siteName.text = siterow.siteName
            else:
                siteName.text = "No name"
        else:
            siteName = arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT", "SiteRightName")[0]
            if fieldInfo.findFieldByName("siteName") > 0:
                if siterow.siteName == ' ':
                    siteName.text = "No name"
                else:
                    siteName.text = siterow.siteName
            else:
                siteName.text = "No name"

        # dbf file containing field names, types, ltorgt, aveValue, ndigits
        fldrows = arcpy.SearchCursor(workdir + "flddata.dbf","rowNumber < 38") # Not set up to process the Social Equity or Reliability scores
        fldrow = fldrows.next()
        while fldrow:

            if fldrow.DataType == "Double":
                if fldExists(fldrow.FieldName,column,fldrow.rowNumber):
                    #proctext(fieldValue,fieldType,ndigits,ltorgt,aveValue,colNumber,rowNumber)
                    fldValue = "siterow." + fldrow.FieldName
                    #proctext(fieldValue,fieldType,ndigits,ltorgt,aveValue,colNumber,rowNumber)
                    proctext(eval(fldValue),"Number",fldrow.ndigits,fldrow.ltorgt,fldrow.aveValue,column,fldrow.rowNumber,fldrow.allnos)
            else:
                if fldExists(fldrow.FieldName,column,fldrow.rowNumber):
                    fldValue = "siterow." + fldrow.FieldName
                    #proctext(eval(fldValue),"Boolean",0,"","YES",column,fldrow.rowNumber,fldrow.allnos)
                    proctext(eval(fldValue),"Boolean",0,"",fldrow.aveBool,column,fldrow.rowNumber,fldrow.allnos)

            fldrow = fldrows.next()

        del fldrow
        del fldrows

        if oddeven == 0:
            if arcpy.Exists(workdir + "test" + str(pagecnt) + ".pdf"):
                arcpy.Delete_management(workdir + "test" + str(pagecnt) + ".pdf", "")
            arcpy.mapping.ExportToPDF(mxd, workdir + "test" + str(pagecnt) + ".pdf", "PAGE_LAYOUT")
            pdfDoc.appendPages(workdir + "test" + str(pagecnt) + ".pdf")
            pagecnt += 1
        counter += 1
        siterow = siterows.next()

    if oddeven == 1:  # If you finish a layer with an odd number of records, last record was not added to the pdf.
        # Blank out right side
        siteText = arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT", "SiteRightText")[0]
        siteText.text = " "
        # Blank out right side
        siteName = arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT", "SiteRightName")[0]
        siteName.text = " "
        # Fill right side with gray empty boxes
        for i in range(39):
            newBox = graybox.clone("_clone")
            boxpos(newBox,2,i + 1)
        if arcpy.Exists(workdir + "test" + str(pagecnt) + ".pdf"):
            arcpy.Delete_management(workdir + "test" + str(pagecnt) + ".pdf", "")
        arcpy.mapping.ExportToPDF(mxd, workdir + "test" + str(pagecnt) + ".pdf", "PAGE_LAYOUT")
        pdfDoc.appendPages(workdir + "test" + str(pagecnt) + ".pdf")

    del siterow
    del siterows

    arcpy.Delete_management("rptbview", "")

    pdfDoc.saveAndClose()

    if arcpy.Exists(workdir + "result1.mxd"):
        arcpy.Delete_management(workdir + "result1.mxd", "")
    #mxd.save()
    mxd.saveACopy(workdir + "result1.mxd")

    del mxd
    del pdfDoc

    print "Completed reprtpg6.py at " + strftime("%H:%M:%S", localtime()) + "\n"
    print "Created " + workdir + "combine1.pdf and result1.mxd"

except:

    pdfDoc.saveAndClose()
    del pdfDoc
    del mxd

    import traceback, sys
    # get the traceback object
    tb = sys.exc_info()[2]

    # tbinfo contains the failure's line number and the line's code
    tbinfo = traceback.format_tb(tb)[0]

    print tbinfo          # provides where the error occurred
    print sys.exc_type    # provides the type of error
    print sys.exc_value   # provides the error message

    print "Problem occured"
    arcpy.AddMessage(arcpy.GetMessages())
    print arcpy.GetMessages()