import csv

csv_path = "data/raw/rbc_nesbitt/20160601_Baseline.csv"
with open(csv_path, "r", encoding="latin1") as f:
    reader = csv.reader(f)
    headers = next(reader)

print("--- DETAILED COLUMNS 30 to 90 ---")
for i in range(30, 90):
    clean = headers[i].encode("ascii", "replace").decode("ascii")
    print(f"Col {i:2d}: {clean}")
