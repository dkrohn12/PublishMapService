#PublishAGLRMapService.py
#Tool to more easily publish known Map Services
#Format: PublishAGLRMapService.py <MapServiceToUpdate1> <MapServiceToUpdate2> ...
#Changes
#2015/07/07		DLK Created in conjunction with PublishAGLRMapService.bat
#2016/01/15		DLK Changed OutageLocation with ClickOrders to better describe layers
#2016/10/14		DLK/MP Updated to at Recycle Start time to ga_Configs array
#2017/06/22		DLK Rearranged code to put configuratioon code at top
#					Added Support to abort processing if referenced data
#					is not present in the Servers' known locations.
#2017/07/21		DLK Added check of FQDN URL for gentoken if non-FQDN fails

#Code was orignally taken from the 'Modify SDDraft example 6' from
#http://desktop.arcgis.com/en/arcmap/10.3/analyze/arcpy-mapping/createmapsddraft.htm
#Modify SDDraft example 6
#
#The following sample script creates a Service Definition Draft (.sddraft) file
#for the ARCGIS_SERVER server_type from a Map Document (.mxd). It then enables 
#caching on the service by modifying the .sddraft file using the xml.dom.minidom
# standard Python library. The modified .sddraft file is then saved to a new 
# file. Next, the new .sddraft file is analyzed for errors using the 
# AnalyzeForSD function. After analyzing the service definition draft, it is 
# time to stage the service definition. Use the Stage Service geoprocessing tool
# to stage the service definition. Then use the Upload Service Definition 
# geoprocessing tool to upload the service definition to the server and publish
# the map service. Once the service has been published, the script then calls 
# the Manage Map Server Cache Scales geoprocessing tool which updates the scale 
# levels in an existing cached map or image service. Use this tool to add new 
# scales or delete existing scales from a cache. Finally, the script calls the 
# Manage Map Server Cache Tiles geoprocessing tool to create map service cache 
# tiles.

import xml.dom.minidom as DOM 
import os, re, time, sys
import urllib, urllib2, json
#import win32com.client
import arcpy

	#[0]=Name [1]=MinInstances [2]=MaxInstances [3]=UsageTimeout [4]=WaitTimeout
	#[5]=IdleTimeout [6]=RecycleInterval every x Hrs [7]=Start Recycle Time
	#[8]=[List Of Capabilties to turn on]
	#Valid Capabilities: MapServer (always on), WCSServer, WMSServer, FeatureServer
	#					SchematicsServer, MobileServer, NAServer, KMLServer, WFSServer
