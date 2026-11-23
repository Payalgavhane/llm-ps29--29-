"""Backend logic for the Language Grammar Tutor.

Flow: paragraph -> build prompt -> call LLM (Gemini or Groq) -> parse JSON
      -> corrected text + list of {error, correction, rule, category}.
"""
import html
import json
import re
import time
from collections import Counter

import requests

PROVIDERS = {
    "Gemini": {"model": "gemini-flash-latest", "env": "GEMINI_API_KEY"},
    "Groq": {"model": "llama-3.3-70b-versatile", "env": "GROQ_API_KEY"},
}

SYSTEM_PROMPT = """You are a patient English grammar tutor for language learners.
You will receive one paragraph written by a learner. Do the following:
1. Correct every grammar, spelling, punctuation and word-choice mistake.
   Keep the learner's meaning and voice; do not rewrite correct sentences.
2. List each mistake separately.
3. For each mistake give: the exact wrong text copied character-for-character
   from the paragraph ("error"), the fixed text ("correction"), a short,
   simple grammar rule explaining why ("rule"), and a category.
   Category must be one of: Tense, Subject-Verb Agreement, Article, Preposition,
   Plural/Singular, Word Choice, Spelling, Punctuation, Word Order, Other.
4. Give one short, encouraging "tip" about the learner's most repeated mistake.

Return ONLY valid JSON (no markdown, no commentary) in exactly this shape:
{
  "corrected_text": "<full corrected paragraph>",
  "errors": [
    {"error": "...", "correction": "...", "rule": "...", "category": "..."}
  ],
  "tip": "..."
}
If the paragraph has no mistakes, return the same text and "errors": [].
Explain rules in simple words suitable for the learner's level."""


FALLBACK_MODELS = {
    "Gemini": ["gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-flash-lite-latest"],
    "Groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
}


class GrammarTutorError(Exception):
    """Raised for any problem calling the LLM or reading its answer."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def build_user_prompt(paragraph: str, level: str = "Intermediate",
                      native_language: str = "") -> str:
    prompt = f"Learner level: {level}.\n"
    if native_language.strip():
        prompt += (f"Learner's native language: {native_language.strip()} "
                   "(keep this in mind for typical mistakes).\n")
    prompt += f"\nParagraph:\n\"\"\"\n{paragraph.strip()}\n\"\"\""
    return prompt


def call_llm(system_prompt: str, user_prompt: str, provider: str,
             api_key: str, model: str | None = None, timeout: int = 60) -> str:
    if not api_key:
        raise GrammarTutorError("API key is missing. Add it in the sidebar or .env file.")
    model = model or PROVIDERS[provider]["model"]
    try:
        if provider == "Gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            body = {
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": 0.2,
                                     "responseMimeType": "application/json"},
            }
            r = requests.post(url, json=body, timeout=timeout,
                              headers={"x-goog-api-key": api_key})
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        if provider == "Groq":
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "temperature": 0.2,
                      "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": system_prompt},
                                   {"role": "user", "content": user_prompt}]},
                timeout=timeout)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        raise GrammarTutorError(f"Unknown provider: {provider}")
    except requests.HTTPError as e:
        code = e.response.status_code
        hint = {400: "Bad request / invalid key.", 401: "Invalid API key.",
                403: "API key not allowed.", 404: "Model name not found.",
                429: "Rate limit hit - wait a minute and retry.",
                503: "Server busy - try again in a few seconds."}.get(code, "")
        raise GrammarTutorError(f"API error {code}. {hint}", status=code) from e
    except requests.RequestException as e:
        raise GrammarTutorError(f"Network problem: {e}") from e
    except (KeyError, IndexError, ValueError) as e:
        raise GrammarTutorError("Unexpected response format from the API.") from e


def parse_response(raw: str) -> dict:
    """Turn the model's text into a clean dict, even if it adds ``` fences."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise GrammarTutorError("Model did not return JSON. Try again.")
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise GrammarTutorError("Model returned broken JSON. Try again.") from e

    errors = []
    for item in data.get("errors", []) or []:
        if not isinstance(item, dict):
            continue
        errors.append({
            "error": str(item.get("error", "")).strip(),
            "correction": str(item.get("correction", "")).strip(),
            "rule": str(item.get("rule", "")).strip(),
            "category": str(item.get("category", "Other")).strip() or "Other",
        })
    return {"corrected_text": str(data.get("corrected_text", "")).strip(),
            "errors": errors, "tip": str(data.get("tip", "")).strip()}


def call_with_fallback(system_prompt, user_prompt, provider, api_key, model=None,
                       retries=3):
    """Retry on 429/503 and move to another model on 404/503 so the app rarely fails."""
    models = ([model] if model else []) + [m for m in FALLBACK_MODELS[provider] if m != model]
    last = None
    for m in models:
        for attempt in range(retries):
            try:
                return call_llm(system_prompt, user_prompt, provider, api_key, m)
            except GrammarTutorError as e:
                last = e
                if e.status in (429, 503) and attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))      # wait 2s, then 4s
                    continue
                break                                   # try the next model
        if last is not None and last.status in (400, 401, 403, None):
            raise last                                  # bad key / network: no point retrying
    raise last


def correct_paragraph(paragraph: str, provider: str, api_key: str,
                      level: str = "Intermediate", native_language: str = "",
                      model: str | None = None) -> dict:
    if not paragraph or not paragraph.strip():
        raise GrammarTutorError("Please paste a paragraph first.")
    if len(paragraph) > 3000:
        raise GrammarTutorError("Paragraph is too long (max 3000 characters).")
    raw = call_with_fallback(SYSTEM_PROMPT, build_user_prompt(paragraph, level, native_language),
                             provider, api_key, model)
    result = parse_response(raw)
    if not result["corrected_text"]:
        raise GrammarTutorError("Model returned no corrected text. Try again.")
    return result


def highlight(text: str, phrases: list[str], bg: str, fg: str) -> str:
    """Return HTML of `text` with each phrase wrapped in a coloured <mark>."""
    spans = []
    for p in phrases:
        if not p:
            continue
        for m in re.finditer(re.escape(p), text, flags=re.I):
            s, e = m.span()
            if all(e <= a or s >= b for a, b in spans):   # skip overlaps
                spans.append((s, e))
                break
    spans.sort()
    out, pos = [], 0
    for s, e in spans:
        out.append(html.escape(text[pos:s]))
        out.append(f'<mark style="background:{bg};color:{fg};padding:1px 4px;'
                   f'border-radius:4px;">{html.escape(text[s:e])}</mark>')
        pos = e
    out.append(html.escape(text[pos:]))
    return "".join(out).replace("\n", "<br>")


def tally_categories(errors: list[dict]) -> Counter:
    return Counter(e["category"] for e in errors)
