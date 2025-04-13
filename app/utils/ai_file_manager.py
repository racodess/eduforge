# ai_file_manager.py

import os
import shutil
from typing import List

class AIFileManager:
    """
    Handles uploading, listing, and deleting files in the app's media folder.
    """

    def __init__(self, media_dir: str = "media"):
        self.media_dir = media_dir
        if not os.path.exists(self.media_dir):
            os.makedirs(self.media_dir)

        # Adjust these as needed
        self.allowed_extensions = {"pdf", "txt", "png", "jpg", "jpeg", "gif"}

    def get_all_files(self) -> List[str]:
        """
        Returns a list of all file names in the media folder.
        """
        return [
            f for f in os.listdir(self.media_dir)
            if os.path.isfile(os.path.join(self.media_dir, f))
        ]

    def is_extension_allowed(self, filename: str) -> bool:
        """
        Check if file's extension is in the allowed list.
        """
        ext = filename.split(".")[-1].lower()
        return ext in self.allowed_extensions

    def save_file(self, file_obj, filename: str) -> bool:
        """
        Saves the uploaded file to the media folder, if allowed.
        Returns True if saved, False if extension is not allowed.
        """
        if not self.is_extension_allowed(filename):
            return False

        destination_path = os.path.join(self.media_dir, filename)
        with open(destination_path, "wb") as f:
            f.write(file_obj.getbuffer())  # file_obj is a Streamlit UploadedFile
        return True

    def delete_file(self, filename: str) -> None:
        """
        Deletes the file from the media folder if it exists.
        """
        file_path = os.path.join(self.media_dir, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