g_aConfigs = [
			  #Use Default if Service not in list
			['Default',                  0, 5, 120, 60, 300, 6,   '00:00', [] ],
			  #Map Services for EasyStreet
			['EasyStreet',               2, 5, 600, 60, 1800, 24, '00:00', [] ],
			#Map Services for SENTRi Tickets
			['SENTRiTickets',            0, 5, 600, 60, 1800, 24, '00:00', [] ],
			  #Map Services for GSCA
			['AdminBoundary',            2, 5, 120, 60, 300, 6,   '00:10', [] ],
			['Building',                 2, 5, 120, 60, 300, 2,   '00:10', [] ],
			['ClickOrders',              0, 5, 600, 60, 1800, 24, '00:00', [] ],
			['CPSystem',                 2, 5, 120, 60, 300, 6,   '00:20', [] ],
			['Facility',                 2, 5, 120, 60, 300, 6,   '00:30', [] ],
			['GasMain',                  2, 5, 120, 60, 300, 6,   '00:40', [] ],
			['OutageLocation',           0, 5, 600, 60, 1800, 24, '00:00', [] ],
			['RetiredFacility',          2, 5, 120, 60, 300, 6,   '00:50', [] ],
			  #Map Services for SENTRi
			['SENTRI_GIS_AGLC',          1, 5, 300, 120, 300, 6,  '00:00', ['TicketServer'] ],
			['SENTRI_GIS_FCG',           1, 5, 300, 120, 300, 6,  '00:00', ['TicketServer'] ],
			['SENTRI_GIS_NICOR',         1, 5, 300, 120, 300, 6,  '00:00', ['TicketServer'] ],
			  #Map Services for GetLocation / CircleOf Life
			['AGLRGISWebServices_FGDB',  0, 8, 120, 60, 300, 24,  '00:00', [] ],
			['AGLRGISWebServices_GDB',   0, 8, 120, 60, 300, 24,  '00:00', [] ],
			['SOGASGISWebServices_FGDB', 0, 8, 120, 60, 300, 24,  '00:00', [] ],
			['SOGASGISWebServices_GDB',  0, 8, 120, 60, 300, 24,  '00:00', [] ],
			  #Map Services for Nicor GLOBE
			['AnnotationDimensions',      2, 5, 120, 60, 300, 6,  '00:00', [] ],
			['AOI',                       0, 5, 120, 60, 300, 6,  '00:00', [] ],
			['AOI_NicorData',             2, 5, 120, 60, 300, 6,  '00:00', [] ],
			['Detail',                    2, 5, 120, 60, 300, 6,  '00:00', [] ],
			['Facility',                  2, 5, 120, 60, 300, 6,  '00:00', [] ],
			['GasMain',                   2, 5, 120, 60, 300, 6,  '00:00', [] ],
			['Landbase',                  2, 5, 120, 60, 300, 6,  '00:00', [] ],
			['Pipe',                      2, 5, 120, 60, 300, 6,  '00:00', [] ],
			['Scales',                    2, 5, 120, 60, 300, 6,  '00:00', [] ],
			['ServiceAnno',               0, 5, 120, 60, 300, 6,  '00:00', [] ],
			['Services',                  0, 5, 120, 60, 300, 6,  '00:00', [] ],
			['ServiceTerritory',          2, 5, 120, 60, 300, 6,  '00:00', [] ]
		]

	#[0]=Name [1]=MinInstances [2]=MaxInstances [3]=UsageTimeout [4]=WaitTimeout
	#[5]=IdleTimeout [6]=RecycleInterval every x Hrs [7]=Start Recycle Time
	#[8]=[List Of Capabilties to turn on] 

sComputerName = os.getenv("COMPUTERNAME")
sUSERDNSDOMAIN= os.getenv("USERDNSDOMAIN")
sShortComputerName = re.sub( 'GAATL', '', sComputerName.upper())
	#Location of system .ags files
	#DLK 20150310 Connection File is now in a standard place
	#You should create a connection file on the server, then copy to 
	# the T:/GIS/Config/DataModel/ModelChange/Config folder and rename
	# in the format <SERVER>_[6443|6080]_ADMIN.ags
systemFolder = 'T:/gis/Config/DataModel/ModelChange/Config'
	#Create Connection file
port       = 6443
server     = '%s_6443_ADMIN' % (sComputerName)
CONN_FILE  = '%s/%s.ags' % (systemFolder, server )

if not os.path.exists(CONN_FILE):
	port      = 6080
	server    = '%s_6080_ADMIN' % (sComputerName)
	CONN_FILE = '%s/%s.ags' % (systemFolder, server )
	if not os.path.exists(CONN_FILE):
		print "Connection File [%s] does not exist. exitting" % CONN_FILE
		return 1
#print "Using CONN_FILE [%s]" % CONN_FILE

gHTTPTYPE     = 'http'
g_ProdServers = ["GAATLP51W","GAATLP515W","GAATLP956W","GAATLP957W","GONWSGISP81", "GONWSGISP82"]
g_bProd       = (sComputerName.upper() in g_ProdServers)
sAdminUser = 'siteadmin_User'
sAdminPass = 'siteadmin_DEV_UATPWD'
if g_bProd:
	sAdminPass = 'siteadmin_PRODPWD'

	# define Folder Variables where various data will be stored
WORKSPACE    = 'D:/Workspace'
GDB_PATH     = '%s/GDBs'     % WORKSPACE
MXD_PATH     = '%s/MXDs'     % WORKSPACE
SDDRAFT_PATH = '%s/SDDrafts' % WORKSPACE
OUT_PATH     = '%s/output'   % WORKSPACE

	#Create Folders if they don't exist GDB_PATH should already exist
