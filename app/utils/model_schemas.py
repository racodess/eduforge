# model_schemas.py

from typing import List
from pydantic import BaseModel, Field, ConfigDict

TEXT_FORMAT = {"type": "text"}

class FlashcardItem(BaseModel):
    front: str = Field(
        description="The question in markdown format. Use (`) for inline code."
    )
    back: str = Field(
        description="The answer in markdown format. Use (`) for inline code, and language-detected code-block fencing for code snippets."
    )
    model_config = ConfigDict(extra='forbid')

class Flashcard(BaseModel):
    flashcards: List[FlashcardItem] = Field(
        description="A list of markdown-formatted flashcards derived from concept items."
    )
    header: str = Field(
        description=(
            "Describe the flashcards list using an accurate and succinct title in markdown format that follows "
            "the structure `BroadTopic: SpecificConcept` (e.g., 'Java: Identifiers')."
        )
    )
    model_config = ConfigDict(extra='forbid')

# New models for notes generation

class NoteItem(BaseModel):
    title: str = Field(
        description="Title of the note in markdown format."
    )
    content: str = Field(
        description="Content of the note in markdown format."
    )
    model_config = ConfigDict(extra='forbid')

class Note(BaseModel):
    notes: List[NoteItem] = Field(
        description="A list of markdown-formatted notes generated from source material."
    )
    header: str = Field(
        description="Provide a succinct title for the notes section in markdown format."
    )
    model_config = ConfigDict(extra='forbid')
