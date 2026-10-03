import json
import sys

from pipeline.runner import run_pipeline

DEFAULT = "T0tal: Rs l200 | Pald: 1000 | Due: 200"

text = " ".join(sys.argv[1:]) or DEFAULT
print("INPUT:", text)

for step, name in [(1, "Step 1 - extract"), (2, "Step 2 - normalize"),
                   (3, "Step 3 - classify"), (4, "Step 4 - final")]:
    print("\n" + name)
    print(json.dumps(run_pipeline(text, upto=step), indent=2))