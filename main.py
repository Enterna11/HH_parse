import sys
import os

if '-u' in sys.argv:
    os.system('python source/gui.py')
else:
    os.system('python source/parser.py')
    
