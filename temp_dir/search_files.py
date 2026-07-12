import os

search_dirs = [r"D:\gem tenders", r"d:\tenderTracker"]
found = []
for sd in search_dirs:
    for root, dirs, files in os.walk(sd):
        for f in files:
            if "7673431" in f:
                found.append(os.path.join(root, f))

print("Found files:", found)
