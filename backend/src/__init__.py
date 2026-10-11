# Lets every script accept  --region <name>  (it is read before src.config loads).
import os
import sys

if "--region" in sys.argv:
    _i = sys.argv.index("--region")
    if _i + 1 < len(sys.argv):
        os.environ["NL_REGION"] = sys.argv[_i + 1]
