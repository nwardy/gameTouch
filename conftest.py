"""Put the project root on sys.path so `pytest` finds the packages."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
