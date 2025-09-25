import pdfplumber

# Extract text from a sample PDF to see the actual format
pdf_file = "test_cvs/tech_cv_033.pdf"  # 781 characters, technology CV

print("=" * 60)
print("DEBUGGING PDF TEXT FORMAT")
print("=" * 60)

try:
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    
    print(f"File: {pdf_file}")
    print(f"Length: {len(text)} characters")
    print("=" * 60)
    print("RAW TEXT:")
    print("=" * 60)
    print(repr(text))  # Show exact format with \n, spaces, etc.
    print("=" * 60)
    print("FORMATTED TEXT:")
    print("=" * 60)
    print(text)
    print("=" * 60)
    
    # Look for potential experience sections
    lines = text.split('\n')
    print("LINES ANALYSIS:")
    print("=" * 60)
    for i, line in enumerate(lines):
        if line.strip():
            print(f"Line {i:2d}: {repr(line)}")
    
except Exception as e:
    print(f"Error: {e}")
