import requests
import struct
import io
import zlib
from pathlib import Path

url = 'https://ndownloader.figshare.com/files/57268553'
total_size = 928675992
tail_len = 65536
start_byte = total_size - tail_len
r_tail = requests.get(url, headers={'Range': f'bytes={start_byte}-{total_size - 1}'}, timeout=20)
tail_bytes = r_tail.content
eocd_pos = tail_bytes.rfind(b'PK\x05\x06')
eocd = tail_bytes[eocd_pos:eocd_pos + 22]
sig, disk, disk_cd, num_cd_disk, num_cd, cd_size, cd_offset, comment_len = struct.unpack('<IHHHHIIH', eocd)
r_cd = requests.get(url, headers={'Range': f'bytes={cd_offset}-{cd_offset + cd_size - 1}'}, timeout=30)
cd_bytes = r_cd.content

bio = io.BytesIO(cd_bytes)
targets = ['20170618_Baseline.csv', '20170702_Baseline.csv']
target_entries = {}
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
    for t in targets:
        if fname.endswith(t):
            target_entries[t] = {
                'offset': local_hdr_offset,
                'comp_size': comp_size,
                'uncomp_size': uncomp_size,
                'method': comp_method,
                'name': fname
            }

out_dir = Path('data/raw/rbc_nesbitt')
for t, info in target_entries.items():
    print('Fetching', t, 'offset:', info['offset'])
    r_hdr = requests.get(url, headers={'Range': f"bytes={info['offset']}-{info['offset'] + 600}"}, timeout=20)
    hdr_bytes = r_hdr.content
    loc_sig, loc_ver, loc_flag, loc_method, loc_time, loc_date, loc_crc, loc_csize, loc_usize, loc_nlen, loc_elen = struct.unpack('<IHHHHHIIIHH', hdr_bytes[:30])
    data_start = info['offset'] + 30 + loc_nlen + loc_elen
    data_end = data_start + info['comp_size'] - 1
    
    r_data = requests.get(url, headers={'Range': f"bytes={data_start}-{data_end}"}, timeout=30)
    data_bytes = r_data.content
    if info['method'] == 8:
        decomp = zlib.decompress(data_bytes, -15)
    else:
        decomp = data_bytes
        
    out_file = out_dir / t
    with open(out_file, 'wb') as f:
        f.write(decomp)
    print('Saved', out_file, len(decomp), 'bytes')
