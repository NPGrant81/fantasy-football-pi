import os

# signal to application code that we're running under pytest
os.environ['TESTING'] = '1'
os.environ['DATABASE_URL'] = 'sqlite:///./pytest_backend.db'
