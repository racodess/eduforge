# flashcards_ai.py
import streamlit as st
import re

class AIFlashcardProcessor:
    """
    Provides advanced AI-based methods for:
      1) Rewriting text for clarity,
      2) Extracting + chunking text from a URL,
      3) Splitting text by headings and chunk sizes,
      4) Generating question-answer style flashcards from text.

    This version removes references to PDF/image fields and Anki,
    focusing on pure text input/output in markdown.
    """

    def __init__(self):
        # You can load any API keys, config, or additional prompts here
        self.max_chunk_tokens = 800  # Example: keep each chunk fairly small
        self.min_chunk_tokens = 200  # Example: merge smaller sections

    def rewrite_text(self, text: str) -> str:
        """
        (Optional) Example that calls an LLM to "rewrite or clarify" the text.
        In this stub, we simply return text unchanged. 
        Replace with your openai.ChatCompletion call if desired.
        """
        # -- Pseudo-code to call LLM:
        # messages = [
        #     {"role": "system", "content": "Rewrite the following text for clarity..."},
        #     {"role": "user", "content": text},
        # ]
        # response = openai.ChatCompletion.create(model="gpt-4", messages=messages)
        # rewritten = response['choices'][0]['message']['content']
        # return rewritten
        return text

    def scrape_url_to_text(self, url: str) -> str:
        """
        Fetches a URL and converts it to plain text (or markdown).
        In a real app, you'd do an HTTP GET and use a library like trafilatura/BeautifulSoup.
        Here we do a simple placeholder. 
        """
        # -- For example:
        # response = requests.get(url)
        # html_content = response.text
        # text_content = <convert HTML -> text or markdown>
        # return text_content
        return f"Simulated text content fetched from {url}"

    def _extract_markdown_sections(self, markdown_text: str):
        """
        Splits markdown text by heading lines (#, ##, ###, etc.).
        Returns a list of { 'title': heading, 'content': textUntilNextHeading }.
        """
        heading_regex = re.compile(r'^(#{1,6})\s+(.*)$', re.MULTILINE)
        lines = markdown_text.splitlines()

        sections = []
        current_title = None
        current_content = []

        for line in lines:
            match = heading_regex.match(line)
            if match:
                # new heading found -> close off previous section
                if current_title is not None:
                    sections.append({
                        "title": current_title.strip(),
                        "content": "\n".join(current_content).strip()
                    })
                current_title = match.group(2)  # The heading text
                current_content = []
            else:
                current_content.append(line)

        if current_title is not None:
            sections.append({
                "title": current_title.strip(),
                "content": "\n".join(current_content).strip()
            })

        # If no headings found, treat entire text as one "section"
        if not sections:
            sections = [{"title": "Untitled", "content": markdown_text}]

        return sections

    def _count_tokens(self, text: str) -> int:
        """
        Rough placeholder for counting tokens. 
        If you integrate tiktoken or your own logic, do that here.
        """
        # e.g. naive: 1 token ~ 4-5 words
        return len(text.split()) // 0.75  # pretend each "word" is 0.75 tokens

    def _chunk_text(self, sections):
        """
        Example chunking logic: merges small sections to avoid
        many tiny calls, and keeps big sections separate.
        """
        merged = []
        buffer_title = []
        buffer_content = []
        buffer_token_count = 0

        def flush():
            if buffer_title or buffer_content:
                merged.append({
                    "title": "; ".join(buffer_title),
                    "content": "\n".join(buffer_content)
                })

        for sec in sections:
            sec_title = sec["title"]
            sec_content = sec["content"]
            sec_tokens = self._count_tokens(sec_content)

            # If this section is large, handle it alone:
            if sec_tokens >= self.min_chunk_tokens:
                # flush buffer first
                flush()
                buffer_title = []
                buffer_content = []
                buffer_token_count = 0
                # Then add this large chunk by itself
                merged.append(sec)
            else:
                # Merge it into the buffer if we can
                if (buffer_token_count + sec_tokens) <= self.max_chunk_tokens:
                    buffer_title.append(sec_title)
                    buffer_content.append(sec_content)
                    buffer_token_count += sec_tokens
                else:
                    # flush existing
                    flush()
                    buffer_title = [sec_title]
                    buffer_content = [sec_content]
                    buffer_token_count = sec_tokens

        # flush remainder
        flush()

        return merged

    def _generate_qa_pairs(self, text_chunk: str) -> list:
        """
        Calls an LLM to produce question/answer flashcards from the chunk.
        This sample just returns a dummy Q&A. 
        Replace with your real LLM logic that examines `text_chunk`.
        """
        # -- Pseudo-code:
        # prompt = f"Generate Q&A pairs from this text:\n{text_chunk}"
        # response = openai.ChatCompletion.create(...)
        # parse JSON from response
        # or if it's purely text, parse out front/back
        # return list_of_qa (dictionaries)
        
        # For demonstration, we return a single Q&A from each chunk:
        return [{"front": f"Q about: {text_chunk[:40]} ...", "back": "A. This is a sample answer."}]

    def generate_ai_flashcards(self, raw_text: str) -> list:
        """
        High-level method that:
          1) Rewrites text (optional),
          2) Splits by headings,
          3) Merges small sections,
          4) For each chunk, calls an LLM to produce Q&A pairs.

        Returns a list of dictionaries: [{"front": "...", "back": "..."}, ...]
        """
        # 1) rewrite if you want 
        rewritten = self.rewrite_text(raw_text)

        # 2) extract sections by headings
        sections = self._extract_markdown_sections(rewritten)

        # 3) chunk/merge small sections
        chunked = self._chunk_text(sections)

        # 4) gather Q&A from each chunk
        all_cards = []
        for chunk in chunked:
            qa_list = self._generate_qa_pairs(chunk["content"])
            all_cards.extend(qa_list)

        return all_cards


class AIFlashcardImporter:
    """
    This class was originally a stub for handling AI-powered flashcard imports.
    We now integrate it with AIFlashcardProcessor for rewriting text,
    chunking, and generating Q&A pairs from the user’s content.
    """

    def __init__(self):
        self.processor = AIFlashcardProcessor()

    def process_file(self, uploaded_file) -> str:
        """
        Reads the uploaded file and returns its contents as a string.
        For now, we assume it's a .txt file. 
        """
        try:
            content_bytes = uploaded_file.getvalue()
            return content_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            st.error(f"Error reading file: {e}")
            return ""

    def process_text(self, text: str) -> str:
        """
        Returns the text directly for further AI processing.
        """
        return text

    def process_url(self, url: str) -> str:
        """
        Uses the new logic to fetch or scrape the URL. 
        """
        return self.processor.scrape_url_to_text(url)

    def generate_flashcards(self, final_text: str):
        """
        Actual call to create flashcards from user content.
        This method now invokes AIFlashcardProcessor to do
        chunk-based Q&A generation.
        """
        if not final_text.strip():
            return []

        # Here is where we produce the final Q&A pairs:
        flashcards = self.processor.generate_ai_flashcards(final_text)
        return flashcards

