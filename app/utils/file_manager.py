# file_manager.py

import os
from typing import List


class FileManager:
    """
    Handles uploading, listing, deleting, and interacting with files in the app's media folder.
    """

    # Maps common file extensions to a broad content type understood by the system.
    EXTENSION_CONTENT_TYPE_MAP = {
        '.txt': 'text',
        '.pdf': 'pdf',
        '.json': 'json',
        '.png': 'image',
        '.jpg': 'image',
        '.jpeg': 'image',
        '.gif': 'image',
        '.bmp': 'image',
    }

    def __init__(self) -> None:
        """
        Initialize the FileManager with a media directory and allowed file extensions.
        The media directory is forced to be two levels up from this file's directory,
        in a folder named "media".

        Args:
            media_dir (str): Provided directory path (ignored).
            allowed_extensions (List[str]): List of allowed file extensions, e.g. [".jpg", ".png"].
        """
        # Override any provided media_dir with the path two directories up relative to this file.
        self.media_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "media")
        self.allowed_extensions = list(FileManager.EXTENSION_CONTENT_TYPE_MAP.keys())

        # Create the media directory if it does not exist.
        if not os.path.exists(self.media_dir):
            os.makedirs(self.media_dir)

        # Create the media directory if it does not exist.
        if not os.path.exists(self.media_dir):
            os.makedirs(self.media_dir)

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
        Checks if a file's extension is allowed.
        """
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        return ext in self.allowed_extensions

    def save_file(self, file_obj, filename: str) -> bool:
        """
        Saves the uploaded file to the media folder, if allowed.
        Returns True if saved, False otherwise.
        """
        if not self.is_extension_allowed(filename):
            return False

        destination_path = os.path.join(self.media_dir, filename)
        with open(destination_path, "wb") as f:
            f.write(file_obj.getbuffer())  # file_obj is a Streamlit UploadedFile
        return True

    def delete_file(self, filename: str) -> None:
        """
        Deletes a file from the media folder if it exists.
        """
        file_path = os.path.join(self.media_dir, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
