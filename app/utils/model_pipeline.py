# model_pipeline.py

"""
Defines the ModelPipeline class for orchestrating OpenAI-driven content processing.
Supports flashcard and note generation flows, including chunk merging,
concept and note prompt handling, and error logging.
"""

import os
from rich.console import Console
from utils import model_schemas
from utils.logger import logger
from utils.file_helper import FileHelper
from utils.model_helper import ModelHelper

class ModelPipeline:
    """
    Handles end-to-end generation flows against OpenAI models.
    Provides methods for flashcards, notes, and underlying chunk processing.
    """
    def __init__(self, media_dir: str):
        """
        Initialize pipeline with a media directory for storing assets.
        """
        self.media_dir = media_dir

        # Rich console for formatted output
        self.console = Console()

        # Shared conversation history (system + user messages)
        self.conversation: list = []

    def generate_flashcards(
        self,
        file_path=None,
        url=None,
        metadata=None,
        flashcard_type='general',
        media_path=None,
    ):
        """
        Generate flashcards from a URL or file input.

        Parameters:
            file_path: Local file to process.
            url: Remote URL to scrape and process.
            flashcard_type: 'general' or 'note' to select prompt flow.
            media_path: Optional path to store media outputs.

        Returns:
            List of validated Pydantic models (Flashcard or Note).
        """
        results = []

        # Determine content source type
        content_type = "url" if url else "text"
        url_name = url or ""
        source_name = os.path.basename(file_path) if file_path else ""

        # Process URL flow
        if url:
            # Placeholder for scraped data; must be populated
            webpage_data = None
            if not webpage_data:
                logger.warning(
                    "No data returned from URL: %s. Skipping flashcard generation.", url
                )
                return results
            
            # Extract sections for processing
            chunks = webpage_data.get("sections", [])

            # Delegate to chunk processor
            results = self._process_chunks(
                chunks=chunks,
                card_type=flashcard_type,
                url_name=url_name,
                file_name=source_name,
                content_type=content_type,
                media_path=media_path
            )
            return results

        # Process file flow
        elif file_path:
            # Determine file content type (text, pdf, image, etc.)
            detected_type = FileHelper.get_content_type(
                file_path=file_path,
                url=None
            )
            if detected_type == 'unsupported':
                logger.warning(
                    "Unsupported file type: %s. Skipping flashcard generation.", file_path
                )
                return results
            content_type = detected_type.lower()

            try:
                # Read file data as string or bytes
                file_content = FileHelper().get_data(
                    file_path,
                    content_type
                )
            except FileHelper.UnsupportedFileTypeError as e:
                logger.warning("Unsupported file type error: %s", e)
                return results
            except Exception as e:
                logger.error("Error reading file %s: %s", file_path, e)
                return results

            # Wrap file into a single chunk
            chunk = [{
                "title": source_name,
                "content": file_content
            }]

            # Delegate to chunk processor
            results = self._process_chunks(
                chunks=chunk,
                card_type=flashcard_type,
                url_name=url_name,
                file_name=source_name,
                content_type=content_type,
                media_path=media_path,
            )
            return results

        # Missing both inputs: log error
        else:
            logger.error(
                "Neither file_path nor url provided to generate_flashcards."
            )
            return results
        
    def generate_notes(
        self,
        *,
        file_path=None,
        url=None,
        media_path=None
    ):
        """
        Shortcut to generate notes by reusing flashcard logic with a 'note' type.
        """
        return self.generate_flashcards(
            file_path=file_path,
            url=url,
            media_path=media_path,
            flashcard_type="note"
        )

    def _run_generic_flow(
        self,
        *,
        flow_name: str,
        prompt_type: ModelHelper.PromptType,
        content: str,
        url_name: str,
        file_name: str,
        content_type: str,
        model_class,
        media_path=None,
    ):
        """
        Core runner for concept or note flows, handling prompts and parsing.
        """
        print()

        # Visual separator for flow start
        self.console.rule(f"Running {flow_name}")

        helper = ModelHelper()

        # Build system message based on flow type
        system_message = helper.get_system_message(prompt_type)

        # Request content generation from OpenAI
        response = helper.get_flashcards(
            conversation=self.conversation,
            system_message=system_message,
            user_text=content,
            run_as_image=(content_type not in ["text", "url"]),
            response_format=model_class
        )

        # Validate and parse into Pydantic model
        card_model = model_class.model_validate_json(response)

        # Print results to console
        output = (
            card_model.flashcards 
            if hasattr(card_model, "flashcards") 
            else card_model.notes
        )
        self.console.print(output)
        return card_model

    def _run_concept_flow(
        self,
        content,
        url_name,
        file_name,
        content_type,
        media_path,
    ):
        """
        Run the concept (general flashcards) flow.
        """
        return self._run_generic_flow(
            flow_name="Concepts Flow",
            prompt_type=ModelHelper.PromptType.CONCEPTS,
            content=content,
            url_name=url_name,
            file_name=file_name,
            content_type=content_type,
            model_class=model_schemas.Flashcard,
            media_path=media_path,
        )

    def _run_note_flow(
        self,
        content,
        url_name,
        file_name,
        content_type,
        media_path,
    ):
        """
        Run the note generation flow.
        """
        return self._run_generic_flow(
            flow_name="Notes Flow",
            prompt_type=ModelHelper.PromptType.NOTES,
            content=content,
            url_name=url_name,
            file_name=file_name,
            content_type=content_type,
            model_class=model_schemas.Note,
            media_path=media_path,
        )

    def _merge_chunks(self, chunks, file_name):
        """
        Merge small text chunks to meet token thresholds before prompting.

        Accumulates chunks under min_chunk_tokens until max_chunk_tokens,
        then flushes into a combined section.
        """
        merged_chunks: list = []
        content_buffer: list = []
        running_token_count = 0

        def flush_temp_buffer():
            # Combine buffered chunks into one merged chunk
            nonlocal content_buffer, running_token_count
            merged_chunks.append({"title": "Merged chunks", "content": ""})
            for ch in content_buffer:
                merged_chunks[-1]["content"] += (
                    f"{ch['title']}:\n{ch['content']}\n------\n"
                )
            content_buffer.clear()
            running_token_count = 0

        min_chunk_tokens = 300
        max_chunk_tokens = 1000

        helper = ModelHelper()

        # Iterate over all input chunks
        for idx, chunk in enumerate(chunks, start=1):
            heading_title = chunk.get("title", file_name)
            chunk_text = chunk["content"]
            chunk_tokens = helper.get_num_tokens(chunk_text)
            logger.info(
                f"[Chunk] '{heading_title}' has {chunk_tokens} tokens."
            )

            # Decide whether to buffer or flush based on token counts
            if chunk_tokens < min_chunk_tokens:
                if running_token_count + chunk_tokens <= max_chunk_tokens:
                    logger.info(
                        f"Merging chunk ('{heading_title}') into buffer"
                    )
                    content_buffer.append({"title": heading_title, "content": chunk_text})
                    running_token_count += chunk_tokens
                else:
                    logger.info(
                        f"Flushing buffer before adding chunk {idx}"
                    )
                    flush_temp_buffer()
                    content_buffer.append({"title": heading_title, "content": chunk_text})
                    running_token_count = chunk_tokens
            else:
                # Large chunk: flush any buffer first, then add standalone
                if running_token_count > 0:
                    logger.info(
                        "Flushing buffer before processing large chunk"
                    )
                    flush_temp_buffer()
                logger.info(
                    f"Processing chunk ('{heading_title}') standalone."
                )
                merged_chunks.append({"title": heading_title, "content": chunk_text})

        # Flush any remainder in buffer
        if running_token_count > 0:
            logger.info(
                f"Flushing final buffer (~{running_token_count} tokens)."
            )
            flush_temp_buffer()

        return merged_chunks

    def _process_chunks(
        self,
        chunks,
        card_type,
        url_name,
        file_name,
        content_type,
        media_path=None,
    ):
        """
        Process each text/image chunk through the appropriate flow.

        Merges small chunks for text/url, prints each chunk,
        then routes to concept or note flows.
        """
        print()
        self.console.rule("[bold red]Extracted and Filtered Data[/bold red]")

        # Merge small chunks for text or URL inputs
        if content_type in ["text", "url"]:
            chunks = self._merge_chunks(chunks=chunks, file_name=file_name)

        results = []
        
        # Iterate and process each chunk
        for idx, chunk in enumerate(chunks, start=1):
            heading_title = chunk.get("title", file_name) or "(untitled section)"
            chunk_text = chunk["content"]

            print()
            self.console.rule(f"[bold red]Chunk {idx}:[/bold red] {heading_title}")

            # Display chunk content or image message
            if content_type in ["text", "url"]:
                self.console.print(chunk_text)
            elif content_type == "image":
                self.console.print(
                    "Processing image for flashcard generation"
                )
            else:
                self.console.print(
                    "Unsupported content type for flashcard generation."
                )

            # Select flow based on card_type
            if card_type == 'general':
                card_model = self._run_concept_flow(
                    content=chunk_text,
                    url_name=url_name,
                    file_name=file_name,
                    content_type=content_type,
                    media_path=media_path,
                )
            else:
                card_model = self._run_note_flow(
                    content=chunk_text,
                    url_name=url_name,
                    file_name=file_name,
                    content_type=content_type,
                    media_path=media_path,
                )
            results.append(card_model)
        return results
