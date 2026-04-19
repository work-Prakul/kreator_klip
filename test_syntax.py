#!/usr/bin/env python
import sys
import traceback

try:
    import main
except SyntaxError as e:
    print("SYNTAX ERROR:")
    print(f"  File: {e.filename}")
    print(f"  Line: {e.lineno}")
    print(f"  Offset: {e.offset}")
    print(f"  Text: {e.text}")
    print(f"  Message: {e.msg}")
    traceback.print_exc()
except Exception as e:
    print("OTHER ERROR:")
    traceback.print_exc()
