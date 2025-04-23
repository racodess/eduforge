# generated_items.py

"""
Display and manage AI-generated study items (flashcards, notes, graphs) in a dedicated view.
Includes import, regeneration, and deletion workflows integrated with database utilities.
"""

import re
import streamlit as st

from utils.flashcards_db import add_card
from utils.notes_db import create_note
from utils.file_helper import FileHelper


def render_generated_items_window() -> None:
    """
    Render the full-screen view for generated items, with Back button and sections
    for Flashcards, Notes, and Graphs based on session_state content.
    """
    # Top row: Back button and header
    top_cols = st.columns([2, 8])
    if top_cols[0].button("Back", key="gen_back_btn", use_container_width=True):

        # Restore previous UI context if available
        if st.session_state.pre_gen_state:
            for key, val in st.session_state.pre_gen_state.items():
                st.session_state[key] = val

        # Exit generated view
        st.session_state.generated_view = False
        st.session_state.pre_gen_state = None
        st.rerun()

    # Title for generated items section
    top_cols[1].markdown(
        "<h2 style='text-align:left;'>Generated Items</h2>",
        unsafe_allow_html=True
    )
    st.markdown("<hr>", unsafe_allow_html=True)

    # Flashcards section
    if st.session_state.get("generated_cards"): # show only if cards exist
        st.markdown(
            "<h2 style='text-align:center;'>Flashcards</h2>",
            unsafe_allow_html=True
        )
        _render_generated_flashcards_section()

    # Vertical spacing between sections
    st.text("\n" * 4)

    # Notes section
    if st.session_state.get("generated_notes"): # show only if notes exist
        st.markdown(
            "<h2 style='text-align:center;'>Notes</h2>",
            unsafe_allow_html=True
        )
        _render_generated_notes_section()

    # More spacing
    st.text("\n" * 4)

    # Graphs section
    if st.session_state.get("generated_graphs"): # show only if graphs exist
        st.markdown(
            "<h2 style='text-align:center;'>Graphs</h2>",
            unsafe_allow_html=True
        )
        _render_generated_graphs_section()

    # Inform if nothing was generated
    if not (
        st.session_state.get("generated_cards") or
        st.session_state.get("generated_notes") or
        st.session_state.get("generated_graphs")
    ):
        st.info("No generated items to display.")


# Helper for flashcards
def _render_generated_flashcards_section() -> None:
    """
    Render controls and list for generated flashcards,
    allowing bulk import/delete and per-card actions.
    """
    target_ids = st.session_state.get("gen_target_deck_ids", [])
    if not target_ids:
        st.error("Target deck(s) not found – please re‑run generation.")
        return

    # Action buttons: import or clear all
    col_a, col_b = st.columns(2)
    if col_a.button("Add All Flashcards", use_container_width=True):
        for deck_id in target_ids:
            for card in st.session_state.generated_cards:
                add_card(deck_id, card.front, card.back, extra_fields=None)
        st.success("Imported all flashcards!")
        st.session_state.generated_cards = []
        st.rerun()
    if col_b.button("Delete All Flashcards", use_container_width=True):
        st.session_state.generated_cards = []
        st.rerun()

    # Render each flashcard container
    for idx, card in enumerate(st.session_state.generated_cards):
        _render_flashcard_container(card, idx)


def _render_flashcard_container(card, idx: int) -> None:
    """
    Display a single generated flashcard with its front/back content
    and buttons to add, regenerate, or delete.
    """
    # Layout columns to center the card
    _, middle, _ = st.columns([1, 6, 1])
    with middle:
        with st.container(border=True):
            # Card header
            st.markdown(
                f'<div style="text-align: left; font-size: 16px;"><strong>Flashcard {idx+1}</strong></div>',
                unsafe_allow_html=True
            )
            st.text("")

            # Front side
            st.markdown('<div style="text-align: center;"><h3>Front</h3></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="text-align: center;">{card.front}</div>', unsafe_allow_html=True)

            st.text("")
            st.text("")

            # Back side
            st.markdown('<div style="text-align: center;"><h3>Back</h3></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="text-align: center;">{card.back}</div>', unsafe_allow_html=True)

            st.divider()

            # Action buttons: Add, Regenerate, Delete
            b1, b2, b3 = st.columns(3)
            if b1.button("", key=f"add_fc_{idx}", type="secondary",
                          icon=":material/add_circle:", use_container_width=True):
                for deck_id in st.session_state.get("gen_target_deck_ids", []):
                    add_card(deck_id, card.front, card.back, extra_fields=None)
                st.session_state.generated_cards.pop(idx)
                st.rerun()
            if b2.button("", key=f"regen_fc_{idx}", type="secondary",
                          icon=":material/cached:", use_container_width=True):
                # Regenerate card via FileHelper logic
                new_card = FileHelper().regenerate_flashcard(card)
                st.session_state.generated_cards[idx] = new_card
                st.rerun()
            if b3.button("", key=f"del_fc_{idx}", type="secondary",
                          icon=":material/cancel:", use_container_width=True):
                st.session_state.generated_cards.pop(idx)
                st.rerun()


# Helper for notes
def _render_generated_notes_section() -> None:
    """
    Render controls and list for generated notes,
    allowing bulk import/delete and per-note actions.
    """
    nb_ids = st.session_state.get("gen_target_nb_ids", [])
    if not nb_ids:
        st.error("Target notebook(s) not found – please re‑run generation.")
        return

    # Bulk import or clear all notes
    col_a, col_b = st.columns(2)
    if col_a.button("Add All Notes", use_container_width=True):
        for nb_id in nb_ids:
            for note in st.session_state.generated_notes:
                create_note(nb_id, note.title, note.content)
        st.success("Imported all notes!")
        st.session_state.generated_notes = []
        st.rerun()
    if col_b.button("Delete All Notes", use_container_width=True):
        st.session_state.generated_notes = []
        st.rerun()

    # Render each note container
    for idx, note in enumerate(st.session_state.generated_notes):
        _render_note_container(note, idx)


