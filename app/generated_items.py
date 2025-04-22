import re
import streamlit as st

from utils.flashcards_db import add_card
from utils.notes_db import create_note
from utils.file_helper import FileHelper

def render_generated_items_window():
    top_cols = st.columns([2, 8])
    if top_cols[0].button("Back", key="gen_back_btn", use_container_width=True):
        if st.session_state.pre_gen_state:
            for k, v in st.session_state.pre_gen_state.items():
                st.session_state[k] = v
        st.session_state.generated_view = False
        st.session_state.pre_gen_state = None
        st.rerun()

    top_cols[1].markdown("<h2 style='text-align:left;'>Generated Items</h2>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    # FLASHCARDS
    if st.session_state.get("generated_cards"):
        st.markdown("<h2 style='text-align:center;'>Flashcards</h2>", unsafe_allow_html=True)
        _render_generated_flashcards_section()

    st.text("")
    st.text("")
    st.text("")
    st.text("")

    # NOTES
    if st.session_state.get("generated_notes"):
        st.markdown("<h2 style='text-align:center;'>Notes</h2>", unsafe_allow_html=True)
        _render_generated_notes_section()

    st.text("")
    st.text("")
    st.text("")
    st.text("")

    # GRAPHS
    if st.session_state.get("generated_graphs"):
        st.markdown("<h2 style='text-align:center;'>Graphs</h2>", unsafe_allow_html=True)
        _render_generated_graphs_section()

    if not (
        st.session_state.get("generated_cards")
        or st.session_state.get("generated_notes")
        or st.session_state.get("generated_graphs")
    ):
        st.info("No generated items to display.")

# ================= helper: flashcards =========================
def _render_generated_flashcards_section():
    target_ids = st.session_state.get("gen_target_deck_ids", [])
    if not target_ids:
        st.error("Target deck(s) not found – please re‑run generation.")
        return

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

    for i, card in enumerate(st.session_state.generated_cards):
        _render_flashcard_container(card, i)

def _render_flashcard_container(card, idx):
    ccols = st.columns([1, 6, 1])
    with ccols[1]:
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align: left; font-size: 16px;"><strong>Flashcard {idx+1}</strong></div>',
                unsafe_allow_html=True
            )
            st.text("")

            st.markdown('<div style="text-align: center;"><h3>Front</h3></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="text-align: center;">{card.front}</div>', unsafe_allow_html=True)

            st.text("")
            st.text("")

            st.markdown('<div style="text-align: center;"><h3>Back</h3></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="text-align: center;">{card.back}</div>', unsafe_allow_html=True)

            st.divider()

            b1, b2, b3 = st.columns(3)
            if b1.button("", key=f"add_fc_{idx}", type="tertiary", icon=":material/add_circle:", use_container_width=True):
                for deck_id in st.session_state.get("gen_target_deck_ids", []):
                    add_card(deck_id, card.front, card.back, extra_fields=None)
                st.session_state.generated_cards.pop(idx)
                st.rerun()
            if b2.button("", key=f"regen_fc_{idx}", type="tertiary", icon=":material/cached:", use_container_width=True):
                new_card = FileHelper().regenerate_flashcard(card)
                st.session_state.generated_cards[idx] = new_card
                st.rerun()
            if b3.button("", key=f"del_fc_{idx}", type="tertiary", icon=":material/cancel:", use_container_width=True):
                st.session_state.generated_cards.pop(idx)
                st.rerun()

# ================= helper: notes ==============================
def _render_generated_notes_section():
    nb_ids = st.session_state.get("gen_target_nb_ids", [])
    if not nb_ids:
        st.error("Target notebook(s) not found – please re‑run generation.")
        return

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

    for i, note in enumerate(st.session_state.generated_notes):
        _render_note_container(note, i)

