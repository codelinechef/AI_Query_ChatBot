import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise EnvironmentError("GEMINI_API_KEY not set in .env")

genai.configure(api_key=api_key)

print("Available models:")
for model in genai.list_models():
    if hasattr(model, "supported_generation_methods") and 'generateContent' in model.supported_generation_methods:
        print(f"- {model.name}")

