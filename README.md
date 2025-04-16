# EduForge

An innovative, integrated AI powered learning platform designed to transform how users engage with educational resources.

---

## Table of Contents

1. [Key Features](#key-features)
2. [Requirements](#requirements)
3. [Setup](#setup)
4. [Usage](#usage)
5. [Troubleshooting](#troubleshooting)

---

## Key Features

1. **Flashcards**

   - Leverage AI to transform data covering software engineering topics from uploaded PDF files, URLs, or text files into highly effective flashcards.

2. **Quiz Questions**

   - To further support your flashcards, enhance your learning with AI-generated quiz questions tailored to any topic of your choice.

3. **Latest Updates**
   - Stay in the loop with our latest features and improvements, ensuring you never miss a new addition!

---

## Requirements

- [Python 3.12+](https://www.python.org/)
- [OpenAI API Key](https://openai.com/api/)

---

## Setup

1. **Clone or download** this repository:

   ```bash
   git clone https://github.com/racodess/eduforge.git
   cd eduforge
   ```

2. **Create** the environment file:

   ```bash
   echo > .env
   ```

3. **Add** the environment variable for your OpenAI API key:

   ```
   OPENAI_API_KEY="xx-xxxxxx..."
   ```

4. **Create and activate** virtual environment:

   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

5. **Install** dependencies:

   ```bash
   pip install setup/requirements.txt
   ```

---

## Usage

1. **Navigate** to the project folder:

   ```bash
   cd /path/to/eduforge
   ```

2. **Activate** virtual environment:

   ```bash
   .\venv\Scripts\activate
   ```

3. **Run**:

   ```bash
   ./run.bat
   ```

   If you run into issues with `./run.bat` you can run directly with:

   ```bash
   streamlit run app/0_Updates.py
   ```

   EduForge should now be running on your localhost port [8501](http://localhost:8501) if available.

---

## Troubleshooting

If you encounter any issues or simply want to provide suggestions, please open an issue on our [github](https://github.com/racodess/eduforge)!
