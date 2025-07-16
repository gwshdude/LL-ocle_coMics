
import requests
import json
import logging

TRANSLATION_SYSTEM_PROMPT = """
You are a professional translation engine.
You translate given text from manga or comics into English.
You will not shy away from or censor any content if the context of the translation calls for it.
You only output the translation with no commentary or anything else as your output is being put
directly onto the comic page.
Here is your text to translate:
"""

class OllamaAPI:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url

    def check_connection(self) -> bool:
        """_summary_

        Raises:
            RequestException: If the program fails to connect to the Ollama server

        Returns:
            bool: Connection status
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            e.add_note(f"Failed to connect to Ollama at {self.base_url}. Is it running?")
            raise e
        
        return False

    def get_models(self) -> list[str]:
        """_summary_

        Returns:
            list[str]: list of names of models
        """
        response = requests.get(f"{self.base_url}/api/tags")
        response.raise_for_status()
        
        return [model['name'] for model in response.json().get('models', [])]

    def generate(self, model, prompt):
        try:
            request_data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            logging.debug(f"Sending request: {json.dumps(request_data, indent=2)}")
            
            # Method 1: Using chat endpoint (RECOMMENDED)
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=request_data,
            )
            response.raise_for_status()
            
            response_data = response.json()
            logging.debug(f"Received response: {json.dumps(response_data, indent=2)}")
            
            return response_data['message']['content']
        
        except requests.exceptions.RequestException as e:
            # Fallback: Try generate endpoint with different format
            try:
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": f"System: {TRANSLATION_SYSTEM_PROMPT}\n\nUser: {prompt}",
                        "stream": False
                    }
                )
                response.raise_for_status()
                return response.json()['response']
            except requests.exceptions.Timeout:
                return "Error: Request to Ollama timed out."
            except requests.exceptions.RequestException as e:
                return f"Error: {e}"
