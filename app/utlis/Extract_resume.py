from PyPDF2 import PdfReader

def extract_text_from_resume(resume_path):
    """Basic text extractor for PDF resumes"""
    text = ""
    if resume_path.lower().endswith(".pdf"):
        reader = PdfReader(resume_path)
        for page in reader.pages:
            text += page.extract_text() or ""
    else:
        raise ValueError("Only PDF resumes supported in current setup.")
    return text
