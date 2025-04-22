# model_helper.py

"""
Utility class for interacting with OpenAI API tailored to EduForge flows.
Supports text token counting, prompt templating, content rewriting, and flashcard/note generation.
"""

import sys
import tiktoken
from enum import Enum
from openai import OpenAI
from rich.console import Console
from utils import model_schemas, prompts
from utils.logger import logger

class ModelHelper:
    """
    A helper for constructing prompts, counting tokens, and handling OpenAI completions.
    Manages separate models for text and image-based inputs.
    """
    def __init__(self, model_text="gpt-4o-mini", model_image="gpt-4o-2024-11-20"):
        """
        Initialize with model identifiers and a Rich console for logging.
        """
        self.model_text = model_text # Model for text-based prompts
        self.model_image = model_image # Model variant optimized for image data
        self.console = Console() # For rich logging in terminal
        self.client = OpenAI() # OpenAI API client instance

    class PromptType(Enum):
        """
        Enumerates the types of prompts supported by ModelHelper.
        """
        CONCEPTS = "concepts" # Generate conceptual flashcards
        NOTES = "notes" # Generate structured notes
        REWRITE = "rewrite_text" # Rewrite text in Markdown
        VALIDATE_REWRITE = "validate_rewrite" # Validate rewritten text

    # Map prompt types to their template strings
    PROMPT_TEMPLATES = {
        PromptType.CONCEPTS: prompts.CONCEPT_FLASHCARD_PROMPT,
        PromptType.NOTES: prompts.NOTE_GENERATION_PROMPT,
        PromptType.REWRITE: prompts.REWRITE_PROMPT,
        PromptType.VALIDATE_REWRITE: prompts.VALIDATE_REWRITE_PROMPT,
    }

    def get_num_tokens(self, string: str, encoding_name: str = None) -> int:
        """
        Estimate token count for a given string using tiktoken.
        If encoding_name is provided, uses that; otherwise infers from text model.
        """
        if encoding_name:
            encoding = tiktoken.get_encoding(encoding_name)
        else:
            encoding = tiktoken.encoding_for_model(self.model_text)
        return len(encoding.encode(string))

    def get_system_message(self, prompt_type: PromptType, **kwargs) -> str:
        """
        Fill and return the system message template corresponding to a prompt type.
        Additional keyword args are formatted into the template.
        """
        template = self.PROMPT_TEMPLATES.get(prompt_type, "")
        return template.format(**kwargs)
    
    def get_rewrite(self, text: str, *, content_type: str = "text") -> str:
        """
        Rewrite input text into clean Markdown and validate it.
        Retries up to twice if token count is insufficient.
        """
        # Build system and user messages for the rewrite flow
        system = self.get_system_message(self.PromptType.REWRITE)
        msgs = [
            {"role": "system", "content": system},
            {"role": "user",   "content": text}
        ]

        # Determine minimum acceptable token count
        original_tokens = self.get_num_tokens(text)
        min_tokens = max(original_tokens - 50, 0)

        rewritten, rewritten_tokens = "", 0
        for _ in range(2):
            # If rewritten is too short, request another completion
            if rewritten_tokens <= min_tokens:
                cmp = self.get_completion(
                    messages=msgs,
                    response_format=model_schemas.TEXT_FORMAT,
                    run_as_image=False
                )
                rewritten = cmp.choices[0].message.content
                rewritten_tokens = self.get_num_tokens(rewritten)
            else:
                break

        # Validate the rewrite if tokens still low
        if rewritten_tokens <= min_tokens and not self._is_valid_rewrite(text, rewritten):
            raise ValueError("Rewrite validation failed – aborting.")
        return rewritten

    def get_flashcards(self, conversation, system_message, user_text, run_as_image, response_format):
        """
        Generate flashcards or notes based on user input.
        Builds message list differently if processing images.
        Logs conversation and token usage.
        Returns the assistant's response content.
        """
        # Initialize conversation with system message if empty
        if not conversation:
            conversation.append({"role": "system", "content": system_message})

        # Prepare messages payload
        if run_as_image:
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": user_text}}]}
            ]

            # Log a placeholder in conversation history
            conversation.append({"role": "user", "content": "Sent an image for flashcard generation."})
        else:
            # Append user text to conversation history
            conversation.append({"role": "user", "content": user_text})
            messages = conversation

        # Call completion API
        completion = self.get_completion(
            messages=messages,
            response_format=response_format,
            run_as_image=run_as_image
        )
        response = completion.choices[0].message.content
        
        # Append assistant reply to history
        conversation.append({"role": "assistant", "content": response})

        # Log roles and contents for inspection
        for item in conversation:
            role = item.get("role")
            content = item.get("content")
            self.console.log(f"[bold red]{role}:[/bold red] {content}")

        # Truncate history if it grows too long
        if len(conversation) > 4:
            del conversation[1:3]

        # Log token usage details
        self.console.log(f"[bold red]Token Usage:[/bold red] {completion.usage}")
        return response

    def _is_valid_rewrite(self, original: str, rewritten: str) -> bool:
        """
        Validate a rewritten text by asking the model to check correctness.
        Returns True if the validator model affirms validity.
        """
        system = self.get_system_message(
            self.PromptType.VALIDATE_REWRITE,
            user_message=original
        )
        msgs = [
            {"role": "system", "content": system},
            {"role": "user", "content": rewritten}
        ]
        cmp = self.get_completion(
            messages=msgs,
            response_format=model_schemas.RewriteValidator,
            run_as_image=False
        )
        verdict = model_schemas.RewriteValidator.model_validate_json(
            cmp.choices[0].message.content
        )
        return bool(verdict.is_valid)

    def get_completion(self, messages: list, response_format, run_as_image: bool = False):
        """
        Execute the OpenAI API call with appropriate model selection.
        Catches and logs errors, then rethrows.
        Returns the completion object.
        """
        # Choose model based on input type
        model = self.model_image if run_as_image else self.model_text
        try:
            completion = self.client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=response_format,
                max_completion_tokens=16384,
                temperature=0,
                top_p=0.1
            )
        except Exception as e:
            logger.error("Error calling LLM: %s", e, exc_info=True)
            raise

        # Log the raw model response
        self.console.log(
            f"[bold yellow]`{model}` response:[/bold yellow] {completion.choices[0].message.content}"
        )
        return completion
