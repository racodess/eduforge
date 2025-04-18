# file_helper.py

from __future__ import annotations
import os, io, json, base64, shutil, tempfile, re
from typing import List

from PIL import Image
from rich.console import Console
from pdf2image import convert_from_path

from utils.logger import logger
from utils.scraper import process_url as scrape_process_url
from utils import model_schemas


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

    def process_file(self, uploaded_file, start_page=None, end_page=None) -> str:
        """
        Processes an uploaded file (txt, pdf, image) and returns its text content or image data URI.
        Added support for processing PDF files with a specified page range and images using base64 URIs.
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
            pages = reader.pages
            if start_page is not None and end_page is not None:
                pages = reader.pages[start_page - 1: end_page]
            for page in pages:
                page_text = page.extract_text()
                if page_text:
                    text_content += page_text + "\n"
            self._set_media_copy_fileobj(uploaded_file, filename)
            return text_content.strip()
        elif content_type == 'image':
            # Process image file using base64 image URI conversion.
            uploaded_file.seek(0)
            self._set_media_copy_fileobj(uploaded_file, filename)
            # Ensure the file pointer is at the start so Pillow can read it.
            uploaded_file.seek(0)
            image = Image.open(uploaded_file)
            image_uri = FileHelper._get_img_uri(image)
            return image_uri
        return ""

    def process_text(self, text: str) -> str:
        """
        Processes a raw text input (e.g. pasted content) and returns the cleaned text.
        """
        return text.strip()

    def process_url(self, url):
        """
        Fetch readable page text from *url*.

        Steps
        -----
        1.  Use :pyfunc:`utils.scraper.process_url` to get heading‑based sections.
        2.  Re‑assemble into Markdown (we keep headings so downstream chunk
            merging can still use them as cues).
        3.  Pipe the Markdown through the LLM rewrite assistant to remove
            noise, duplicates, etc.
        """
        from utils.model_helper import ModelHelper

        logger.info("Scraping and rewriting %s", url)
        scraped = scrape_process_url(url)
        if not scraped:
            return ""

        merged_md = []
        for sec in scraped["sections"]:
            merged_md.append(f"## {sec['title']}\n{sec['content']}")
        markdown_text = "\n\n".join(merged_md)

        helper = ModelHelper()
        try:
            rewritten = helper.get_rewrite(markdown_text, content_type="url")
            return rewritten.strip()
        except Exception as e:
            logger.error("Rewrite failed for %s: %s", url, e, exc_info=True)
            # Fall back to raw markdown if rewrite bombs out
            return markdown_text.strip()

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

    def regenerate_flashcard(self, flashcard: "model_schemas.FlashcardItem"):
        """
        Calls the LLM to regenerate a single flashcard, using the card's
        stored `data` excerpt as context. Falls back to the old front/back if
        `data` is missing.
        """

        from utils.model_helper import ModelHelper
        from utils.prompts import REGENERATE_FLASHCARD_PROMPT

        helper = ModelHelper()

        user_payload = {
            "original front": flashcard.front,
            "original back": flashcard.back,
            "context": flashcard.data or ""
            }

        # JSON‑encode so the LLM sees a text blob, not a Python object.
        user_payload = json.dumps({
            "original front": flashcard.front,
            "original back": flashcard.back,
            "context": flashcard.data or ""
            }, 
            ensure_ascii=False
            )

        response = helper.get_flashcards(
            conversation=[],
            system_message=REGENERATE_FLASHCARD_PROMPT,
            user_text=user_payload,
            run_as_image=False,
            response_format=model_schemas.FlashcardItem
        )

        new_card = model_schemas.FlashcardItem.model_validate_json(response)
        return new_card
    
    def regenerate_note(self, note: "model_schemas.NoteItem"):
        from utils.model_helper import ModelHelper
        from utils.prompts import REGENERATE_NOTE_PROMPT

        helper = ModelHelper()

        payload = json.dumps(
            {
                "original title": note.title,
                "original content": note.content,
                "context": note.data or ""
            },
            ensure_ascii=False
        )

        response = helper.get_flashcards(      # keeps convo util
            conversation=[],
            system_message=REGENERATE_NOTE_PROMPT,
            user_text=payload,
            run_as_image=False,
            response_format=model_schemas.NoteItem
        )
        
        return model_schemas.NoteItem.model_validate_json(response)
    
    def regenerate_graph(self, graph_note: "model_schemas.NoteItem", *, graph_type: str):
        from utils.model_helper import ModelHelper
        from utils.prompts import REGENERATE_GRAPH_PROMPT

        helper = ModelHelper()
        payload = json.dumps(
            {
                "original title": graph_note.title,
                "original content": graph_note.content,
                "context": graph_note.data or "",
                "graph_type": graph_type,
            },
            ensure_ascii=False,
        )
        response = helper.get_flashcards(
            conversation=[],
            system_message=REGENERATE_GRAPH_PROMPT,
            user_text=payload,
            run_as_image=False,
            response_format=model_schemas.NoteItem,
        )
        return model_schemas.NoteItem.model_validate_json(response)

    def generate_flashcards_pipeline(self, text: str, flashcard_type='general'):
        """
        Uses the generation pipeline to produce flashcards from the provided content.
        
        When the content is a base64 image URI (detected if it starts with "data:image"),
        bypass writing to a temporary file and directly create an image chunk.
        
        For text input, writes the content to a temporary .txt file.
        """
        from utils.model_pipeline import ModelPipeline
        pipeline = ModelPipeline(media_dir=self.get_media_path())
        
        # Check if the text is actually a base64-encoded image.
        if text.startswith("data:image"):
            models = pipeline._process_chunks(
                chunks=[{"title": "Uploaded Image", "content": text}],
                card_type=flashcard_type,
                url_name="",
                file_name="uploaded_image.png",  # Dummy filename with correct extension
                content_type="image",
                media_path=self.get_media_path()
            )
        else:
            # Handle as text input: write to a temporary file first.
            temp_file_path = os.path.join(self.get_media_path(), "temp_flashcard.txt")
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(text)
            models = pipeline.generate_flashcards(
                file_path=temp_file_path,
                flashcard_type=flashcard_type,
                media_path=self.get_media_path()
            )
            # Clean up the temporary file.
            os.remove(temp_file_path)
        
        return models
    
    def generate_notes_pipeline(self, text: str):
        """
        Produce study **notes** from *text* and return a list[model_schemas.Note]
        """
        from utils.model_pipeline import ModelPipeline
        pipeline = ModelPipeline(media_dir=self.get_media_path())

        if text.startswith("data:image"):
            models = pipeline._process_chunks(
                chunks=[{"title": "Uploaded Image", "content": text}],
                card_type="note",                  # key flag
                url_name="",
                file_name="uploaded_image.png",
                content_type="image",
                media_path=self.get_media_path()
            )
        else:
            tmp = os.path.join(self.get_media_path(), "temp_note.txt")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            models = pipeline.generate_notes(file_path=tmp, media_path=self.get_media_path())
            os.remove(tmp)
        return models
    
    def generate_graphs_pipeline(self, text: str, graph_type: str):
        """Return **list[model_schemas.NoteItem]** representing either
        a *mind map* or a *knowledge graph* generated from *text*.
        """
        from utils.model_helper import ModelHelper
        from utils.prompts import (
            MIND_MAP_GENERATION_PROMPT,
            KNOWLEDGE_GRAPH_GENERATION_PROMPT,
        )

        prompt = (
            MIND_MAP_GENERATION_PROMPT
            if graph_type == "mind_map"
            else KNOWLEDGE_GRAPH_GENERATION_PROMPT
        )

        helper = ModelHelper()
        # We bypass the bigger chunk‑merging pipeline – for graphs we want a
        # holistic view.  The *NoteItem* response keeps the data model simple.
        response = helper.get_flashcards(
            conversation=[],
            system_message=prompt,
            user_text=text,
            run_as_image=False,
            response_format=model_schemas.NoteItem,
        )
        note = model_schemas.NoteItem.model_validate_json(response)
        if not re.search(r"```(?:graphviz|dot)\s", note.content, re.IGNORECASE):
            note.content = f"```graphviz\n{note.content.strip()}\n```"
        return [note]

    # Dispatch table mapping content types to their read functions.
    READ_DISPATCH = {
        'text': _get_plain_text,
        'image': lambda path: FileHelper._get_img_uri(Image.open(path)),
        'pdf': lambda path: FileHelper._get_img_uri(FileHelper._get_image(path)[0]) if FileHelper._get_image(path) else "",
    }
