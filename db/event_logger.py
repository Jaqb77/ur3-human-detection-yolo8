from openpyxl import Workbook
from openpyxl.reader.excel import load_workbook
import os

def init_check(filename, data):
    if os.path.exists(filename):
        wb = load_workbook(filename)
        ws = wb.active 
    else:
        wb = Workbook() 
        ws = wb.active
        ws.append(list(data.keys()))
