# model_helper.py

import sys
import tiktoken
from enum import Enum
from openai import OpenAI
from rich.console import Console
from utils import model_schemas, prompts
from utils.logger import logger

class ModelHelper:
    """
    A helper class for interacting with the OpenAI API
    to rewrite text, generate flashcards or notes, etc.
    """
    def __init__(self, model_text="gpt-4o-mini", model_image="gpt-4o-2024-11-20"):
        self.model_text = model_text
        self.model_image = model_image
        self.console = Console()
        self.client = OpenAI()

    class PromptType(Enum):
        CONCEPTS = "concepts"
        NOTES = "notes"
        REWRITE = "rewrite_text"
        VALIDATE_REWRITE = "validate_rewrite"

    PROMPT_TEMPLATES = {
        PromptType.CONCEPTS: prompts.CONCEPT_FLASHCARD_PROMPT,
        PromptType.NOTES: prompts.NOTE_GENERATION_PROMPT,
        PromptType.REWRITE: prompts.REWRITE_PROMPT,
        PromptType.VALIDATE_REWRITE: prompts.VALIDATE_REWRITE_PROMPT,
    }

    def get_num_tokens(self, string: str, encoding_name: str = None) -> int:
        encoding = tiktoken.get_encoding(encoding_name) if encoding_name else tiktoken.encoding_for_model(self.model_text)
        return len(encoding.encode(string))

    def get_system_message(self, prompt_type: PromptType, **kwargs) -> str:
        template = self.PROMPT_TEMPLATES.get(prompt_type, "")
        return template.format(**kwargs)
    
    def get_rewrite(self, text: str, *, content_type: str = "text") -> str:
        """Rewrite *text* into clean Markdown, validating the result."""
        system = self.get_system_message(self.PromptType.REWRITE)
        msgs = [{"role": "system", "content": system},
                {"role": "user",   "content": text}]

        original_tokens = self.get_num_tokens(text)
        min_tokens = max(original_tokens - 50, 0)

        rewritten, rewritten_tokens = "", 0
        for _ in range(2):
            if rewritten_tokens <= min_tokens:
                cmp = self.get_completion(msgs,
                                        response_format=model_schemas.TEXT_FORMAT,
                                        run_as_image=False)
                rewritten = cmp.choices[0].message.content
                rewritten_tokens = self.get_num_tokens(rewritten)
            else:
                break

        if rewritten_tokens <= min_tokens and \
        not self._is_valid_rewrite(text, rewritten):
            raise ValueError("Rewrite validation failed – aborting.")
        return rewritten

    def get_flashcards(self, conversation, system_message, user_text, run_as_image, response_format):
        """
        Generates flashcards from user input. Depending on run_as_image, the method prepares 
        different message payloads. The OpenAI API is called via get_completion.
        """
        if not conversation:
            conversation.append({"role": "system", "content": system_message})

        messages = []
        if run_as_image:
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": user_text}}]}
            ]
            conversation.append({"role": "user", "content": "Sent an image for flashcard generation."})
        else:
            conversation.append({"role": "user", "content": user_text})
            messages = conversation

        completion = self.get_completion(
            messages=messages if run_as_image else conversation,
            response_format=response_format,
            run_as_image=run_as_image
        )
        response = completion.choices[0].message.content
        conversation.append({"role": "assistant", "content": response})

        for item in conversation:
            for k, v in item.items():
                if k == "role":
                    self.console.log(f"\n[bold red]{k}:[/bold red]", v)
                else:
                    self.console.log(f"[bold red]{k}:[/bold red]\n", v)

        if len(conversation) > 4:
            del conversation[1:3]

        self.console.log("\n[bold red]Token Usage:[/bold red]", completion.usage)
        return response
     
    def _is_valid_rewrite(self, original: str, rewritten: str) -> bool:
        system = self.get_system_message(self.PromptType.VALIDATE_REWRITE,
                                        user_message=original)
        msgs = [
            {"role": "system", "content": system},
            {"role": "user", "content": rewritten}
        ]
        cmp = self.get_completion(msgs,
                                response_format=model_schemas.RewriteValidator,
                                run_as_image=False)
        verdict = model_schemas.RewriteValidator.model_validate_json(
            cmp.choices[0].message.content)
        return bool(verdict.is_valid)

    def get_completion(self, messages: list, response_format, run_as_image: bool = False):
        """
        Makes the API call to OpenAI using the provided messages and parameters.
        It determines which model to use based on whether the input is an image or text.
        """
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

        self.console.log(f"[bold yellow]`{model}` response:[/bold yellow]", completion.choices[0].message.content)
        return completion
