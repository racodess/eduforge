# file_helper.py

"""
Utilities for processing user-supplied files, text, URLs, and regenerating study items.
Supports reading and converting text, PDFs, images, and handling media storage,
plus integration with scraping and LLM-based rewriting and regeneration.
"""

from __future__ import annotations
import os
import io
import json
import base64
import re
from typing import List

from PIL import Image
from rich.console import Console
from pdf2image import convert_from_path

from utils.model_helper import ModelHelper
from utils.logger import logger
from utils.scraper import process_url as scrape_process_url
from utils import model_schemas


class FileHelper:
    """
    Helper class for reading various file types (text, PDF, image),
    converting them to consumable formats, storing media, and
    orchestrating scraping and LLM-based rewriting pipelines.
    """

    class UnsupportedFileTypeError(Exception):
        """
        Raised when encountering a file type not supported by READ_DISPATCH
        or EXTENSION_CONTENT_TYPE_MAP.
        """
        pass

    # Shared console for logging to terminal
    console = Console()

    # Map file extensions to abstract content types
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
        Initialize FileHelper, creating a media directory two levels up.
        Allowed_extensions lists the keys from EXTENSION_CONTENT_TYPE_MAP.
        """
        # Determine media folder location relative to this file
        self.media_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "media"
        )

        # List of permitted file extensions
        self.allowed_extensions = list(FileHelper.EXTENSION_CONTENT_TYPE_MAP.keys())

        # Ensure media directory exists
        os.makedirs(self.media_dir, exist_ok=True)

    def get_media_path(self) -> str:
        """
        Return the path to the media directory for storing uploaded files.
        """
        return self.media_dir

    def get_data(self, file_path: str, content_type: str):
        """
        Read and return data from a file based on the provided content_type.
        Delegates to functions in READ_DISPATCH.
        Raises UnsupportedFileTypeError if no reader exists.
        """
        read_func = self.READ_DISPATCH.get(content_type)
        if not read_func:
            raise self.UnsupportedFileTypeError(
                f"Unsupported file type: {content_type}"
            )
        try:
            return read_func(file_path)
        except Exception as e:
            logger.error(
                "Error processing file %s as %s: %s",
                file_path, content_type, e
            )
            raise

    def get_ignore_list(self, directory) -> List[str]:
        """
        Stub: Return a list of headings to ignore when scraping.
        Intended for future customization via config files.
        """
        return [] # No ignore rules by default

    @classmethod
    def get_content_type(cls, file_path: str, url: str = None) -> str:
        """
        Deduce content_type: 'url' if URL is provided, else map by file extension.
        Returns 'unsupported' for unknown extensions.
        """
        if url:
            return 'url'
        if file_path:
            _, ext = os.path.splitext(file_path)
            return cls.EXTENSION_CONTENT_TYPE_MAP.get(ext.lower(), 'unsupported')
        return 'unsupported'

    def process_file(
        self,
        uploaded_file,
        start_page=None,
        end_page=None
    ) -> str:
        """
        Convert an uploaded_file (.txt, .pdf, image) to text or data URI.
        Supports page-range extraction for PDFs and base64 encoding for images.
        Copies the original file into media_dir for storage.
        """
        filename = uploaded_file.name
        _, ext = os.path.splitext(filename)
        content_type = self.EXTENSION_CONTENT_TYPE_MAP.get(ext.lower(), 'unsupported')

        if content_type == 'unsupported':
            logger.warning("Unsupported file type: %s. Skipping.", filename)
            return ""

        if content_type == 'text':
            # Read text file, copy it to media, and return its contents
            uploaded_file.seek(0)
            text_content = uploaded_file.read().decode('utf-8')
            self._set_media_copy_fileobj(uploaded_file, filename)
            return text_content.strip()

        elif content_type == 'pdf':
            # Extract text from PDF pages via PyPDF2
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                logger.error("PyPDF2 is required to process PDF files.")
                return ""
            uploaded_file.seek(0)
            reader = PdfReader(uploaded_file)
            pages = reader.pages
            
            # Apply page slicing if requested
            if start_page is not None and end_page is not None:
                pages = pages[start_page-1:end_page]
            text = ""
            for page in pages:
                page_text = page.extract_text() or ''
                text += page_text + "\n"
            self._set_media_copy_fileobj(uploaded_file, filename)
            return text.strip()

        elif content_type == 'image':
            # Convert image to base64 data URI for model consumption
            uploaded_file.seek(0)
            self._set_media_copy_fileobj(uploaded_file, filename)
            uploaded_file.seek(0)
            image = Image.open(uploaded_file)
            return FileHelper._get_img_uri(image)

        return ""

    def process_text(self, text: str) -> str:
        """
        Clean and return pasted text input.
        """
        return text.strip()

    def process_url(self, url: str) -> str:
        """
        Scrape a URL into Markdown sections, reassemble them,
        then pass through LLM rewrite to clean noise.
        Returns rewritten Markdown or raw markdown on failure.
        """
        logger.info("Scraping and rewriting %s", url)
        scraped = scrape_process_url(url)
        if not scraped:
            return ""

        # Merge sections into a single markdown string
        parts = [f"## {sec['title']}\n{sec['content']}" for sec in scraped['sections']]
        markdown_text = "\n\n".join(parts)

        helper = ModelHelper()
        try:
            rewritten = helper.get_rewrite(markdown_text, content_type="url")
            return rewritten.strip()
        except Exception as e:
            logger.error("Rewrite failed for %s: %s", url, e, exc_info=True)
            return markdown_text.strip()

    def _set_media_copy_fileobj(self, fileobj, filename: str) -> None:
        """
        Save an uploaded file object into media_dir under `filename`.
        """
        try:
            dest = os.path.join(self.get_media_path(), filename)
            fileobj.seek(0)
            with open(dest, 'wb') as f:
                f.write(fileobj.read())
            logger.info("Copied file %s to media folder.", filename)
        except Exception as e:
            logger.error("Error copying media file %s: %s", filename, e)

    @staticmethod
    def _get_image(path: str) -> List[Image.Image]:
        """
        Convert PDF path to list of PIL Images using pdf2image.
        """
        return convert_from_path(path)

    @staticmethod
    def _get_img_uri(img: Image.Image) -> str:
        """
        Encode a PIL Image as a base64 data URI (PNG format).
        """
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        b64 = base64.b64encode(buffer.read()).decode('utf-8')
        return f"data:image/png;base64,{b64}"

    @staticmethod
    def _get_plain_text(file_path: str) -> str:
        """
        Read a text file from disk as UTF-8 and return its contents.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def regenerate_flashcard(self, flashcard: "model_schemas.FlashcardItem") -> model_schemas.FlashcardItem:
        """
        Ask LLM to regenerate a flashcard from its existing front/back/context.
        Returns a new FlashcardItem model instance.
        """
        from utils.model_helper import ModelHelper
        from utils.prompts import REGENERATE_FLASHCARD_PROMPT

        helper = ModelHelper()
        payload = json.dumps({
            "original front": flashcard.front,
            "original back": flashcard.back,
            "context": flashcard.data or ""
        }, ensure_ascii=False)

        response = helper.get_flashcards(
            conversation=[],
            system_message=REGENERATE_FLASHCARD_PROMPT,
            user_text=payload,
            run_as_image=False,
            response_format=model_schemas.FlashcardItem
        )
        return model_schemas.FlashcardItem.model_validate_json(response)

    def regenerate_note(self, note: "model_schemas.NoteItem") -> model_schemas.NoteItem:
        """
        Ask LLM to regenerate a note tab from its existing title/content/context.
        Returns a new NoteItem model.
        """
        from utils.model_helper import ModelHelper
        from utils.prompts import REGENERATE_NOTE_PROMPT

        helper = ModelHelper()
        payload = json.dumps({
            "original title": note.title,
            "original content": note.content,
            "context": note.data or ""
        }, ensure_ascii=False)

        response = helper.get_flashcards(
            conversation=[],
            system_message=REGENERATE_NOTE_PROMPT,
            user_text=payload,
            run_as_image=False,
            response_format=model_schemas.NoteItem
        )
        return model_schemas.NoteItem.model_validate_json(response)

    def regenerate_graph(
        self,
        graph_note: "model_schemas.NoteItem",
        *,
        graph_type: str
    ) -> model_schemas.NoteItem:
        """
        Ask LLM to regenerate a graph from its content and type (mind_map/knowledge_graph).
        Ensures content is wrapped in a graphviz code block.
        """
        from utils.model_helper import ModelHelper
        from utils.prompts import REGENERATE_GRAPH_PROMPT

        helper = ModelHelper()
        payload = json.dumps({
            "original title": graph_note.title,
            "original content": graph_note.content,
            "context": graph_note.data or "",
            "graph_type": graph_type
        }, ensure_ascii=False)

        response = helper.get_flashcards(
            conversation=[],
            system_message=REGENERATE_GRAPH_PROMPT,
            user_text=payload,
            run_as_image=False,
            response_format=model_schemas.NoteItem
        )
        note = model_schemas.NoteItem.model_validate_json(response)

        # Wrap raw content in graphviz block if missing
        if not re.search(r"```(?:graphviz|dot)\s", note.content, re.IGNORECASE):
            note.content = f"```graphviz\n{note.content.strip()}\n```"
        return note

    def generate_flashcards_pipeline(self, text: str, flashcard_type='general') -> List[model_schemas.Flashcard]:
        """
        High-level entry for generating flashcards from text or image data URI.
        Writes to temp file for text inputs or uses direct chunk if image.
        Cleans up temp files afterward.
        """
        from utils.model_pipeline import ModelPipeline
        pipeline = ModelPipeline(media_dir=self.get_media_path())
        
        # Image data URI path
        if text.startswith("data:image"):
            chunks = [{"title": "Uploaded Image", "content": text}]
            models = pipeline._process_chunks(
                chunks=chunks,
                card_type=flashcard_type,
                url_name="",
                file_name="uploaded_image.png",
                content_type="image",
                media_path=self.get_media_path()
            )
        else:
            # Write text to a temporary file for processing
            tmp = os.path.join(self.get_media_path(), "temp_flashcard.txt")
            with open(tmp, 'w', encoding='utf-8') as f:
                f.write(text)
            models = pipeline.generate_flashcards(
                file_path=tmp,
                flashcard_type=flashcard_type,
                media_path=self.get_media_path()
            )
            os.remove(tmp)
        return models

    def generate_notes_pipeline(self, text: str) -> List[model_schemas.Note]:
        """
        High-level entry for generating structured notes from text or image data URI.
        Similar to flashcards pipeline but triggers note-specific flows.
        """
        from utils.model_pipeline import ModelPipeline
        pipeline = ModelPipeline(media_dir=self.get_media_path())

        if text.startswith("data:image"):
            chunks = [{"title": "Uploaded Image", "content": text}]
            models = pipeline._process_chunks(
                chunks=chunks,
                card_type="note",
                url_name="",
                file_name="uploaded_image.png",
                content_type="image",
                media_path=self.get_media_path()
            )
        else:
            tmp = os.path.join(self.get_media_path(), "temp_note.txt")
            with open(tmp, 'w', encoding='utf-8') as f:
                f.write(text)
            models = pipeline.generate_notes(
                file_path=tmp,
                media_path=self.get_media_path()
            )
            os.remove(tmp)
        return models

    def generate_graphs_pipeline(self, text: str, graph_type: str) -> List[model_schemas.NoteItem]:
        """
        Generate mind maps or knowledge graphs from text or image data URI.
        Uses a single holistic content flow without chunk merging.
        Ensures graphviz formatting in the output.
        """
        from utils.model_helper import ModelHelper
        from utils.prompts import MIND_MAP_GENERATION_PROMPT

        # Determine whether we're handling text or image content
        prompt = MIND_MAP_GENERATION_PROMPT
        helper = ModelHelper()

        if text.startswith("data:image"):  # If the input is an image
            # Handle image input
            chunks = [{"title": "Uploaded Image", "content": text}]
            response = helper.get_flashcards(
                conversation=[],
                system_message=prompt,
                user_text=text,  # For image, we directly send the image data
                run_as_image=True,  # Indicating that this is an image
                response_format=model_schemas.NoteItem
            )
        else:
            # Handle text input
            response = helper.get_flashcards(
                conversation=[],
                system_message=prompt,
                user_text=text,  # For text, we send the plain text
                run_as_image=False,  # Indicating that this is text
                response_format=model_schemas.NoteItem
            )

        # Wrap raw graph content in code fences if needed
        note = model_schemas.NoteItem.model_validate_json(response)
        if not re.search(r"```(?:graphviz|dot)\s", note.content, re.IGNORECASE):
            note.content = f"```graphviz\n{note.content.strip()}\n```"

        return [note]

    # Dispatch table mapping abstract content types to read functions
    READ_DISPATCH = {
        'text': _get_plain_text,
        'image': lambda path: FileHelper._get_img_uri(Image.open(path)),
        'pdf': lambda path: FileHelper._get_img_uri(FileHelper._get_image(path)[0])
            if FileHelper._get_image(path) else "",
    }
    