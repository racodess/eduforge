# 2_Notebook.py

import streamlit as st
from utils import notes_db
import os

# Initialize the notes database
notes_db.init_db()

# Custom CSS for theme
with open('././ui-theme/global.css') as f:
    css = f.read()
st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)

st.title("Notebook Dashboard")

# Retrieve notebooks from the database
notebooks = notes_db.get_notebooks()  # returns list of tuples (id, name)
notebook_options = {name: nid for nid, name in notebooks}

dashboard_option = "--- Dashboard ---"
options = [dashboard_option] + list(notebook_options.keys())

selected_notebook = st.selectbox("Select a Notebook", options)

if selected_notebook == dashboard_option:
    # ---------------------
    # DASHBOARD VIEW
    # ---------------------
    # Create Notebook area appears immediately under the selectbox (only for the dashboard)
    st.subheader("Create a New Notebook")
    new_notebook_name = st.text_input("New Notebook Name", key="new_notebook_dashboard")
    if st.button("Create Notebook"):
        if new_notebook_name.strip():
            # Check if a notebook with the same name already exists.
            if new_notebook_name.strip() in notebook_options:
                st.error("Notebook already exists.")
            else:
                notebook_id = notes_db.create_notebook(new_notebook_name.strip())
                if notebook_id is not None:
                    st.success(f"Notebook '{new_notebook_name}' created!")
                    # Clear the text input by resetting the session state value.
                    st.session_state["new_notebook_dashboard"] = ""
                    st.experimental_rerun()
                else:
                    st.error("An error occurred while creating the notebook.")
        else:
            st.warning("Please enter a notebook name.")

    # Dashboard view: AI note generation form and file, text, and URL input.
    st.subheader("Generate Study Notes")
    st.write(
        "Generate study notes from a file, pasted text, or a URL. "
        "This is useful if you have raw study material you'd like to turn into notes."
    )
    # Initialize generated_notes in session state if not already present.
    if "generated_notes" not in st.session_state:
        st.session_state.generated_notes = []

    # --- File uploader, text input, and URL input ---
    uploaded_file = st.file_uploader(
        label="Upload a .txt, .pdf, or image file (optional)",
        type=["txt", "pdf", "png", "jpg", "jpeg", "gif"],
        help="Provide a text file, PDF, or image with the content you want to convert into notes."
    )

    page_range = None
    if uploaded_file is not None and uploaded_file.name.lower().endswith('.pdf'):
        try:
            from PyPDF2 import PdfReader
            uploaded_file.seek(0)
            pdf_reader = PdfReader(uploaded_file)
            total_pages = len(pdf_reader.pages)
            uploaded_file.seek(0)
        except Exception as e:
            total_pages = 0
        col1, col2 = st.columns(2)
        start_page = col1.number_input("Start Page", min_value=1, max_value=total_pages if total_pages > 0 else 1, value=1, step=1)
        end_page = col2.number_input("End Page", min_value=1, max_value=total_pages if total_pages > 0 else 1, value=total_pages if total_pages > 0 else 1, step=1)
        page_range = (start_page, end_page)

    text_input = st.text_area(
        "Or paste text content here",
        "",
        help="You can directly paste your notes or content here."
    )

    url_input = st.text_input(
        "Or provide a URL (optional)",
        "",
        help="If you want to pull text from a URL, enter it here."
    )

    if st.button("Generate Notes", use_container_width=True):
        from utils.file_helper import FileHelper
        file_helper = FileHelper()
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
            st.warning("No valid content provided. Please upload a file, paste text, or enter a URL.")
        else:
            generated_models = file_helper.generate_notes_pipeline(final_text)
            generated_notes = []
            for model_instance in generated_models:
                if hasattr(model_instance, "notes"):
                    generated_notes.extend(model_instance.notes)
            st.session_state.generated_notes = generated_notes
            if generated_notes:
                st.success(f"Generated {len(generated_notes)} notes!")
            else:
                st.info("No notes were generated.")

    # Display generated notes, if any.
    if st.session_state.get("generated_notes"):
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>Generated Notes</h2>", unsafe_allow_html=True)
        all_cols = st.columns(2)
        with all_cols[0]:
            if st.button("Add All Generated Notes", use_container_width=True):
                # (Implement adding to a notebook as needed)
                st.success("Added all generated notes to your notebooks!")
                st.session_state.generated_notes = []
                st.experimental_rerun()
        with all_cols[1]:
            if st.button("Delete All Generated Notes", use_container_width=True):
                st.session_state.generated_notes = []
                st.experimental_rerun()

        for i, note in enumerate(st.session_state.generated_notes):
            with st.container():
                st.markdown(f"### Note {i+1}: {note.title}")
                st.markdown(note.content)
                note_cols = st.columns(3)
                with note_cols[0]:
                    if st.button("Add", key=f"note_add_{i}", use_container_width=True):
                        st.success(f"Note {i+1} added!")
                with note_cols[1]:
                    if st.button("Regenerate", key=f"note_regen_{i}", use_container_width=True):
                        st.success(f"Note {i+1} regenerated!")
                with note_cols[2]:
                    if st.button("Delete", key=f"note_delete_{i}", use_container_width=True):
                        st.session_state.generated_notes.pop(i)
                        st.experimental_rerun()

