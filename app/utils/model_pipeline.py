# model_pipeline.py

import os
from rich.console import Console
from utils import model_schemas
from utils.logger import logger
from utils.file_helper import FileHelper
from utils.model_helper import ModelHelper

class ModelPipeline:
    """
    Handles the generation flow for OpenAI models.
    """

    def __init__(self, media_dir: str):
        self.media_dir = media_dir
        self.console = Console()
        # Global conversation list for context if needed.
        self.conversation = []

    def generate_flashcards(
        self,
        file_path=None,
        url=None,
        metadata=None,
        flashcard_type='general',
        media_path=None,
    ):
        """
        Orchestrates the entire process of creating flashcards, either from a local file or a URL.
        Returns a list of generated flashcard models.
        """
        results = []
        # Decide if the content is from a URL or a local file.
        content_type = "url" if url else "text"
        url_name = url if url else ""
        source_name = os.path.basename(file_path) if file_path else ""

        if url:
            # For URL-based input, the webpage scraping is not currently implemented.
            webpage_data = None
            if not webpage_data:
                logger.warning("No data returned from URL: %s. Skipping flashcard generation.", url)
                return results
            chunks = webpage_data.get("sections", [])
            results = self._process_chunks(
                chunks=chunks,
                card_type=flashcard_type,
                url_name=url_name,
                file_name=source_name,
                content_type=content_type,
                media_path=media_path
            )
            return results
        elif file_path:
            # For files, detect the type and attempt to read the data.
            detected_type = FileHelper.get_content_type(file_path=file_path, url=None)
            if detected_type == 'unsupported':
                logger.warning("Unsupported file type: %s. Skipping flashcard generation.", file_path)
                return results
            content_type = detected_type.lower()

            try:
                file_content = FileHelper().get_data(file_path, content_type)
            except FileHelper.UnsupportedFileTypeError as e:
                logger.warning("Unsupported file type error: %s", e)
                return results
            except Exception as e:
                logger.error("Error reading file %s: %s", file_path, e)
                return results

            # Wrap the file content into a single chunk using the filename as title.
            chunk = [
                {"title": source_name, "content": file_content}
            ]
            results = self._process_chunks(
                chunks=chunk,
                card_type=flashcard_type,
                url_name=url_name,
                file_name=source_name,
                content_type=content_type,
                media_path=media_path,
            )
            return results
        else:
            logger.error("Neither file_path nor url provided to generate_flashcards.")
            return results

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
        Encapsulates the standard steps to generate flashcards for conceptual content.
        """
        print()
        self.console.rule(f"Running {flow_name}")

        # Instantiate the ModelHelper to access instance methods.
        helper = ModelHelper()

        # Prepare the system message for the LLM based on prompt type.
        system_message = helper.get_system_message(prompt_type)
        # Generate flashcards using the LLM.
        response = helper.get_flashcards(
            conversation=self.conversation,
            system_message=system_message,
            user_text=content,
            run_as_image=(content_type not in ["text", "url"]),
            response_format=model_class
        )

        # Validate JSON response with Pydantic.
        card_model = model_class.model_validate_json(response)

        # NOTE: We no longer assign the extra fields (url_name, file_name, content_type)
        # to the model instance because the Pydantic model is defined with only `flashcards` and `header`.
        # If you need to use this metadata, handle it separately from the validated model.

        # Display generated flashcards.
        self.console.print(card_model.flashcards)

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
        Initiates the "Concepts" flashcard generation flow.
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

    def _merge_chunks(self, chunks, file_name):
        """
        Merges small text chunks while ensuring none are lost.
        """
        merged_chunks = []
        content_buffer = []
        running_token_count = 0

        def flush_temp_buffer():
            nonlocal content_buffer, running_token_count
            merged_chunks.append({"title": "Merged chunks", "content": ""})
            for chunk in content_buffer:
                merged_chunks[-1]['content'] += f"{chunk['title']}:\n{chunk['content']}\n------\n"
            content_buffer.clear()
            running_token_count = 0

        min_chunk_tokens = 300
        max_chunk_tokens = 1000

        # Instantiate ModelHelper so that we can call get_num_tokens as an instance method.
        from utils.model_helper import ModelHelper  # Ensure proper import if not already imported
        model_helper = ModelHelper()

        for idx, chunk in enumerate(chunks, start=1):
            heading_title = chunk.get("title", file_name)
            chunk_text = chunk["content"]
            # Use the instance method call
            chunk_tokens = model_helper.get_num_tokens(chunk_text)
            logger.info(f"[Chunk] '{heading_title}' has {chunk_tokens} tokens.")

            if chunk_tokens < min_chunk_tokens:
                if running_token_count + chunk_tokens <= max_chunk_tokens:
                    logger.info(
                        f"Merging chunk ('{heading_title}') into buffer (current total={running_token_count} tokens)."
                    )
                    content_buffer.append({"title": heading_title, "content": chunk_text})
                    running_token_count += chunk_tokens
                else:
                    logger.info(
                        f"Buffer ~{running_token_count} tokens; flushing before adding chunk {idx} ('{heading_title}')."
                    )
                    flush_temp_buffer()
                    content_buffer.append({"title": heading_title, "content": chunk_text})
                    running_token_count = chunk_tokens
            else:
                if running_token_count > 0:
                    logger.info(
                        f"Flushing buffer (~{running_token_count} tokens) before adding larger chunk {idx} ('{heading_title}')."
                    )
                    flush_temp_buffer()
                logger.info(
                    f"Processing chunk ('{heading_title}') as a standalone chunk."
                )
                merged_chunks.append({"title": heading_title, "content": chunk_text})

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
        Iterates over chunked content to generate flashcards for each section.
        Returns a list of generated flashcard models.
        """
        print()
        self.console.rule("[bold red]Extracted and Filtered Data[/bold red]")

        # Merge chunks if working with text or URL content.
        if content_type in ["text", "url"]:
            chunks = self._merge_chunks(chunks=chunks, file_name=file_name)

        results = []
        for idx, chunk in enumerate(chunks, start=1):
            heading_title = chunk.get("title", file_name)
            chunk_text = chunk["content"]

            print()
            self.console.rule(f"[bold red]Chunk {idx}:[/bold red] {heading_title}")

            if content_type in ["text", "url"]:
                self.console.print(chunk_text)
            else:
                self.console.print("Image placeholder text")

            card_model = self._run_concept_flow(
                content=chunk_text,
                url_name=url_name,
                file_name=file_name,
                content_type=content_type,
                media_path=media_path,
            )
            results.append(card_model)
        return results
