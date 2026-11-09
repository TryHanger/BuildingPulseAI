"""Script to stream download representative RBC-Nesbitt files from Figshare archive.
Uses HTTP Range requests to extract files on-the-fly from Public_ScientificData_AHUFaults.zip
without downloading the entire 928 MB archive.
"""
import io
import os
import struct
import zlib
import requests

FIGSHARE_DOWNLOAD_URL = "https://ndownloader.figshare.com/files/57268553"
TOTAL_SIZE = 928675992

def get_central_directory():
    # Read EOCD in last 65KB
    tail_len = 65536
    start_byte = TOTAL_SIZE - tail_len
    r = requests.get(FIGSHARE_DOWNLOAD_URL, headers={"Range": f"bytes={start_byte}-{TOTAL_SIZE - 1}"}, timeout=30)
    tail_bytes = r.content
    eocd_pos = tail_bytes.rfind(b"PK\x05\x06")
    eocd = tail_bytes[eocd_pos:eocd_pos + 22]
    sig, disk, disk_cd, num_cd_disk, num_cd, cd_size, cd_offset, comment_len = struct.unpack("<IHHHHIIH", eocd)
    
    # Read CD
    r_cd = requests.get(FIGSHARE_DOWNLOAD_URL, headers={"Range": f"bytes={cd_offset}-{cd_offset + cd_size - 1}"}, timeout=60)
    cd_bytes = r_cd.content
    
    files = {}
    bio = io.BytesIO(cd_bytes)
    while True:
        cd_sig = bio.read(4)
        if cd_sig != b"PK\x01\x02":
            break
        cd_entry = bio.read(42)
        if len(cd_entry) < 42:
            break
        (version, version_needed, flag, comp_method, mod_time, mod_date,
         crc32, comp_size, uncomp_size, name_len, extra_len, comment_len,
         disk_num, int_attr, ext_attr, local_hdr_offset) = struct.unpack("<HHHHHHIIIHHHHHII", cd_entry)
        fname = bio.read(name_len).decode("utf-8", errors="ignore")
        bio.read(extra_len + comment_len)
        files[fname] = {
            "comp_size": comp_size,
            "uncomp_size": uncomp_size,
            "offset": local_hdr_offset,
        }
    return files

def extract_file(url, file_meta, out_path):
    offset = file_meta["offset"]
    comp_size = file_meta["comp_size"]
    # Local header is 30 bytes + variable name/extra
    fetch_len = comp_size + 512
    r = requests.get(url, headers={"Range": f"bytes={offset}-{offset + fetch_len}"}, timeout=60)
    data = r.content
    sig, ver, flag, method, mtime, mdate, crc, csize_hdr, usize_hdr, nlen, elen = struct.unpack("<IHHHHHIIIHH", data[:30])
    data_start = 30 + nlen + elen
    comp_data = data[data_start:data_start + comp_size]
    if method == 8: # deflate
        uncomp = zlib.decompress(comp_data, -15)
    elif method == 0: # stored
        uncomp = comp_data
    else:
        raise ValueError(f"Unsupported compression method {method}")
        
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(uncomp)
    print(f"Extracted: {out_path} ({len(uncomp)} bytes)")

def main():
    print("Reading Figshare central directory...")
    files = get_central_directory()
    nesbitt_files = {k: v for k, v in files.items() if "02_RBC-Nesbitt" in k and not k.endswith("/")}
    print(f"Found {len(nesbitt_files)} RBC-Nesbitt files in remote zip.")
    
    # Target files to fetch
    targets = [
        "Public_ScientificData_AHUFaults/02_RBC-Nesbitt/Baselines/20160601_Baseline.csv",
        "Public_ScientificData_AHUFaults/02_RBC-Nesbitt/Baselines/20160712_Baseline.csv",
        "Public_ScientificData_AHUFaults/02_RBC-Nesbitt/20170811_CooCoiValStuck_100.csv",
        "Public_ScientificData_AHUFaults/02_RBC-Nesbitt/20180711_CooCoiValStuck_80.csv",
        "Public_ScientificData_AHUFaults/02_RBC-Nesbitt/20170718_OADamStuck_100.csv",
        "Public_ScientificData_AHUFaults/02_RBC-Nesbitt/20180710_OADamStuck_30.csv",
    ]
    
    out_dir = os.path.join("data", "raw", "rbc_nesbitt")
    for t in targets:
        if t in files:
            fname = os.path.basename(t)
            dest = os.path.join(out_dir, fname)
            extract_file(FIGSHARE_DOWNLOAD_URL, files[t], dest)
        else:
            print(f"Warning: target {t} not found in zip")
            
    print("All sample RBC-Nesbitt files fetched successfully!")

if __name__ == "__main__":
    main()
