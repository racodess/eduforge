import os

import streamlit as st
from typing import List
from openai import OpenAI

from utils.flashcards_db import get_decks
from utils.notes_db import get_notebooks
from utils.file_helper import FileHelper

def render_generation_sidebar():
    """Generation tool now lives permanently in the sidebar."""
    with st.sidebar:
        st.markdown("## Generate Study Material")

        # pick study‑material type
        study_types = st.multiselect(
            "Select study material type(s)",
            options=[
                "Flashcards",
                "Notebooks", # traditional markdown notes
                "Mind Maps",
            ],
            key="gen_study_types",
        )

        # dynamically show target multiselect
        # Flashcard decks selection
        if "Flashcards" in study_types:
            decks = get_decks()
            if not decks:
                st.error("No decks available. Please create a deck first.")
                return
            deck_opts = {dname: did for did, dname in decks}
            st.session_state.gen_target_deck_ids = st.multiselect(
                "Target deck(s)",
                options=list(deck_opts.keys()),
                default=list(deck_opts.keys())[:1],
                key="gen_deck_select",
            )
            st.session_state.gen_target_deck_ids = [
                deck_opts[name] for name in st.session_state.gen_target_deck_ids
            ]
        else:
            st.session_state.pop("gen_target_deck_ids", None)

        # ALL notebook‑bound study types (notes *and* graphs)
        needs_notebooks = any(
            t in study_types for t in ["Notebooks", "Mind Maps"]
        )
        if needs_notebooks:
            notebooks = get_notebooks()
            if not notebooks:
                st.error("No notebooks available. Please create one first.")
                return
            nb_opts = {nname: nid for nid, nname in notebooks}
            st.session_state.gen_target_nb_ids = st.multiselect(
                "Target notebook(s)",
                options=list(nb_opts.keys()),
                default=list(nb_opts.keys())[:1],
                key="gen_nb_select",
            )
            st.session_state.gen_target_nb_ids = [
                nb_opts[name] for name in st.session_state.gen_target_nb_ids
            ]
        else:
            st.session_state.pop("gen_target_nb_ids", None)

        # shared content inputs
        file_helper = FileHelper()

        uploaded_file = st.file_uploader(
            label="Upload a .txt, .pdf, or image file",
            type=["txt", "pdf", "png", "jpg", "jpeg", "gif"],
            key="gen_file_uploader",
        )

        page_range = None
        if uploaded_file is not None and uploaded_file.name.lower().endswith(".pdf"):
            try:
                from PyPDF2 import PdfReader
                uploaded_file.seek(0)
                pdf_reader = PdfReader(uploaded_file)
                total_pages = len(pdf_reader.pages)
                uploaded_file.seek(0)
            except Exception:
                total_pages = 0
            sc1, sc2 = st.columns(2)
            start_page = sc1.number_input("Start Page", min_value=1, max_value=total_pages if total_pages else 1, value=1, step=1)
            end_page = sc2.number_input("End Page", min_value=1, max_value=total_pages if total_pages else 1, value=total_pages if total_pages else 1, step=1)
            page_range = (start_page, end_page)

        text_input = st.text_area("Or paste text content here", "", key="gen_text_input")
        url_input = st.text_input("Or provide a URL", "", key="gen_url_input")

        # GENERATE button
        if st.button("Generate", key="gen_button", use_container_width=True):
            final_text = ""

            if uploaded_file is not None:
                if uploaded_file.name.lower().endswith('.pdf') and page_range is not None:
                    final_text = file_helper.process_file(uploaded_file, start_page=page_range[0], end_page=page_range[1])
                else:
                    final_text = file_helper.process_file(uploaded_file)
            elif text_input.strip():
                final_text = file_helper.process_text(text_input.strip())
            elif url_input.strip():
                final_text = file_helper.process_url(url_input.strip())

            if not final_text:
                st.warning("No valid content provided!")
                return
            
            # run the pipelines
            if "Flashcards" in study_types:
                flashcard_models = file_helper.generate_flashcards_pipeline(final_text)
                st.session_state.generated_cards = [
                    fc
                    for m in flashcard_models
                    if hasattr(m, "flashcards")
                    for fc in m.flashcards
                ]
            else:
                st.session_state.pop("generated_cards", None)

            if "Notebooks" in study_types:
                note_models = file_helper.generate_notes_pipeline(final_text)
                st.session_state.generated_notes = [
                    nt for m in note_models if hasattr(m, "notes") for nt in m.notes
                ]
            else:
                st.session_state.pop("generated_notes", None)

            # Mind Maps
            graph_models: List[dict] = []
            if "Mind Maps" in study_types:
                graph_models.extend(
                    [
                        {
                            "item": g,
                            "type": "mind_map",
                        }
                        for g in file_helper.generate_graphs_pipeline(final_text, "mind_map")
                    ]
                )

            if graph_models:
                st.session_state.generated_graphs = graph_models
            else:
                st.session_state.pop("generated_graphs", None)

            if not (
                st.session_state.get("generated_cards")
                or st.session_state.get("generated_notes")
                or st.session_state.get("generated_graphs")
            ):
                st.info("Nothing was generated.")
                return

            # save previous UI context & open dedicated viewer
            if not st.session_state.generated_view:
                st.session_state.pre_gen_state = {
                    "selected_deck_id": st.session_state.get("selected_deck_id"),
                    "selected_deck_mode": st.session_state.get("selected_deck_mode"),
                    "selected_notebook_id": st.session_state.get("selected_notebook_id"),
                }
                st.session_state.generated_view = True
                st.rerun()

        render_chatbot_sidebar()

def render_chatbot_sidebar():
    """
    Fully‑featured OpenAI chatbot.
    (Logic copied from 4_Chatbot.py – only the location changed.)
    """
    st.divider()                      # ← required divider under Generate
    st.markdown("## Chatbot 💬")

    openai_api_key = os.getenv("OPENAI_API_KEY")

    # Initialise chat history once
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "How can I help you?"}
        ]

    # Display history
    for m in st.session_state.messages:
        st.chat_message(m["role"]).write(m["content"])

    # Handle new user input
    if prompt := st.chat_input("Ask me anything…"):
        if not openai_api_key:
            st.info("Please add an OpenAI API key to continue.")
            st.stop()

        client = OpenAI(api_key=openai_api_key)

        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=st.session_state.messages,
        )
        reply = resp.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.chat_message("assistant").write(reply)
