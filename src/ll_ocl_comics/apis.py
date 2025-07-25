
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

    def get_model_info(self, model_name: str) -> dict:
        """Get detailed information about a specific model including context length.
        
        Args:
            model_name (str): Name of the model to get info for
            
        Returns:
            dict: Model information from Ollama
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/show",
                json={"name": model_name},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.warning(f"Could not get model info for {model_name}: {e}")
            return {}

    def get_model_max_context(self, model_name: str) -> int:
        """Get the maximum context length supported by a model.
        
        Args:
            model_name (str): Name of the model
            
        Returns:
            int: Maximum context length in tokens
        """
        try:
            model_info = self.get_model_info(model_name)
            
            # Try to extract context length from different possible locations
            # Check parameters first
            if 'parameters' in model_info:
                params = model_info['parameters']
                if 'num_ctx' in params:
                    return int(params['num_ctx'])
            
            # Check modelfile content for num_ctx parameter
            if 'modelfile' in model_info:
                modelfile = model_info['modelfile']
                import re
                ctx_match = re.search(r'PARAMETER\s+num_ctx\s+(\d+)', modelfile, re.IGNORECASE)
                if ctx_match:
                    return int(ctx_match.group(1))
            
            # Check details section
            if 'details' in model_info:
                details = model_info['details']
                if 'parameter_size' in details:
                    # Estimate based on parameter size - this is a rough heuristic
                    param_size = details['parameter_size']
                    if '70B' in param_size or '65B' in param_size:
                        return 32768  # Large models typically support more context
                    elif '13B' in param_size or '7B' in param_size:
                        return 8192   # Medium models
                    else:
                        return 4096   # Smaller models
            
            # Default fallback for unknown models
            logging.info(f"Could not determine context length for {model_name}, using default 4096")
            return 4096
            
        except Exception as e:
            logging.warning(f"Error getting context length for {model_name}: {e}")
            return 4096  # Safe default

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

    def load_context_length(self):
        """Load context length from config file, or use default if not found."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('context_length', 13000)
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Could not load config file: {e}. Using default context length.")
        
        return 13000

    def save_context_length(self, context_length):
        """Save context length to config file."""
        try:
            config = {}
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                except (json.JSONDecodeError, IOError):
                    config = {}
            
            config['context_length'] = context_length
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            return True
        except IOError as e:
            logging.error(f"Could not save config file: {e}")
            return False

    def load_temperature(self):
        """Load temperature from config file, or use default if not found."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('temperature', 0.7)
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Could not load config file: {e}. Using default temperature.")
        
        return 0.7

    def save_temperature(self, temperature):
        """Save temperature to config file."""
        try:
            config = {}
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                except (json.JSONDecodeError, IOError):
                    config = {}
            
            config['temperature'] = temperature
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            return True
        except IOError as e:
            logging.error(f"Could not save config file: {e}")
            return False
    
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

    def generate(self, model, prompt, context_length=None, temperature=None):
        try:
            request_data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": self.current_system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            
            # Add options if specified
            options = {}
            if context_length and context_length > 0:
                options["num_ctx"] = context_length
                logging.debug(f"Setting context length to {context_length}")
            
            if temperature is not None:
                options["temperature"] = temperature
                logging.debug(f"Setting temperature to {temperature}")
            
            if options:
                request_data["options"] = options
            
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
                fallback_data = {
                    "model": model,
                    "prompt": f"System: {self.current_system_prompt}\n\nUser: {prompt}",
                    "stream": False
                }
                
                # Add options to fallback request too
                options = {}
                if context_length and context_length > 0:
                    options["num_ctx"] = context_length
                
                if temperature is not None:
                    options["temperature"] = temperature
                
                if options:
                    fallback_data["options"] = options
                
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json=fallback_data
                )
                response.raise_for_status()
                return response.json()['response']
            except requests.exceptions.Timeout:
                return "Error: Request to Ollama timed out."
            except requests.exceptions.RequestException as e:
                return f"Error: {e}"
