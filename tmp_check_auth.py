import sys
import os
import auth_manager
import inspect

print(f"auth_manager file: {auth_manager.__file__}")
print(f"do_logout signature: {inspect.signature(auth_manager.do_logout)}")
print(f"sys.path: {sys.path}")