for dir in [ MXD_PATH, SDDRAFT_PATH, OUT_PATH ]:
	if not os.path.exists(dir): os.mkdir(dir)
		#Create Folders if they don't exist
	for subfolder in [ "AGLC", "ETG", "FCG", "NG", "VNG", "LeakSurveyPOC" ]:
		sSubfolder = dir+'/'+subfolder
		if not os.path.exists(sSubfolder): os.mkdir(sSubfolder)

	#Time Format for logging
sHMSFmt       = "%H:%M:%S"
sShortTimeFmt = '%Y%m%d%H%M%S'
sLongTimeFmt  = "%a, %d %b %Y %H:%M:%S"
NL            = "\n"

#Write info to log and to screen
def LogMsg(f,sMsg):
	sTime = time.strftime(sHMSFmt, time.localtime())
	sLine = "%s: %s" % (sTime, sMsg)
	print sLine
	if f:
		f.write (sLine + NL)
		f.flush()
#End LogMsg

#gentoken and getServiceList modified from ArcGIS Server Administration Toolkit - 10.1+
# http://www.arcgis.com/home/item.html?id=12dde73e0e784e47818162b4d41ee340
def gentoken(server, port, adminUser, adminPass, expiration=60):
    #Re-usable function to get a token required for Admin changes

	if str(port) == "6443": httptype = 'https'
	else				  : httptype = 'http'
	server_FQDN   = "{}.{}".format(server,sUSERDNSDOMAIN)
	url           = "{}://{}:{}/arcgis/admin/generateToken?f=json".format(httptype, server, port)
	url_FQDN      = url.replace(server, server_FQDN)

	query_dict = {'username':   adminUser,
					'password':   adminPass,
					'expiration': str(expiration),
					'client':     'requestip'}

	query_string = urllib.urlencode(query_dict)
	try:
		token = json.loads(urllib.urlopen(url, query_string).read())
	except:
		#Before giving up, try with the FGDN, e.g gaatlp913w.corp.aglrsc.com
		#This Solves the following ERROR:
		#CertificateError: hostname 'GAATLT512W' doesn't match u'GAATLT512W.CORPTEST.AGLRSC.COM'
		url   = url_FQDN
		token = json.loads(urllib.urlopen(url, query_string).read())	

	if "token" not in token:
		#If invalid, change siteadmin password
		query_dict['password'] = 'siteadmin'
		query_string = urllib.urlencode(query_dict)
		token = json.loads(urllib.urlopen(url, query_string).read())

	if "token" not in token:
		arcpy.AddError('Error in gentoken(): ' + token['messages'])
		quit()
	else:
		return token['token']
#End gentoken

def getServiceList(server, port,adminUser, adminPass, token=None):
    ''' Function to get all services
    Requires Admin user/password, as well as server and port (necessary to construct token if one does not exist).
    If a token exists, you can pass one in for use.  
    Note: Will not return any services in the Utilities or System folder
    '''    
    
    
    if token is None:    
        token = gentoken(server, port, adminUser, adminPass)    
    
    services = []    
    folder = ''
    
    if str(port) == "6443": httptype = 'https'
    else				  : httptype = 'http'
    server_FQDN   = "{}.{}".format(server,sUSERDNSDOMAIN)
    BASE_URL      = "{}://{}:{}".format(httptype, server, port)
    BASE_URL_FQDN = BASE_URL.replace(server, server_FQDN)
    URL = "{}/arcgis/admin/services{}?f=pjson&token={}".format(BASE_URL, folder, token)
    try:
        serviceList = json.loads(urllib2.urlopen(URL).read())
    except:
        #Try FQDN URL before quitting
        URL         = URL.replace(BASE_URL,BASE_URL_FQDN)
        serviceList = json.loads(urllib2.urlopen(URL).read())
        BASE_URL    = BASE_URL_FQDN

    # Build up list of services at the root level
    for single in serviceList["services"]:
        services.append(single['serviceName'] + '.' + single['type'])
     
    # Build up list of folders and remove the System and Utilities folder (we dont want anyone playing with them)
    folderList = serviceList["folders"]
    folderList.remove("Utilities")             
    #folderList.remove("System")
        
    if len(folderList) > 0:
        for folder in folderList:                                              
            URL = "{}/arcgis/admin/services/{}?f=pjson&token={}".format(BASE_URL, folder, token)
            fList = json.loads(urllib2.urlopen(URL).read())
            
            for single in fList["services"]:
                services.append(folder + "/" + single['serviceName'] + '.' + single['type'])                    
    
    return services