else:
    # ---------------------
    # NOTEBOOK (Tab) VIEW
    # ---------------------
    notebook_id = notebook_options[selected_notebook]
    st.subheader(f"Notebook: {selected_notebook}")
    
    # Fetch tabs (notes) for the selected notebook.
    notes = notes_db.get_notes(notebook_id)  # List of tuples: (id, tab_name, content)
    if not notes:
        st.info("No notes found in this notebook.")
    
    # For the default tab: if the "Default" note has no content, fill it with explanatory text.
    default_note_instruction = (
        "Welcome to your notebook! This is the default note explaining how to use the notes feature.\n\n"
        "Use the 'Add Tab' button to create new notes, and 'Delete Tab' to remove notes (except this default note).\n\n"
        "You can edit notes using the 'Edit Tab' button, and rename notes using the 'Rename Tab' option.\n\n"
        "To return to the dashboard, select '--- Dashboard ---' from the notebook drop-down at the top."
    )
    updated_notes = []
    for note in notes:
        note_id, tab_name, content = note
        if tab_name == "Default" and content.strip() == "":
            content = default_note_instruction
        updated_notes.append((note_id, tab_name, content))
    notes = updated_notes

    # Allow the user to select which tab to manage.
    tab_names = [note[1] for note in notes]
    management_tab = st.selectbox("Select Tab for Management", tab_names, key="management_tab_select")
    current_note = next(note for note in notes if note[1] == management_tab)
    current_note_id, current_tab_name, current_content = current_note

    st.markdown("---")
    # Four buttons for tab interactions: Add, Delete, Rename, and Edit.
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Add Tab"):
            # Adds a new tab with a default name and empty content.
            notes_db.create_note(notebook_id, "New Tab", "")
            st.success("New tab added!")
            st.experimental_rerun()
    with col2:
        if st.button("Delete Tab"):
            if current_tab_name == "Default":
                st.error("The default tab cannot be deleted.")
            else:
                notes_db.delete_note(current_note_id)
                st.success("Tab deleted!")
                st.experimental_rerun()
    with col3:
        new_tab_name = st.text_input("New Tab Name", value=current_tab_name, key="rename_tab_input")
        if st.button("Rename Tab"):
            notes_db.rename_note(current_note_id, new_tab_name)
            st.success("Tab renamed!")
            st.experimental_rerun()
    with col4:
        # Toggle edit mode for the selected tab.
        edit_key = f"editing_{current_note_id}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False
        if not st.session_state[edit_key]:
            if st.button("Edit Tab"):
                st.session_state[edit_key] = True
                st.experimental_rerun()
        else:
            if st.button("Cancel Edit"):
                st.session_state[edit_key] = False
                st.experimental_rerun()
            # Show a form to edit the tab content.
            with st.form(key=f"edit_form_{current_note_id}"):
                edited_content = st.text_area("Edit Note Content", value=current_content, height=300)
                if st.form_submit_button("Save"):
                    notes_db.update_note(current_note_id, edited_content)
                    st.session_state[edit_key] = False
                    st.success("Note updated!")
                    st.experimental_rerun()

    # Render each tab’s content in a st.tabs widget for preview.
    tab_labels = [note[1] for note in notes]
    tabs = st.tabs(tab_labels)
    for idx, (note_id, tab_name, content) in enumerate(notes):
        with tabs[idx]:
            st.markdown(f"## {tab_name}")
            st.markdown(content if content else "*(No content yet)*")
