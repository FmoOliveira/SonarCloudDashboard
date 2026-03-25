import os

os.environ["DEMO_MODE"] = "1"
os.environ["AZURE_AD_TENANT_ID"] = "dummy"
os.environ["AZURE_AD_CLIENT_ID"] = "dummy"
os.environ["AZURE_AD_CLIENT_SECRET"] = "dummy"

import subprocess
subprocess.run(["pytest", "tests/"])