#End genServiceList


def Publish_MapService(MXD_FILE, bMapServiceExists=False ) :
	global g_aConfigs

	if not os.path.exists(CONN_FILE):
		print "Connection File [%s] does not exist. exitting" % CONN_FILE
		return 1

	sMXD = MXD_FILE.replace("\\","/")
	sServiceName = sMXD.replace(MXD_PATH+'/','')
	if sServiceName[-4:].upper() == ".MXD":
		sServiceName = sServiceName[:-4]	#Remove .MXD extension
	else:
		sMXD += ".mxd"
	#setup full path
	sMXD = "%s/%s" % (MXD_PATH, sMXD)

	sBaseServiceName = sServiceName
	sFolder = ""
	if sServiceName.find("/") >= 0:
		sFolder=os.path.dirname(sServiceName)
		sBaseServiceName = os.path.basename(sServiceName)

	sMapServiceFullPath = "%s/%s" % (CONN_FILE,sServiceName)

		#Create Temporary File Names for creating/Updating Map Service
	sddraft      = "%s/%s.sddraft" % (SDDRAFT_PATH, sServiceName)
	sd           = "%s/%s.sd" % (OUT_PATH, sServiceName)
	outXML       = "%s/%s.sddraft" % (OUT_PATH, sServiceName)
	sddraft_name = sddraft.replace(SDDRAFT_PATH+"/",'')
	sd_name      = sd.replace(OUT_PATH+"/",'')
	outXML_name  = outXML.replace(OUT_PATH+"/",'')

	#sServiceName, sFolder, sBaseServiceName, sddraft, sd, outXML
	mapDoc = arcpy.mapping.MapDocument(sMXD)
	#print sMXD
	if sBaseServiceName.upper() in ["ADMINBOUNDARY","SERVICECENTERS"]:
		mapDoc.credits=sShortComputerName	#Only want to display Credit for ServiceCenters
	else:
		mapDoc.credits=''
	sTags = mapDoc.tags
	sSummary = mapDoc.summary.strip()
	if len(sSummary) == 0:	sSummary = ("%s %s" % (sFolder,sBaseServiceName)).strip()

	# build paths to data
	mapServer = '%s/%s.MapServer' % (CONN_FILE, sServiceName)

	# create sddraft
	LogMsg(gFD, 'Creating Map Draft [%s]' % sddraft_name)
	if os.path.exists(sddraft): os.remove(sddraft)
	arcpy.mapping.CreateMapSDDraft(mapDoc, sddraft, sBaseServiceName, 'ARCGIS_SERVER', CONN_FILE,
								   False, sFolder,sSummary, sTags)

	# read sddraft xml
	doc = DOM.parse(sddraft)

		#Update XML to tell Upload Service Definition this is an update
	if bMapServiceExists:
		tagsType = doc.getElementsByTagName('Type')
		for tagType in tagsType:
			if tagType.parentNode.tagName == 'SVCManifest':
				if tagType.hasChildNodes():
					tagType.firstChild.data = "esriServiceDefinitionType_Replacement"

		tagsState = doc.getElementsByTagName('State')
		for tagState in tagsState:
			if tagState.parentNode.tagName == 'SVCManifest':
				if tagState.hasChildNodes():
					tagState.firstChild.data = "esriSDState_Published"

	aConfig = g_aConfigs[0]		#Default values if not found
	for a in g_aConfigs:
		if a[0] == sBaseServiceName: aConfig=a

	MinInstances = aConfig[1]
	MaxInstances = aConfig[2]
	if not g_bProd:
		if MinInstances > 0: MinInstances = 0
		if MaxInstances > 3: MaxInstances = 3
	UsageTimeout     = aConfig[3]
	WaitTimeout      = aConfig[4]
	IdleTimeout      = aConfig[5]
	RecycleInterval  = aConfig[6]
	RecycleStartTime = aConfig[7]
	aCapabilities    = ['MapServer'] + aConfig[8]
	LogMsg(gFD,
	"%s Map Service Parameters: Min/MaxInstances %d/%d Usage/Wait/Idle Timeouts %d/%d/%d RecycleInterval %d Restart Time %s" %
	(sServiceName,MinInstances,MaxInstances, UsageTimeout, WaitTimeout, IdleTimeout, RecycleInterval, RecycleStartTime))
	LogMsg(gFD, "%s Map Service Capabilities: %s" % (sServiceName, aCapabilities))
		
	# turn on caching in the configuration properties
		#Make any Changes to the Map Service Properties default
	keys = doc.getElementsByTagName('Key')
	for key in keys:
		k = key.firstChild.data
		v = key.nextSibling.firstChild
		#if v is None:
		#	print "%s\tNone" % (k)
		#else:
		#	print "%s\t%s" % (k, v.data)
		if   k == 'MinInstances': v.data = MinInstances #1
		elif k == 'MaxInstances': v.data = MaxInstances #1
		elif k == 'UsageTimeout': v.data = UsageTimeout #6000
		elif k == 'WaitTimeout':  v.data = WaitTimeout  #60
		elif k == 'IdleTimeout':  v.data = IdleTimeout	#20000
		elif k == 'recycleInterval':
			if v is None:
				v = doc.createTextNode(str(RecycleInterval))
				key.nextSibling.appendChild(v)
			else:
				v.data = RecycleInterval	#24
		elif k == 'recycleStartTime':
			if v is None:
				v = doc.createTextNode(RecycleStartTime)
				key.nextSibling.appendChild(v)
			else:
				v.data = RecycleStartTime
		#else:
		#	print 'Unused Key %s' % k

	#Ensure Only services in aCapabilities are turned on - KML Service is turned off
	services___ = doc.getElementsByTagName('TypeName')
	for service__ in services___:
		sEnabled = 'false'
		#print service__.firstChild.data, service__.parentNode.getElementsByTagName('Enabled')[0].firstChild.data
		if service__.firstChild.data in aCapabilities:  sEnabled = 'true'
		service__.parentNode.getElementsByTagName('Enabled')[0].firstChild.data = sEnabled
		##if service__.firstChild.data == 'TicketServer':
		##	ts = service__
		#print "%s	%s" % (service__.firstChild.data, service__.parentNode.getElementsByTagName('Enabled')[0].firstChild.data) 
		#if service__.firstChild.data == 'KmlServer':
		#	service__.parentNode.getElementsByTagName('Enabled')[0].firstChild.data = 'false'
		#if service__.firstChild.data == 'WMSServer':
		#	service__.parentNode.getElementsByTagName('Enabled')[0].firstChild.data = 'true'
				
	# output to a new sddraft
	if os.path.exists(outXML): os.remove(outXML)
	f = open(outXML, 'w')     
	doc.writexml( f )     
	f.close() 
	
	# analyze new sddraft for errors
	LogMsg(gFD, 'Analyzing [%s]' % outXML_name)
	analysis = arcpy.mapping.AnalyzeForSD(outXML)

	# print dictionary of messages, warnings and errors
	#Code 10045 is Map is being published with data copied to the server using data frame full extent
	#Code 24011 is Layer's data source is not registered with the server and data will be copied to the server
	bDataRegistered = True
	for key in ('messages', 'warnings', 'errors'):
		LogMsg(gFD, "----%s---" % key.upper())
		vars = analysis[key]
		for ((message, code), layerlist) in vars.iteritems():
			LogMsg(gFD, "	CODE %d %s" % (code, message))
			sMsg = "	   applies to:"
			for layer in layerlist:
				sMsg += layer.name + " "
			LogMsg(gFD,sMsg)
			if code in [10045, 24011] : bDataRegistered = False

	# stage and upload the sServiceName if the sddraft analysis did not contain errors
	if analysis['errors'] == {} and bDataRegistered :
		# Execute StageService
		if os.path.exists(sd): os.remove(sd)
		LogMsg(gFD, "Staging Service Definition... [%s]" % outXML_name)
		try:
			arcpy.StageService_server(outXML, sd)
			# Execute UploadServiceDefinition
			LogMsg(gFD, "Uploading Service Definition... [%s]" % sd_name)
			arcpy.UploadServiceDefinition_server(sd, CONN_FILE)
			# Print messaging from UploadServiceDefinition
		except:
			LogMsg(gFD, "----Error Staging {0}---".format(outXML_name))
			for x in range(0,arcpy.GetMessageCount()):
				arcpy.AddReturnMessage(x)
				LogMsg(gFD, arcpy.GetMessage(x))
			LogMsg(gFD,"{0} contained errors. StageService aborted.".format(outXML_name))
			exit()
	else: 
		LogMsg(gFD,"{0} contained errors or data is not registered on the Server. StageService and UploadServiceDefinition aborted.".format(sddraft))
		exit()
		
	LogMsg(gFD, "Successfully Published Map Service [%s]"  % sServiceName)
