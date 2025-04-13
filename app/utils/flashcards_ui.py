# flashcards_ui.py

import streamlit as st
import base64
import json
import re

from utils.flashcards_db import update_card, add_card
from utils.flashcards_sm2 import project_interval, format_interval_short

# Regex / Helper functions for base64 image handling
IMAGE_PATTERN = re.compile(
    r"!\[.*?\]\((data:image/(?:png|jpe?g|gif);base64,.*?)\)",
    flags=re.IGNORECASE | re.DOTALL
)

def extract_base64_images(text: str):
    """
    Returns a list of data URIs found in markdown syntax:
    ![...](data:image/png;base64,...)
    """
    return IMAGE_PATTERN.findall(text)

def remove_base64_image_from_text(text: str, data_uri: str):
    """
    Removes the exact ![Attached Image](data_uri) markdown snippet from text.
    """
    import re
    pattern = re.escape(f"![Attached Image]({data_uri})")
    return re.sub(pattern, "", text)


# Rendering a card's front/back + extras with st.image where needed
def render_card_visual(front, back, extras=None, show_back=False):
    """
    Renders the card's front, and optionally back + extras.
    Any embedded data URIs are extracted and displayed via st.image().
    """
    # --- FRONT ---
    st.markdown("<h1 style='text-align:center;'>Front</h1>", unsafe_allow_html=True)
    front_images = extract_base64_images(front)
    text_front_no_images = IMAGE_PATTERN.sub("", front)
    st.markdown(text_front_no_images)
    for img in front_images:
        st.image(img)

    if show_back:
        st.divider()
        # --- BACK ---
        st.markdown("<h1 style='text-align:center;'>Back</h1>", unsafe_allow_html=True)
        back_images = extract_base64_images(back)
        text_back_no_images = IMAGE_PATTERN.sub("", back)
        st.markdown(text_back_no_images)
        for img in back_images:
            st.image(img)

    # --- EXTRAS ---
    if extras and len(extras) > 0:
        st.divider()
        for field_name, field_value in extras.items():
            st.markdown(f"### {field_name}")
            field_images = extract_base64_images(field_value)
            text_extra_no_images = IMAGE_PATTERN.sub("", field_value)
            st.markdown(text_extra_no_images)
            for img in field_images:
                st.image(img)