def _render_note_container(note, idx):
    ccols = st.columns([1, 6, 1])
    with ccols[1]:
        with st.container(border=True):
            st.markdown(
                f"<div style='text-align: left; font-size: 16px;'><strong>Note {idx+1}</strong></div>",
                unsafe_allow_html=True,
            )
            st.text("")
            st.markdown(
                f"<div style='text-align: center;'><h3><u>{note.title}</u></h3></div>",
                unsafe_allow_html=True,
            )
            code = _extract_graphviz(note.content)
            if code:
                st.graphviz_chart(code, use_container_width=True)
            else:
                st.markdown(note.content, unsafe_allow_html=True)

            st.divider()
            b1, b2, b3 = st.columns(3)
            # buttons unchanged except regen now works with note regeneration prompt
            if b1.button("", key=f"add_nt_{idx}", type="tertiary", icon=":material/add_circle:", use_container_width=True):
                for nb_id in st.session_state.get("gen_target_nb_ids", []):
                    create_note(nb_id, note.title, note.content)
                st.session_state.generated_notes.pop(idx)
                st.rerun()
            if b2.button("", key=f"regen_nt_{idx}", type="tertiary", icon=":material/cached:", use_container_width=True):
                new_note = FileHelper().regenerate_note(note)
                st.session_state.generated_notes[idx] = new_note
                st.rerun()
            if b3.button("", key=f"del_nt_{idx}", type="tertiary", icon=":material/cancel:", use_container_width=True):
                st.session_state.generated_notes.pop(idx)
                st.rerun()

# ================= helper: graphs ===========================================

def _extract_graphviz(content: str) -> str | None:
    """Return DOT if content contains a graphviz code block **or** looks like raw DOT."""
    m = re.search(r"```(?:graphviz|dot)\s+([\s\S]+?)```", content, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # fall‑back: raw DOT if it begins with graph keyword
    stripped = content.strip()
    if re.match(r"^(strict\s+)?(di)?graph\b", stripped, re.IGNORECASE):
        return stripped
    return None

def _render_generated_graphs_section():
    nb_ids = st.session_state.get("gen_target_nb_ids", [])
    if not nb_ids:
        st.error("Target notebook(s) not found – please re‑run generation.")
        return

    col_a, col_b = st.columns(2)
    if col_a.button("Add All Graphs", use_container_width=True):
        for nb_id in nb_ids:
            for gdict in st.session_state.generated_graphs:
                create_note(nb_id, gdict["item"].title, gdict["item"].content)
        st.success("Imported all graphs!")
        st.session_state.generated_graphs = []
        st.rerun()
    if col_b.button("Delete All Graphs", use_container_width=True):
        st.session_state.generated_graphs = []
        st.rerun()

    for i, gdict in enumerate(st.session_state.generated_graphs):
        _render_graph_container(gdict, i)

def _render_graph_container(gdict: dict, idx: int):
    graph_note = gdict["item"]
    gtype = gdict["type"]
    code = _extract_graphviz(graph_note.content)
    ccols = st.columns([1, 6, 1])
    with ccols[1]:
        with st.container(border=True):
            st.markdown(
                f"<div style='text-align: left; font-size: 16px;'><strong>Graph {idx+1} ({gtype.replace('_', ' ').title()})</strong></div>",
                unsafe_allow_html=True,
            )
            st.text("")
            st.markdown(
                f"<div style='text-align: center;'><h3><u>{graph_note.title}</u></h3></div>",
                unsafe_allow_html=True,
            )

            if code:
                st.graphviz_chart(code, use_container_width=True)
            else:
                st.error("GraphViz block not detected – displaying raw content:")
                st.markdown(graph_note.content, unsafe_allow_html=True)

            st.divider()
            b1, b2, b3 = st.columns(3)
            if b1.button("", key=f"add_gr_{idx}", type="tertiary", icon=":material/add_circle:", use_container_width=True):
                for nb_id in st.session_state.get("gen_target_nb_ids", []):
                    create_note(nb_id, graph_note.title, graph_note.content)
                st.session_state.generated_graphs.pop(idx)
                st.rerun()
            if b2.button("", key=f"regen_gr_{idx}", type="tertiary", icon=":material/cached:", use_container_width=True):
                new_graph = FileHelper().regenerate_graph(graph_note, graph_type=gtype)
                st.session_state.generated_graphs[idx]["item"] = new_graph
                st.rerun()
            if b3.button("", key=f"del_gr_{idx}", type="tertiary", icon=":material/cancel:", use_container_width=True):
                st.session_state.generated_graphs.pop(idx)
                st.rerun()
