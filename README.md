# Language Grammar Tutor (LLM Mini Project - PS31)

**Problem statement:** Language learners keep repeating the same grammar mistakes.
This app takes a paragraph, asks an LLM to correct it, and returns the corrected
text plus a list of `(error, correction, rule)` as JSON. Mistakes are highlighted
in the original text, and a chart shows which mistake types repeat most.

**Who it helps:** students learning English and teachers who want quick feedback.

## Features
- Paste a paragraph -> corrected text + structured JSON
- Red highlights for errors, green highlights for fixes
- Table of Error / Correction / Rule / Category
- Level (Beginner-Advanced) and native-language hints
- Session chart of repeated mistake categories
- Works with Gemini Flash or Groq (Llama 3.3 70B)

## How to run
```bash
python -m venv venv
venv\Scripts\activate        # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env       # Mac/Linux: cp .env.example .env  -> paste your key
streamlit run app.py
```
Free keys: Gemini -> https://aistudio.google.com/apikey , Groq -> https://console.groq.com/keys

Run offline tests: `python test_grammar_tutor.py`

## Project structure
- `grammar_tutor.py` - prompt, LLM call, JSON parsing, highlighting (backend)
- `app.py` - Streamlit UI (frontend)
- `test_grammar_tutor.py` - tests that need no API key
- `sample_inputs.txt` - 5+ test paragraphs

## Output format
```json
{
  "corrected_text": "Yesterday I went to the market and bought an apple.",
  "errors": [
    {"error": "go", "correction": "went", "rule": "Use past tense for finished actions.", "category": "Tense"}
  ],
  "tip": "Practise past tense verbs."
}
```

## Screenshots
_Add 1-2 screenshots here._
