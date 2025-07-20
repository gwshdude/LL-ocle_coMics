
import requests
import json
import logging
import os

# Default system prompt - kept as constant for "Default" button functionality
DEFAULT_TRANSLATION_SYSTEM_PROMPT = """
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
        self.config_file = "mokuro_translator_config.json"
        self.current_system_prompt = self._load_system_prompt()

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

    def _load_system_prompt(self):
        """Load system prompt from config file, or use default if not found."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('system_prompt', DEFAULT_TRANSLATION_SYSTEM_PROMPT)
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Could not load config file: {e}. Using default system prompt.")
        
        return DEFAULT_TRANSLATION_SYSTEM_PROMPT
    
    def _save_system_prompt(self, prompt):
        """Save system prompt to config file."""
        try:
            config = {}
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                except (json.JSONDecodeError, IOError):
                    config = {}
            
            config['system_prompt'] = prompt
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            self.current_system_prompt = prompt
            return True
        except IOError as e:
            logging.error(f"Could not save config file: {e}")
            return False
    
    def get_system_prompt(self):
        """Get the current system prompt."""
        return self.current_system_prompt
    
    def set_system_prompt(self, prompt):
        """Set a new system prompt and save it to config."""
        return self._save_system_prompt(prompt)
    
    def reset_to_default_prompt(self):
        """Reset system prompt to default and remove from config."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Remove system_prompt from config
                if 'system_prompt' in config:
                    del config['system_prompt']
                
                # Save updated config or delete file if empty
                if config:
                    with open(self.config_file, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=2, ensure_ascii=False)
                else:
                    os.remove(self.config_file)
            
            self.current_system_prompt = DEFAULT_TRANSLATION_SYSTEM_PROMPT
            return True
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Could not reset system prompt: {e}")
            return False

    def generate(self, model, prompt):
        try:
            request_data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": self.current_system_prompt},
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
                        "prompt": f"System: {self.current_system_prompt}\n\nUser: {prompt}",
                        "stream": False
                    }
                )
                response.raise_for_status()
                return response.json()['response']
            except requests.exceptions.Timeout:
                return "Error: Request to Ollama timed out."
            except requests.exceptions.RequestException as e:
                return f"Error: {e}"
