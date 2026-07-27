from __future__ import annotations
import json, os, re
from typing import Any
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from config import load_settings

class GeminiClient:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.api_key = self.settings.env(self.settings.get('gemini.api_key_env', 'GEMINI_API_KEY'), required=True)
        self.endpoint = self.settings.get('gemini.endpoint', 'https://generativelanguage.googleapis.com').rstrip('/')
        self.model = self.settings.get('gemini.text_model', 'gemini-1.5-pro')

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        url = f"{self.endpoint}/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': temperature, 'responseMimeType': 'application/json'},
        }
        res = requests.post(url, json=payload, timeout=90)
        res.raise_for_status()
        data = res.json()
        parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        text = ''.join(p.get('text', '') for p in parts).strip()
        if not text:
            raise RuntimeError(f'Gemini returned an empty response: {data}')
        return text

    def generate_json(self, prompt: str, temperature: float = 0.7) -> Any:
        text = self.generate_text(prompt, temperature)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'(\{.*\}|\[.*\])', text, re.S)
            if not match:
                raise
            return json.loads(match.group(1))