# Main form: Add/Edit a card
def render_card_form(deck_id, editing=False, card_data=None, allow_image_attach=False):
    """
    Renders a form for adding or editing a card.
    If editing=True and card_data is given, fields are pre-populated.
    The 'allow_image_attach' flag determines whether the image-upload
    and removal UI is shown.
    """

    if "card_form_values" not in st.session_state:
        st.session_state.card_form_values = {}
    if deck_id not in st.session_state.card_form_values:
        st.session_state.card_form_values[deck_id] = {}

    # ------------------ Load existing data (if editing) ------------------
    if editing and card_data:
        db_front = card_data[2]  # front
        db_back  = card_data[3]  # back
        db_extra_json = card_data[8]

        if db_extra_json:
            try:
                db_extra_data = json.loads(db_extra_json)
            except:
                db_extra_data = {}
        else:
            db_extra_data = {}

        for field in st.session_state.deck_fields[deck_id]:
            if field == "Front":
                st.session_state.card_form_values[deck_id][field] = db_front
            elif field == "Back":
                st.session_state.card_form_values[deck_id][field] = db_back
            else:
                st.session_state.card_form_values[deck_id][field] = db_extra_data.get(field, "")
    else:
        # Clear fields if adding new
        for field in st.session_state.deck_fields[deck_id]:
            if field not in st.session_state.card_form_values[deck_id]:
                st.session_state.card_form_values[deck_id][field] = ""

    # ------------------ FORM ------------------
    with st.form(f"card_form_{deck_id}"):
        # Text fields
        for field in st.session_state.deck_fields[deck_id]:
            st.session_state.card_form_values[deck_id][field] = st.text_area(
                label=field,
                value=st.session_state.card_form_values[deck_id][field],
                placeholder=f"Enter {field} here",
                key=f"card_field_{deck_id}_{field}",
                height=80
            )

        # --- Live preview ---
        front_val = st.session_state.card_form_values[deck_id].get("Front", "")
        back_val  = st.session_state.card_form_values[deck_id].get("Back", "")
        extras_val = {
            f: st.session_state.card_form_values[deck_id][f]
            for f in st.session_state.deck_fields[deck_id]
            if f not in ("Front", "Back")
        }

        st.markdown("---")
        st.markdown("<h6 style='text-align:center;'>Preview</h6>", unsafe_allow_html=True)
        render_card_visual(front_val, back_val, extras=extras_val, show_back=True)

        # --- Submit / Edit fields buttons ---
        btn_cols = st.columns([1, 1])
        submit_label = "Update Card" if editing else "Add Card"
        submitted = btn_cols[0].form_submit_button(submit_label)
        edit_pressed = btn_cols[1].form_submit_button("Edit Fields")

        if edit_pressed:
            st.session_state.edit_fields = True
            st.stop()

        if submitted:
            if front_val.strip() and back_val.strip():
                new_extras_data = {
                    f: st.session_state.card_form_values[deck_id][f]
                    for f in st.session_state.deck_fields[deck_id]
                    if f not in ("Front", "Back")
                }
                if editing and card_data:
                    card_id = card_data[0]
                    update_card(card_id, front_val.strip(), back_val.strip(), new_extras_data)
                    st.success("Flashcard updated!")
                    st.session_state.selected_card_id = None
                else:
                    add_card(deck_id, front_val.strip(), back_val.strip(), new_extras_data)
                    st.success("Flashcard added!")

                st.session_state.card_form_values[deck_id].clear()
                st.rerun()
            else:
                st.error("Please provide both Front and Back text.")

    # ------------------ IMAGE ATTACH / REMOVE (conditional) ------------------
    if allow_image_attach:
        st.markdown("---")
        st.markdown("**Attach an image to one of the fields**")
        field_choice = st.selectbox(
            "Select which field to attach the image to",
            st.session_state.deck_fields[deck_id],
            key=f"attach_field_choice_{deck_id}"
        )
        uploaded_file = st.file_uploader(
            "Upload image",
            type=["png", "jpg", "jpeg", "gif"],
            key=f"img_uploader_{deck_id}"
        )

        # If user uploaded an image, convert to data URI, insert into the chosen field
        if uploaded_file is not None:
            file_bytes = uploaded_file.read()
            b64_data = base64.b64encode(file_bytes).decode("utf-8")

            # Example mime_type: "image/png"
            mime_type = uploaded_file.type
            ext = mime_type.split("/")[-1].lower()
            if ext not in ("png", "jpg", "jpeg", "gif"):
                ext = "png"  # fallback

            data_uri = f"data:image/{ext};base64,{b64_data}"
            chosen_text = st.session_state.card_form_values[deck_id][field_choice]

            if data_uri not in chosen_text:
                new_text = chosen_text + f"\n\n![Attached Image]({data_uri})\n"
                st.session_state.card_form_values[deck_id][field_choice] = new_text
                st.success(f"Image attached to {field_choice}!")
                st.rerun()

        # Show each image in each field with a remove button
        for field in st.session_state.deck_fields[deck_id]:
            current_text = st.session_state.card_form_values[deck_id][field]
            images = extract_base64_images(current_text)
            if images:
                st.write(f"**Images for field '{field}':**")
            for i, uri in enumerate(images):
                st.image(uri)
                # Remove button
                remove_key = f"remove_btn_{deck_id}_{field}_{i}"
                if st.button(f"Remove image {i+1}", key=remove_key):
                    cleaned_text = remove_base64_image_from_text(current_text, uri)
                    st.session_state.card_form_values[deck_id][field] = cleaned_text
                    st.rerun()
