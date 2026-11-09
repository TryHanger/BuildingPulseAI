import requests
import struct
import io
import zipfile

url = 'https://ndownloader.figshare.com/files/57268553'
total_size = 928675992

# EOCD is in the last 65KB of the file
tail_len = 65536
start_byte = total_size - tail_len
r_tail = requests.get(url, headers={'Range': f'bytes={start_byte}-{total_size - 1}'}, timeout=20)
tail_bytes = r_tail.content

print(f"Tail bytes fetched: {len(tail_bytes)}")
# Find EOCD signature b'PK\x05\x06'
eocd_pos = tail_bytes.rfind(b'PK\x05\x06')
if eocd_pos == -1:
    print("EOCD not found in last 65KB, checking Zip64...")
else:
    print(f"Found standard EOCD at offset {eocd_pos} in tail!")
    eocd = tail_bytes[eocd_pos:eocd_pos + 22]
    sig, disk, disk_cd, num_cd_disk, num_cd, cd_size, cd_offset, comment_len = struct.unpack('<IHHHHIIH', eocd)
    print(f"Total files in Central Directory: {num_cd}")
    print(f"Central Directory size: {cd_size} bytes, offset: {cd_offset}")

    # Fetch central directory
    cd_start = cd_offset
    cd_end = cd_offset + cd_size - 1
    r_cd = requests.get(url, headers={'Range': f'bytes={cd_start}-{cd_end}'}, timeout=30)
    cd_bytes = r_cd.content
    print(f"Central directory bytes fetched: {len(cd_bytes)}")

    # Parse central directory entries
    files = []
    bio = io.BytesIO(cd_bytes)
    while True:
        cd_sig = bio.read(4)
        if cd_sig != b'PK\x01\x02':
            break
        cd_entry = bio.read(42)
        if len(cd_entry) < 42:
            break
        (version, version_needed, flag, comp_method, mod_time, mod_date,
         crc32, comp_size, uncomp_size, name_len, extra_len, comment_len,
         disk_num, int_attr, ext_attr, local_hdr_offset) = struct.unpack('<HHHHHHIIIHHHHHII', cd_entry)
        fname = bio.read(name_len).decode('utf-8', errors='ignore')
        bio.read(extra_len + comment_len)
        files.append({
            'name': fname,
            'comp_size': comp_size,
            'uncomp_size': uncomp_size,
            'offset': local_hdr_offset
        })

    print(f"\nSuccessfully parsed {len(files)} file entries inside Public_ScientificData_AHUFaults.zip:")
    for f in files:
        print(f"  {f['name']} ({f['uncomp_size'] / 1024 / 1024:.2f} MB)")
