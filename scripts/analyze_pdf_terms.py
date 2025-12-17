
from pypdf import PdfReader
import os

def extract_text_from_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return

    try:
        reader = PdfReader(pdf_path)
        print(f"Total Pages: {len(reader.pages)}")
        
        # Print first few pages to understand structure
        for i, page in enumerate(reader.pages[:5]):
            print(f"--- Page {i+1} ---")
            print(page.extract_text())
            print("\n")
            
    except Exception as e:
        print(f"Error reading PDF: {e}")

if __name__ == "__main__":
    pdf_path = "02616234871.pdf"
    extract_text_from_pdf(pdf_path)