def _render_note_container(note, idx: int) -> None:
    """
    Display a single generated note with title and content,
    and buttons to add, regenerate, or delete.
    """
    _, middle, _ = st.columns([1, 6, 1])
    with middle:
        with st.container(border=True):
            # Note header
            st.markdown(
                f"<div style='text-align: left; font-size: 16px;'><strong>Note {idx+1}</strong></div>",
                unsafe_allow_html=True,
            )
            st.text("")

            # Note title underlined
            st.markdown(
                f"<div style='text-align: center;'><h3><u>{note.title}</u></h3></div>",
                unsafe_allow_html=True,
            )

            # Render Graphviz if present, else markdown content
            code = _extract_graphviz(note.content)
            if code:
                st.graphviz_chart(code, use_container_width=True)
            else:
                st.markdown(note.content, unsafe_allow_html=True)

            st.divider()
            b1, b2, b3 = st.columns(3)
            if b1.button("", key=f"add_nt_{idx}", type="secondary",
                          icon=":material/add_circle:", use_container_width=True):
                for nb_id in st.session_state.get("gen_target_nb_ids", []):
                    create_note(nb_id, note.title, note.content)
                st.session_state.generated_notes.pop(idx)
                st.rerun()
            if b2.button("", key=f"regen_nt_{idx}", type="secondary",
                          icon=":material/cached:", use_container_width=True):
                new_note = FileHelper().regenerate_note(note)
                st.session_state.generated_notes[idx] = new_note
                st.rerun()
            if b3.button("", key=f"del_nt_{idx}", type="secondary",
                          icon=":material/cancel:", use_container_width=True):
                st.session_state.generated_notes.pop(idx)
                st.rerun()


# Helper for graphs
def _extract_graphviz(content: str) -> str | None:
    """
    Extract DOT code if content contains a Graphviz fenced block
    or appears to be raw DOT text.
    """
    # Look for fenced graphviz or dot block
    match = re.search(r"```(?:graphviz|dot)\s+([\s\S]+?)```", content, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback: content starting with graph or digraph keywords
    stripped = content.strip()
    if re.match(r"^(strict\s+)?(di)?graph\b", stripped, re.IGNORECASE):
        return stripped

    # No Graphviz code detected
    return None


def _render_generated_graphs_section() -> None:
    """
    Render controls and list for generated graphs,
    allowing bulk import/delete and per-graph actions.
    """
    nb_ids = st.session_state.get("gen_target_nb_ids", [])
    if not nb_ids:
        st.error("Target notebook(s) not found – please re‑run generation.")
        return

    # Bulk add or clear all graphs
    col_a, col_b = st.columns(2)
    if col_a.button("Add All Graphs", use_container_width=True):
        for nb_id in nb_ids:
            for g in st.session_state.generated_graphs:
                create_note(nb_id, g["item"].title, g["item"].content)
        st.success("Imported all graphs!")
        st.session_state.generated_graphs = []
        st.rerun()
    if col_b.button("Delete All Graphs", use_container_width=True):
        st.session_state.generated_graphs = []
        st.rerun()

    # Render each graph container
    for idx, gdict in enumerate(st.session_state.generated_graphs):
        _render_graph_container(gdict, idx)


def _render_graph_container(gdict: dict, idx: int) -> None:
    """
    Display a single generated graph with title, Graphviz chart or raw content,
    and buttons to add, regenerate, or delete.
    """
    graph_item = gdict["item"]
    graph_type = gdict["type"]
    code = _extract_graphviz(graph_item.content)

    _, middle, _ = st.columns([1, 6, 1])
    with middle:
        with st.container(border=True):
            # Graph header showing index and type
            st.markdown(
                f"<div style='text-align: left; font-size: 16px;'><strong>"
                f"Graph {idx+1} ({graph_type.replace('_',' ').title()})</strong></div>",
                unsafe_allow_html=True,
            )
            st.text("")

            # Graph title
            st.markdown(
                f"<div style='text-align: center;'><h3><u>{graph_item.title}</u></h3></div>",
                unsafe_allow_html=True,
            )

            # Render chart or raw content with error if not valid
            if code:
                st.graphviz_chart(code, use_container_width=True)
            else:
                st.error("GraphViz block not detected – displaying raw content:")
                st.markdown(graph_item.content, unsafe_allow_html=True)

            st.divider()
            b1, b2, b3 = st.columns(3)
            if b1.button("", key=f"add_gr_{idx}", type="secondary",
                          icon=":material/add_circle:", use_container_width=True):
                for nb_id in st.session_state.get("gen_target_nb_ids", []):
                    create_note(nb_id, graph_item.title, graph_item.content)
                st.session_state.generated_graphs.pop(idx)
                st.rerun()
            if b2.button("", key=f"regen_gr_{idx}", type="secondary",
                          icon=":material/cached:", use_container_width=True):
                # Regenerate graph via FileHelper logic
                new_graph = FileHelper().regenerate_graph(graph_item, graph_type=graph_type)
                st.session_state.generated_graphs[idx]["item"] = new_graph
                st.rerun()
            if b3.button("", key=f"del_gr_{idx}", type="secondary",
                          icon=":material/cancel:", use_container_width=True):
                st.session_state.generated_graphs.pop(idx)
                st.rerun()
