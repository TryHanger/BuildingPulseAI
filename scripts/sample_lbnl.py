import urllib.request
import zipfile
import io

from inspect_remote_zip import RemoteZipFile

url = "https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_SDAHU/LBNL_FDD_Data_Sets_SDAHU.zip"
rz = RemoteZipFile(url)
zf = zipfile.ZipFile(rz)

target_name = "LBNL_FDD_Dataset_SDAHU/AHU_annual.csv"
print(f"Opening {target_name} inside zip...")
with zf.open(target_name) as f:
    # Read first 100 lines
    lines = []
    for _ in range(10):
        line = f.readline().decode('utf-8', errors='ignore')
        lines.append(line)
        print(line.strip())
