import os
import re

# We can try to import pypdf or pdfplumber if available, or just read text files
# Let's search for any PDF files in D:\gem tenders
pdf_files = []
for root, dirs, files in os.walk(r"D:\gem tenders"):
    for f in files:
        if f.lower().endswith(".pdf"):
            pdf_files.append(os.path.join(root, f))

print(f"Total PDF files: {len(pdf_files)}")

# Let's try to extract text from PDFs and search for mill names
# Since we might not have pypdf/pdfplumber in python directly, let's see if we can import them
try:
    import pypdf
    print("pypdf is available")
except ImportError:
    try:
        import PyPDF2 as pypdf
        print("PyPDF2 is available")
    except ImportError:
        pypdf = None
        print("No PDF library available in python")

mills = [
    "NAJIBABAD", "ANOOPSHAHR", "SULTANPUR", "NANPARA", "BELRAYAN",
    "SAMPURNANAGAR", "RAMALA", "MORNA", "GHOSI", "NANAUTA",
    "SEMIKHERA", "SARSAWAN", "MAHMUDABAD", "TILHAR", "BISALPUR",
    "POWAYAN", "PURANPUR", "BAGPAT", "GAJRAULLA", "FEDRATION",
    "CORPORATION", "KAIAMGANJ", "SATHIAON", "BUDAUN", "BILASPUR"
]

if pypdf:
    for pf in pdf_files[:10]:
        try:
            reader = pypdf.PdfReader(pf)
            text = ""
            for page in reader.pages:
                t = page.extract_text()
                if t: text += t
            
            # Check which mills are in this PDF
            found_mills = []
            for m in mills:
                if re.search(r'\b' + re.escape(m) + r'\b', text, re.I):
                    found_mills.append(m)
            if found_mills:
                print(f"File {os.path.basename(pf)} contains mills: {found_mills}")
        except Exception as e:
            print(f"Error reading {pf}: {e}")
