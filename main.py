#!/usr/bin/env python3
"""
StoryLang - Interactive Story Compiler & Execution Engine
A compiler construction project that lets users build and live stories interactively.
"""
 
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
 
from engine.repl import StoryREPL
 
def main():
    repl = StoryREPL()
    repl.run()
 
if __name__ == "__main__":
    main()
 