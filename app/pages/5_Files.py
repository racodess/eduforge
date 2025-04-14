import streamlit as st

from utils.file_manager import FileManager

def main():
    st.title("File Manager")
    st.write(
        "Use this page to upload files (PDF, TXT, images) that can be used in AI-related features."
    )

    file_manager = FileManager()

    # --- Existing File Dropdown Selection ---
    st.subheader("Select Existing File")
    existing_files = file_manager.get_all_files()
    if existing_files:
        selected_file = st.selectbox("Choose an existing file from media", options=existing_files)
        st.write(f"Selected file: {selected_file}")
    else:
        st.info("No existing files in media folder.")

    # ---- File Uploader ----
    st.subheader("Upload a new file")
    uploaded_file = st.file_uploader("Choose a file", type=["pdf", "txt", "png", "jpg", "jpeg", "gif"])
    if uploaded_file is not None:
        filename = uploaded_file.name
        if st.button("Upload", use_container_width=True):
            success = file_manager.save_file(uploaded_file, filename)
            if success:
                st.success(f"File '{filename}' uploaded successfully!")
            else:
                st.error("Unsupported file type or error saving file.")
            st.rerun()  # Use rerun to refresh the page

    st.markdown("---")

    # ---- List existing files ----
    st.subheader("My Files")
    file_list = file_manager.get_all_files()
    if not file_list:
        st.info("No files found in the media folder.")
    else:
        for f in file_list:
            col1, col2 = st.columns([0.8, 0.2])
            col1.write(f"**{f}**")
            if col2.button("Delete", key=f"del_{f}", use_container_width=True):
                file_manager.delete_file(f)
                st.warning(f"File '{f}' has been deleted.")
                st.rerun()

if __name__ == "__main__":
    main()
