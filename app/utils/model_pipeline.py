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
        self.conversation = []

    def generate_flashcards(
        self,
        file_path=None,
        url=None,
        metadata=None,
        flashcard_type='general',
        media_path=None,
    ):
        results = []
        content_type = "url" if url else "text"
        url_name = url if url else ""
        source_name = os.path.basename(file_path) if file_path else ""

        if url:
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
        print()
        self.console.rule(f"Running {flow_name}")

        helper = ModelHelper()
        system_message = helper.get_system_message(prompt_type)
        response = helper.get_flashcards(
            conversation=self.conversation,
            system_message=system_message,
            user_text=content,
            run_as_image=(content_type not in ["text", "url"]),
            response_format=model_class
        )
        card_model = model_class.model_validate_json(response)
        self.console.print(card_model.flashcards if hasattr(card_model, "flashcards") else card_model.notes)
        return card_model

    def _run_concept_flow(
        self,
        content,
        url_name,
        file_name,
        content_type,
        media_path,
    ):
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

        from utils.model_helper import ModelHelper
        model_helper = ModelHelper()

        for idx, chunk in enumerate(chunks, start=1):
            heading_title = chunk.get("title", file_name)
            chunk_text = chunk["content"]
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
        print()
        self.console.rule("[bold red]Extracted and Filtered Data[/bold red]")

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
            elif content_type == "image":
                self.console.print("Processing image for flashcard generation (base64 image URI received).")
            else:
                self.console.print("Unsupported content type for flashcard generation.")

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
