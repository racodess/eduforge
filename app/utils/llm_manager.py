# llm_manager.py

import openai

class LLMHelper:
    """
    A helper class for interacting with the OpenAI API
    to rewrite text, generate flashcards, etc.
    """

    def __init__(self, model_text="gpt-3.5-turbo", model_image="gpt-3.5-turbo"):
        self.model_text = model_text
        self.model_image = model_image

    def rewrite_text(self, input_text: str) -> str:
        """
        Rewrites input text for clarity.
        """
        if not input_text.strip():
            return ""
        prompt = (
            "Please rewrite the following text so that it is clearer and more concise:\n\n"
            f"Original text:\n{input_text}\n\n"
            "Rewritten text (direct, concise, and well-structured):\n"
        )
        response = self._call_openai(prompt, run_as_image=False)
        return response

    def generate_concept_flashcards(self, input_text: str, run_as_image=False) -> list:
        """
        Generates flashcards (Q&A style) from the input text.
        """
        if not input_text.strip():
            return []

        prompt = (
            "You are an assistant that creates concise question-and-answer flashcards "
            "to study key concepts from the content below.\n\n"
            "Please generate a set of flashcards in the form:\n"
            "Front: <question>\nBack: <answer>\n\n"
            f"CONTENT START\n{input_text}\nCONTENT END\n\n"
            "Return them in a plain-text, bullet-style or numbered list. "
            "Each flashcard is separated by a blank line."
        )
        response = self._call_openai(prompt, run_as_image=run_as_image)

        # Naively parse the response into flashcards
        cards = []
        chunks = [chunk.strip() for chunk in response.split("\n\n") if chunk.strip()]
        for chunk in chunks:
            lines = chunk.splitlines()
            front_line = ""
            back_line = ""
            for line in lines:
                if line.lower().startswith("front:"):
                    front_line = line.split(":", 1)[-1].strip()
                elif line.lower().startswith("back:"):
                    back_line = line.split(":", 1)[-1].strip()
            if front_line and back_line:
                cards.append({"front": front_line, "back": back_line})
        return cards

    def _call_openai(self, prompt: str, run_as_image: bool) -> str:
        """
        Internal method to call the OpenAI API.
        """
        model = self.model_image if run_as_image else self.model_text
        try:
            completion = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1200,
                temperature=0.7
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            return f"Error calling OpenAI: {str(e)}"
