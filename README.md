# EduForge

EduForge is an AI-enhanced interactive study platform built using Python and Streamlit, designed to revolutionize the way students organize, review, and master their study materials. Leveraging advanced AI capabilities alongside traditional learning techniques, EduForge offers a personalized, engaging, and efficient learning experience.

---

## 🚀 Features

### Personalized Learning
- AI-driven customized quizzes and spaced-repetition flashcards (SM-2 algorithm).

### Enhanced Engagement
- Interactive notebooks and dynamic flashcard reviews.
- AI-generated content to sustain student interest.

### Efficiency and Organization
- Intuitive management of flashcards and comprehensive notes.
- Structured tracking of progress for systematic studying.

### Accessibility and Convenience
- Cloud-based solution accessible anytime, anywhere.

---

## 📌 Key Components

### 1. Flashcard Management
- Create, edit, organize, and review flashcard decks.
- Spaced-repetition algorithm (SM-2) for optimal memory retention.

### 2. Interactive Notebooks
- Markdown-supported structured note-taking.
- Integrated spaced repetition reviews and graph visualization (via Graphviz).

### 3. AI-Powered Content Generation
- Generate flashcards and detailed notes from texts, URLs, or uploaded files.
- Mind map visualization to connect and simplify complex ideas.

### 4. Dynamic Quiz Module
- Automatically generates quizzes based on selected topics.
- Instant feedback mechanism for immediate learning reinforcement.

---

## 🗂️ Project Structure
```
EduForge
├── .streamlit/              # Streamlit configuration files
├── app/                     # Main application source code
│   ├── utils/               # Backend utilities and AI integration scripts
│   ├── dialogs.py
│   ├── flashcards.py
│   ├── generated_items.py
│   ├── main.py
│   ├── notebooks.py
│   ├── quiz.py
│   └── sidebar.py
├── media/                   # Test files and sample media resources
├── setup/                   # Dependency and environment setup
│   └── requirements.txt
├── ui-theme/                # UI styling assets
│   └── global.css
├── flashcards.db            # SQLite database for flashcards
├── notes.db                 # SQLite database for notes
├── run.bat                  # Execution script for Windows
├── run.sh                   # Execution script for Unix-based systems
├── README.md
├── LICENSE
└── .gitignore
```

---

## ⚙️ Installation

### Prerequisites
- Python 3.12+
- Git
- OpenAI API Key

### Windows 11 (PowerShell)

```powershell
git clone https://github.com/racodess/eduforge.git
cd eduforge

echo OPENAI_API_KEY="your-api-key-here" > .env

python -m venv venv
.\venv\Scripts\activate

pip install -r setup\requirements.txt

.\run.bat
```

App available at [http://localhost:8501](http://localhost:8501).

### Unix-based Systems (Bash)

```bash
git clone https://github.com/racodess/eduforge.git
cd eduforge

echo 'OPENAI_API_KEY="your-api-key-here"' > .env

python -m venv venv
source venv/bin/activate

pip install -r setup/requirements.txt

chmod +x run.sh
./run.sh
```

App available at [http://localhost:8501](http://localhost:8501).

---

## 🛠 Troubleshooting

- **Python Version Issues:** Ensure Python version is 3.12 or higher.
- **Dependency Errors:** Upgrade `pip` and `setuptools` before retrying.
- **Virtual Environment Issues:** Ensure activation scripts are executable.
- **Streamlit Issues:** Verify Streamlit installation and environment paths.
- **Port Issues:** Free port `8501` or run on alternative port:

```bash
streamlit run app/main.py --server.port 8502
```

---

## 📖 Usage Overview

- **Dashboard Page:** Centralized access point with default sample decks and notebooks.
- **Flashcards Page:** Manage flashcard decks and SM-2 algorithm stats.
- **Notebooks Page:** Structured notes management with Graphviz-rendered visualizations.

---

## 📄 License

EduForge is released under the [MIT License](LICENSE).

