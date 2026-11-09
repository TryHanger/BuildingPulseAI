import pypdf

reader = pypdf.PdfReader('docs/LBNL_FDD_Data_Sets_SDAHU.pdf')
with open('docs/LBNL_PDF_TEXT.txt', 'w', encoding='utf-8') as f:
    for i, page in enumerate(reader.pages):
        f.write(f"\n\n=== PAGE {i+1} ===\n\n")
        f.write(page.extract_text() or "")
print(f"Extracted {len(reader.pages)} pages to docs/LBNL_PDF_TEXT.txt")
