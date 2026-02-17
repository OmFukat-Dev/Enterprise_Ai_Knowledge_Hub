import ollama
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from the .env file in the project root
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Ollama client is implicitly local or can be configured via OLLAMA_HOST env var
MODEL = os.getenv("LLM_MODEL", "llama3")

def generate_answer(question: str, context: str) -> str:
    try:
        # Check if Ollama is reachable? Or just try.
        prompt = f"""You are an expert assistant. Answer the question using ONLY the context below.
        If the answer is not in the context, say "I don't know based on the document."

        Context:
        {context}

        Question: {question}
        Answer:"""

        response = ollama.chat(model=MODEL, messages=[
            {
                'role': 'user',
                'content': prompt,
            },
        ])
        return response['message']['content'].strip()
    except Exception as e:
        return f"Error generating answer: {str(e)}\n(Make sure Ollama is installed and running 'ollama serve' and 'ollama pull {MODEL}')"