#End Publish_MapService

def GetMapServicesToProcess(aInputList):
	aList = []
	if len(aInputList) == 1:
		LogMsg(gFD,"Format: No MXD's passed to process")
	i = 0
	for smxd in aInputList:
		if i > 0:
			#validate values
			#Strip off MXD_PATH in case passed and verify exists
			smxd = smxd.replace("\\","/")
			smxd = smxd.replace(MXD_PATH+'/','')
			if smxd[-4:].upper() == ".MXD":
				smxd = smxd[:-4]	#Remove .MXD extension
			testsmxd = smxd.upper()
			if testsmxd == 'AGLC':
				aList += aAGL
			elif testsmxd == 'ETG':
				aList += aETG
			elif testsmxd == 'FCG':
				aList += aFCG
			elif testsmxd == 'NG':
				aList += aNG
			elif testsmxd == 'VNG':
				aList += aVNG
			elif testsmxd == "ALL":
				aList += aBaseMXD + aAGL + aFCG
			elif os.path.exists("%s/%s.mxd" % (MXD_PATH,smxd)):
				aList += [smxd]
			else:
				LogMsg(gFD,"[%s] does not exist in %s. Stopping processing" % (smxd,MXD_PATH))
				return ([])
		else:
			i += 1
	return aList
#END GetMapServicesToProcess

		####	MAINLINE	####
