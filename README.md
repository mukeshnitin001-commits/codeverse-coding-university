# ⚡ CodeVerse — Learn to Code, Step by Step

A coding-learning web app with roles:

## Features
- 🎓 Guided step-by-step Python lessons
- 🧠 **Explain My Code** — paste any code, get a friendly line-by-line AI explanation
- 🔁 **Two Styles** — see two different ways to write the same solution
- 🛡️ **Admin panel** — manage users (change roles, delete), lessons (create/edit/delete), and view stats

## Roles
- **User** (student): lessons, progress tracking, explain-my-code, two-styles
- **Admin**: everything above + full user & content management


## Setup (local)
```bash
pip install -r requirements.txt
python app.py
```
App runs at http://localhost:5000

## AI engine
- Uses a free, OpenAI-compatible model (Groq / Llama) when a `GROQ_API_KEY` env var is set.
- Falls back to a built-in rule-based explainer when no key is present, so it always works.
- Set env vars: `GROQ_API_KEY`, `GROQ_MODEL` (default `llama-3.3-70b-versatile`).

## Deploy
Hosted on Vercel (see `vercel.json`).
