# file_helper.py

import os
import io
import base64
import shutil
import tempfile

from PIL import Image
from rich.console import Console
from pdf2image import convert_from_path

from utils import logger

class FileHelper:

    class UnsupportedFileTypeError(Exception):
        """
        Custom exception raised when an unsupported file type is encountered.
        For example, if a file's extension is not in EXTENSION_CONTENT_TYPE_MAP
        or if no read function is found in READ_DISPATCH.
        """
        pass

    console = Console()

    # Maps common file extensions to a broad content type understood by the system.
    EXTENSION_CONTENT_TYPE_MAP = {
        '.txt': 'text',
        '.pdf': 'pdf',
        '.json': 'json',
        '.png': 'image',
        '.jpg': 'image',
        '.jpeg': 'image',
        '.gif': 'image',
        '.bmp': 'image',
    }

    def __init__(self):
        """
        Initializes the FileHelper with the path to the media folder.
        The media directory is forced to be two levels up from this file's directory,
        in a folder named "media".
        """
        # Force the media directory to be two directories up from this file's location.
        self.media_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "media")
        # Allowed extensions are the keys from EXTENSION_CONTENT_TYPE_MAP.
        self.allowed_extensions = list(FileHelper.EXTENSION_CONTENT_TYPE_MAP.keys())
        # Ensure the media directory exists.
        os.makedirs(self.media_dir, exist_ok=True)

    def get_media_path(self):
        r"""
        Returns the path to the media folder.
        """
        return self.media_dir

    def get_data(self, file_path: str, content_type: str):
        """
        Retrieves the content of a file based on the assigned `content_type`.
        """
        read_func = self.READ_DISPATCH.get(content_type)
        if not read_func:
            raise self.UnsupportedFileTypeError(f"Unsupported file type: {content_type}")

        try:
            return read_func(file_path)
        except Exception as e:
            logger.error("Error processing file %s as %s: %s", file_path, content_type, e)
            raise

    def get_ignore_list(self, directory):
        """
        Stub

        Reads a list of headings to ignore to skip certain sections while processing text from a scraped webpage.
        """
        return []  # Stub implementation

    @classmethod
    def get_content_type(cls, file_path: str, url: str = None) -> str:
        """
        Determines the content type based on either the presence of a URL or a file extension.
        """
        if url:
            return 'url'
        if file_path:
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            return cls.EXTENSION_CONTENT_TYPE_MAP.get(ext, 'unsupported')
        return 'unsupported'

    def process_file(self, uploaded_file) -> str:
        """
        Processes an uploaded file (txt, pdf, image) and returns its text content.
        """
        filename = uploaded_file.name
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        content_type = self.EXTENSION_CONTENT_TYPE_MAP.get(ext, 'unsupported')
        if content_type == 'unsupported':
            logger.warning("Unsupported file type: %s. Skipping.", filename)
            return ""
        if content_type == 'text':
            uploaded_file.seek(0)
            text_content = uploaded_file.read().decode('utf-8')
            self._set_media_copy_fileobj(uploaded_file, filename)
            return text_content.strip()
        elif content_type == 'pdf':
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                logger.error("PyPDF2 is required to process PDF files.")
                return ""
            uploaded_file.seek(0)
            reader = PdfReader(uploaded_file)
            text_content = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content += page_text + "\n"
            self._set_media_copy_fileobj(uploaded_file, filename)
            return text_content.strip()
        elif content_type == 'image':
            # Flashcard generation from images is not supported.
            logger.warning("Flashcard generation from images is not supported.")
            return ""
        return ""

    def process_text(self, text: str) -> str:
        """
        Processes a raw text input (e.g. pasted content) and returns the cleaned text.
        """
        return text.strip()

    def process_url(self, url):
        """
        Processes the URL by fetching its textual content.
        """
        logger.info("Generating flashcards from web page content.")
        try:
            import requests
            response = requests.get(url)
            if response.ok:
                return response.text
            else:
                logger.error("Failed to fetch URL: %s", url)
                return ""
        except Exception as e:
            logger.error("Error fetching URL %s: %s", url, e)
            return ""

    def _set_media_copy(self, file_path, content_type, media_path, pdf_viewer_path):
        """
        Copies the uploaded file to the media folder.
        """
        try:
            destination = os.path.join(media_path, os.path.basename(file_path))
            shutil.copy(file_path, destination)
            logger.info("Copied file %s to media folder.", file_path)
        except Exception as e:
            logger.error("Error copying media file: %s", e)

    def _set_media_copy_fileobj(self, fileobj, filename):
        """
        Copies the uploaded file object to the media folder.
        """
        try:
            destination = os.path.join(self.get_media_path(), filename)
            fileobj.seek(0)
            with open(destination, "wb") as f:
                f.write(fileobj.read())
            logger.info("Copied file %s to media folder.", filename)
        except Exception as e:
            logger.error("Error copying media file %s: %s", filename, e)

    @staticmethod
    def _get_image(path: str):
        """
        Converts a PDF to one or more images using pdf2image.
        """
        return convert_from_path(path)

    @staticmethod
    def _get_img_uri(img: Image.Image) -> str:
        """
        Encodes a PIL Image as a base64 data URI.
        """
        png_buffer = io.BytesIO()
        img.save(png_buffer, format="PNG")
        png_buffer.seek(0)
        base64_png = base64.b64encode(png_buffer.read()).decode('utf-8')
        return f"data:image/png;base64,{base64_png}"

    @staticmethod
    def _get_plain_text(file_path: str) -> str:
        """
        Reads a file as plain UTF-8 text.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    # Dispatch table mapping content types to their read functions.
    READ_DISPATCH = {
        'text': _get_plain_text,
        'image': lambda path: FileHelper._get_img_uri(Image.open(path)),
        'pdf': lambda path: FileHelper._get_img_uri(FileHelper._get_image(path)[0]) if FileHelper._get_image(path) else "",
    }

    def generate_flashcards_pipeline(self, text: str, flashcard_type='general'):
        """
        Uses the generation pipeline to produce flashcards from the provided text content.
        This method writes the text to a temporary file, creates an instance of ModelPipeline,
        invokes its generation method, then cleans up and returns the generated flashcards.
        """
        temp_file_path = os.path.join(self.get_media_path(), "temp_flashcard.txt")
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(text)
        from utils.model_pipeline import ModelPipeline
        pipeline = ModelPipeline(media_dir=self.get_media_path())
        models = pipeline.generate_flashcards(
            file_path=temp_file_path,
            flashcard_type=flashcard_type,
            media_path=self.get_media_path()
        )
        # Clean up the temporary file.
        os.remove(temp_file_path)
        return models
