import requests
import logging
import json
from typing import Generator
import sys
import os

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src import config

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or config.OLLAMA_BASE_URL
        self.model = model or config.LLM_MODEL_NAME

    def generate(self, prompt: str, stream: bool = False, temperature: float = 0.3, system_prompt: str = None) -> str:
        url = f"{self.base_url}/api/chat"
        
        # Build messages array with optional system prompt
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_ctx": 8192
            }
        }

        try:
            response = requests.post(url, json=payload, stream=stream, timeout=300)
            response.raise_for_status()
            
            if stream:
                # Not implementing stream return for now, just aggregation to keep interface simple
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        body = json.loads(line)
                        if "message" in body:
                            content = body["message"].get("content", "")
                            full_response += content
                        if body.get("done"):
                            break
                return full_response
            else:
                body = response.json()
                return body["message"]["content"]

        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with Ollama: {e}")
            raise Exception(f"Unable to connect to LLM (Ollama): {str(e)}")

    def check_connection(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            return response.status_code == 200
        except:
            return False
