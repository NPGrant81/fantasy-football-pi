import os

# signal to application code that we're running under pytest
os.environ['TESTING'] = '1'
