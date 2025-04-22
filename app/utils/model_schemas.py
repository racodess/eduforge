# model_schemas.py

"""
Pydantic models defining data schemas for flashcards, notes, and rewrite validation.
Ensures structured, type-checked inputs and outputs for LLM interactions.
"""

from typing import List
from pydantic import BaseModel, Field, ConfigDict

# Constant defining a simple text response format for completions
TEXT_FORMAT = {"type": "text"}

class FlashcardItem(BaseModel):
    """
    Represents a single flashcard with front/back content and optional source data.
    - front: question text in markdown
    - back: answer text in markdown
    - data: original excerpt used to generate this card
    """
    front: str = Field(
        description="The question in markdown format. Use (`) for inline code."
    )
    back: str = Field(
        description=(
            "The answer in markdown format. Use (`) for inline code, "
            "and fenced code blocks for snippets."
        )
    )
    data: str = Field(
        default=None,
        description="Exact markdown excerpt of the source material used to generate this flashcard."
    )
    model_config = ConfigDict(extra='forbid') # Forbid any unexpected fields to enforce strict schema

class Flashcard(BaseModel):
    """
    Wrapper model containing a list of FlashcardItem objects and a header title.
    - header: markdown title summarizing the flashcard set
    """
    flashcards: List[FlashcardItem] = Field(
        description="A list of markdown-formatted flashcards derived from concepts."
    )
    header: str = Field(
        description=(
            "A succinct markdown title in the format 'BroadTopic: SpecificConcept' "
            "describing the flashcards set (e.g., 'Java: Identifiers')."
        )
    )
    model_config = ConfigDict(extra='forbid')

class NoteItem(BaseModel):
    """
    Represents a single note tab with title, content, and optional source data.
    - title: note heading in markdown
    - content: note body in markdown
    - data: original excerpt used to generate this note
    """
    title: str = Field(
        description="Title of the note in markdown format."
    )
    content: str = Field(
        description="Content of the note in markdown format."
    )
    data: str = Field(
        default=None,
        description="Exact markdown excerpt of the source material used to generate this note."
    )
    model_config = ConfigDict(extra='forbid')

class Note(BaseModel):
    """
    Wrapper model containing a list of NoteItem objects and a header title.
    - header: markdown title summarizing the notes section
    """
    notes: List[NoteItem] = Field(
        description="A list of markdown-formatted notes generated from source material."
    )
    header: str = Field(
        description="A succinct markdown header for the notes section in markdown format."
    )
    model_config = ConfigDict(extra='forbid')

class RewriteValidator(BaseModel):
    """
    Schema for validating rewritten text.
    - is_valid: boolean flag indicating if rewrite is acceptable
    """
    is_valid: bool = Field(
        description="True if the response is a valid rewrite of the original source material."
    )
    model_config = ConfigDict(extra='forbid')