dStart = time.localtime()
sAppName = 'PublishAGLRMapService'
sStart = '%s on %s starting at: %s' % (sAppName, sComputerName, time.strftime(sLongTimeFmt, dStart))
LOGFILE = 'Logs/%s-%s-%s.txt' % (sComputerName, sAppName,time.strftime(sShortTimeFmt, dStart))
if not os.path.isdir("Logs"):
	os.makedirs("Logs")
gFD = open(LOGFILE, 'w')
	
aServiceList = getServiceList(sComputerName, port, sAdminUser, sAdminPass)

#OutageLocation.mxd
#ClickOrders.mxd
sList = "LDC/AdminBoundary LDC/Building LDC/CPSystem LDC/Facility LDC/GasMain LDC/RetiredFacility"
aAGL = sList.replace("LDC", "AGLC").split()
aFCG = sList.replace("LDC", "FCG").split()
aETG = sList.replace("LDC", "ETG").split()
aVNG = sList.replace("LDC", "VNG").split()
aNG = "NG/EasyStreet".split()

sMXD='FCG/Building.mxd'
sBaseMXD = 'ServiceCenters.mxd'
aBaseMXD = sBaseMXD.split()
aTotalList = aBaseMXD + aNG + aAGL + aFCG #+aETG + aVNG
#print LOGFILE,sStart
LogMsg(gFD,sStart)
aList = GetMapServicesToProcess(sys.argv)
LogMsg (gFD, "Publishing %d Map Services using %s" % (len(aList),os.path.basename(CONN_FILE)))
i=1
for sMapService in aList:
	bUpdate = ((sMapService+".MapServer") in aServiceList)
	sMsg = "Creating"
	if bUpdate:
		sMsg = "Updating"
	LogMsg (gFD, "(%d/%d) %s Map Service %s " % (i,len(aList),sMsg,sMapService))
	Publish_MapService(sMapService, bUpdate)
	i += 1
#print ("Return from Creating MapService [%s]: %d" % (sMXD, rc))
LogMsg(gFD,sStart)
LogMsg (gFD, "Finished Publishing %d Map Services" % len(aList))
gFD.close()
