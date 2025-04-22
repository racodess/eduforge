# sidebar.py

"""
Defines the sidebar UI components for generation tools and a chatbot.
Provides functions to render study-material generation options, process user inputs,
and integrate with file handling and OpenAI services.
"""

import os

import streamlit as st
from typing import List
from openai import OpenAI

from utils.flashcards_db import get_decks
from utils.notes_db import get_notebooks
from utils.file_helper import FileHelper


def render_generation_sidebar() -> None:
    """
    Render the study-material generation interface in the Streamlit sidebar.
    Includes selectors for flashcards, notebooks, and mind maps,
    file upload or text/URL input, and triggers generation pipelines.
    """
    # Sidebar context for generation tools
    with st.sidebar:
        st.markdown("## Generate Study Material")

        # Allow user to pick one or more types of study materials
        study_types = st.multiselect(
            "Select study material type(s)",
            options=[
                "Flashcards",
                "Notebooks", # Traditional markdown notes
                "Mind Maps",
            ],
            key="gen_study_types",
        )

        # If flashcards selected, allow deck selection
        if "Flashcards" in study_types:
            decks = get_decks()
            if not decks:
                st.error("No decks available. Please create a deck first.")
                return
            
            # Map deck names to their IDs for multi-select
            deck_opts = {dname: did for did, dname in decks}
            selected_names = st.multiselect(
                "Target deck(s)",
                options=list(deck_opts.keys()),
                default=list(deck_opts.keys())[:1],
                key="gen_deck_select",
            )

            # Convert selected deck names back to IDs in session state
            st.session_state.gen_target_deck_ids = [
                deck_opts[name] for name in selected_names
            ]
        else:
            # Clean up session state if flashcards not selected
            st.session_state.pop("gen_target_deck_ids", None)

        # Determine if notebooks or mind maps require notebook targets
        needs_notebooks = any(
            t in study_types for t in ["Notebooks", "Mind Maps"]
        )
        if needs_notebooks:
            notebooks = get_notebooks()
            if not notebooks:
                st.error("No notebooks available. Please create one first.")
                return
            
            # Map notebook names to their IDs for multi-select
            nb_opts = {nname: nid for nid, nname in notebooks}
            selected_nb_names = st.multiselect(
                "Target notebook(s)",
                options=list(nb_opts.keys()),
                default=list(nb_opts.keys())[:1],
                key="gen_nb_select",
            )

            # Convert selected notebook names back to IDs in session state
            st.session_state.gen_target_nb_ids = [
                nb_opts[name] for name in selected_nb_names
            ]
        else:
            # Clean up session state if no notebook targets needed
            st.session_state.pop("gen_target_nb_ids", None)

        # Initialize file helper for processing inputs
        file_helper = FileHelper()

        # File upload widget for text, PDF, or images
        uploaded_file = st.file_uploader(
            label="Upload a .txt, .pdf, or image file",
            type=["txt", "pdf", "png", "jpg", "jpeg", "gif"],
            key="gen_file_uploader",
        )

        page_range = None

        # If uploaded file is a PDF, show page-range selectors
        if uploaded_file is not None and uploaded_file.name.lower().endswith(".pdf"):
            try:
                from PyPDF2 import PdfReader
                uploaded_file.seek(0)
                pdf_reader = PdfReader(uploaded_file)
                total_pages = len(pdf_reader.pages)
                uploaded_file.seek(0)
            except Exception:
                # Default to zero pages if PDF parsing fails
                total_pages = 0

            # Two columns for start and end page inputs
            sc1, sc2 = st.columns(2)
            start_page = sc1.number_input(
                "Start Page",
                min_value=1,
                max_value=total_pages if total_pages else 1,
                value=1,
                step=1,
            )
            end_page = sc2.number_input(
                "End Page",
                min_value=1,
                max_value=total_pages if total_pages else 1,
                value=total_pages if total_pages else 1,
                step=1,
            )
            page_range = (start_page, end_page)

        # Text area for pasting plain content
        text_input = st.text_area(
            "Or paste text content here", "", key="gen_text_input"
        )

        # URL input for scraping remote content
        url_input = st.text_input(
            "Or provide a URL", "", key="gen_url_input"
        )

        # Generate button to trigger content processing
        if st.button("Generate", key="gen_button", use_container_width=True):
            final_text = ""

            # Prioritize uploaded file processing
            if uploaded_file is not None:
                if uploaded_file.name.lower().endswith('.pdf') and page_range:
                    final_text = file_helper.process_file(
                        uploaded_file,
                        start_page=page_range[0],
                        end_page=page_range[1],
                    )
                else:
                    final_text = file_helper.process_file(uploaded_file)
            # Fall back to pasted text
            elif text_input.strip():
                final_text = file_helper.process_text(text_input.strip())
            # Fall back to URL input
            elif url_input.strip():
                final_text = file_helper.process_url(url_input.strip())

            # Warn if no content was obtained
            if not final_text:
                st.warning("No valid content provided!")
                return

            # Run flashcard generation pipeline if selected
            if "Flashcards" in study_types:
                flashcard_models = file_helper.generate_flashcards_pipeline(
                    final_text
                )
                # Collect all generated flashcards into session
                st.session_state.generated_cards = [
                    fc
                    for m in flashcard_models
                    if hasattr(m, "flashcards")
                    for fc in m.flashcards
                ]
            else:
                # Remove any leftover flashcard state
                st.session_state.pop("generated_cards", None)

            # Run notes generation pipeline if selected
            if "Notebooks" in study_types:
                note_models = file_helper.generate_notes_pipeline(final_text)
                st.session_state.generated_notes = [
                    nt for m in note_models if hasattr(m, "notes") for nt in m.notes
                ]
            else:
                st.session_state.pop("generated_notes", None)

            # Run mind map (graph) generation pipeline if selected
            graph_models: List[dict] = []
            if "Mind Maps" in study_types:
                graph_models.extend(
                    [
                        {"item": g, "type": "mind_map"}
                        for g in file_helper.generate_graphs_pipeline(
                            final_text, "mind_map"
                        )
                    ]
                )

            # Store or remove generated graphs in session state
            if graph_models:
                st.session_state.generated_graphs = graph_models
            else:
                st.session_state.pop("generated_graphs", None)

            # If nothing was generated, inform the user
            if not (
                st.session_state.get("generated_cards")
                or st.session_state.get("generated_notes")
                or st.session_state.get("generated_graphs")
            ):
                st.info("Nothing was generated.")
                return

            # Preserve previous UI selections and open the generation viewer
            if not st.session_state.generated_view:
                st.session_state.pre_gen_state = {
                    "selected_deck_id": st.session_state.get("selected_deck_id"),
                    "selected_deck_mode": st.session_state.get("selected_deck_mode"),
                    "selected_notebook_id": st.session_state.get("selected_notebook_id"),
                }
                st.session_state.generated_view = True
                st.rerun()

        # After generation tools, render the chatbot section
        render_chatbot_sidebar()


def render_chatbot_sidebar() -> None:
    """
    Render a fully-featured OpenAI chatbot interface in the sidebar.
    Reuses logic from main Chatbot module with minor location changes.
    """
    st.divider()  # Separator under Generate section
    st.markdown("## Chatbot 💬")

    # Fetch API key from environment for chatbot
    openai_api_key = os.getenv("OPENAI_API_KEY")

    # Initialize chat history in session state if absent
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "How can I help you?"}
        ]

    # Display each message in the chat history
    for message in st.session_state.messages:
        st.chat_message(message["role"]).write(message["content"])

    # Capture new user prompt
    if user_prompt := st.chat_input("Ask me anything…"):
        # Ensure API key is available
        if not openai_api_key:
            st.info("Please add an OpenAI API key to continue.")
            st.stop()

        client = OpenAI(api_key=openai_api_key)

        # Append and display user query
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        st.chat_message("user").write(user_prompt)

        # Get assistant response from OpenAI
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=st.session_state.messages,
        )
        reply = response.choices[0].message.content

        # Store and display assistant response
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.chat_message("assistant").write(reply)
