# ai_file_utils.py

import os
import base64
import io
from typing import Optional

try:
    from pdfminer.high_level import extract_text
except ImportError:
    extract_text = None

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

try:
    from PIL import Image
except ImportError:
    Image = None

class UnsupportedFileTypeError(Exception):
    """
    Raised when an unsupported file type is encountered.
    """
    pass

EXTENSION_CONTENT_TYPE_MAP = {
    '.txt':  'text',
    '.pdf':  'pdf',
    '.png':  'image',
    '.jpg':  'image',
    '.jpeg': 'image',
    '.gif':  'image',
    '.bmp':  'image'
}

def get_content_type(file_path: str) -> str:
    """
    Determines a file's content type based on its extension.
    """
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    return EXTENSION_CONTENT_TYPE_MAP.get(ext, 'unsupported')

def read_text_file(file_path: str) -> str:
    """
    Reads a text file and returns its content.
    """
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def read_pdf_as_text(file_path: str) -> Optional[str]:
    """
    Extracts text from a PDF using pdfminer (if available).
    """
    if extract_text is None:
        return None
    try:
        return extract_text(file_path)
    except Exception:
        return None

def pdf_first_page_as_base64(file_path: str) -> Optional[str]:
    """
    Converts the first page of a PDF to a base64-encoded PNG image.
    """
    if not convert_from_path or not Image:
        return None
    try:
        pages = convert_from_path(file_path, dpi=150)
        if pages:
            first_page = pages[0]
            return pil_image_to_base64(first_page)
    except Exception:
        pass
    return None

def read_image_as_base64(file_path: str) -> Optional[str]:
    """
    Reads an image file and returns a base64 data URI.
    """
    if not Image:
        return None
    try:
        with Image.open(file_path) as img:
            return pil_image_to_base64(img)
    except Exception:
        return None

def pil_image_to_base64(img: "Image.Image") -> str:
    """
    Converts a PIL Image to a PNG data URI string.
    """
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    base64_data = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{base64_data}"

def read_file_contents_for_ai(file_path: str) -> str:
    """
    High-level function for extracting text from a file for AI processing.
      - .txt: full text
      - .pdf: extracted text (if possible) or a simulated text placeholder
      - .image: simulated placeholder text (or OCR could be integrated)
    """
    ctype = get_content_type(file_path)
    filename = os.path.basename(file_path)

    if ctype == 'text':
        return read_text_file(file_path)
    elif ctype == 'pdf':
        pdf_text = read_pdf_as_text(file_path)
        if pdf_text and pdf_text.strip():
            return pdf_text
        else:
            return f"Simulated text from {filename}"
    elif ctype == 'image':
        return f"Simulated text from {filename}"
    else:
        return f"Simulated text from {filename}"

def process_file(self, uploaded_file) -> str:
    """
    Accepts a Streamlit UploadedFile object, writes it to a temporary file,
    extracts its content using read_file_contents_for_ai, and returns the text.
    """
    if not uploaded_file:
        return ""

    suffix = os.path.splitext(uploaded_file.name)[-1].lower() or ".txt"
    # Write the file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name
    
    content = read_file_contents_for_ai(tmp_path)
    # Clean up the temporary file
    os.remove(tmp_path)
    return content

def process_text(self, text_input: str) -> str:
    """
    Processes pasted text; performs any needed cleanup (currently a passthrough).
    """
    return text_input

def process_url(self, url_input: str) -> str:
    """
    Processes content from a URL.
    This implementation returns placeholder text.
    A full implementation might use requests and HTML parsing.
    """
    # For example, you might implement:
    # import requests
    # try:
    #     response = requests.get(url_input, timeout=10)
    #     if response.status_code == 200:
    #         return response.text
    # except Exception as e:
    #     return ""
    return f"Simulated text retrieved from {url_input}"
