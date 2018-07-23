'''
Constants
'''
import os
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle

FIRMWARE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + \
                               '/trackercontroller/firmware/'

#PDF Styles
STYLES = {'title': ParagraphStyle('title',
	                                 fontName='Helvetica-Bold',
	                                 fontSize=14,
	                                 leading=42,
	                                 alignment=TA_CENTER,
	                                )}

GATEWAY_VERSION = "0.9.9"
MASTER_VERSION= "0.9.9"
TRACKER_VERSION = "0.9.9"

