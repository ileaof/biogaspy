"""Wrapper executavel: python Examples/MEA.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from biogassim.Examples.MEA import main

if __name__ == "__main__":
    main()
