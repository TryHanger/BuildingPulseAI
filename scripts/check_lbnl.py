import urllib.request
import re

def probe(url):
    print(f"=== Probing {url} ===")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            print("Status:", resp.status)
            for m in re.finditer(r'<a\s+(?:[^>]*?\s+)?href=(["\'])(.*?)\1[^>]*>(.*?)</a>', content, re.IGNORECASE | re.DOTALL):
                href = m.group(2)
                text = re.sub(r'<[^>]+>', '', m.group(3)).strip()
                if any(x in href.lower() or x in text.lower() for x in ["download", "zip", "csv", "box.com", "drive.google", "sd-ahu", "inventory", "data"]):
                    print(f"  [Link] {text} -> {href}")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    probe("https://faultdetection.lbl.gov/dataset/simulated-sd-ahu/")
    probe("https://faultdetection.lbl.gov/data/")
