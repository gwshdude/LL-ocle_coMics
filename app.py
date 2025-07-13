import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
from bs4 import BeautifulSoup
import threading
import json
from apis import OllamaAPI

class MokuroTranslator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mokuro Translator")
        self.geometry("400x350")
        self.resizable(False, False)

        self.source_language = tk.StringVar(value="Japanese")
        self.model_name = tk.StringVar()
        
        self.ollama_api = OllamaAPI()
        self.is_translating = False
        self.translation_thread = None

        self.create_widgets()
        self.populate_models()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        if self.is_translating:
            if messagebox.askokcancel("Quit", "Translation in progress. Are you sure you want to quit?"):
                self.destroy()
        else:
            self.destroy()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)

        # Source Language Selection
        lang_frame = ttk.LabelFrame(main_frame, text="Source Language")
        lang_frame.pack(fill="x", expand=True, pady=5)

        lang_menu = ttk.OptionMenu(lang_frame, self.source_language, "Japanese", "Japanese", "Korean", "Thai")
        lang_menu.pack(fill="x", expand=True, padx=5, pady=5)

        # Ollama Model Selection
        model_frame = ttk.LabelFrame(main_frame, text="Ollama Model")
        model_frame.pack(fill="x", expand=True, pady=5)

        self.model_menu = ttk.OptionMenu(model_frame, self.model_name, "Select a model")
        self.model_menu.pack(fill="x", expand=True, padx=5, pady=5)

        # Start Button
        self.start_button = ttk.Button(main_frame, text="Start Translation", command=self.start_translation_thread)
        self.start_button.pack(fill="x", expand=True, pady=10)

        # Progress Bar
        self.progress = ttk.Progressbar(main_frame, orient="horizontal", length=100, mode="determinate")
        self.progress.pack(fill="x", expand=True, pady=5)

        # Status Label
        self.status_label = ttk.Label(main_frame, text="Ready")
        self.status_label.pack(fill="x", expand=True, pady=5)

        self.line_count_label = ttk.Label(main_frame, text="0/0")
        self.line_count_label.pack(fill="x", expand=True, pady=5)

        self.last_translation_label = ttk.Label(main_frame, text="Last Translation: ")
        self.last_translation_label.pack(fill="x", expand=True, pady=5)

    def populate_models(self):
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            self.ollama_api.base_url = f"{config['ollama_host']}:{config['ollama_port']}"
            
            connected, message = self.ollama_api.check_connection()
            if not connected:
                raise Exception(message)

            model_names, error = self.ollama_api.get_models()
            if error:
                raise Exception(error)

            if model_names:
                self.model_name.set(model_names[0])
                menu = self.model_menu["menu"]
                menu.delete(0, "end")
                for name in model_names:
                    menu.add_command(label=name, command=lambda value=name: self.model_name.set(value))
            else:
                self.model_name.set("No models found")
                self.model_menu["menu"].delete(0, "end")
        except FileNotFoundError:
            self.model_name.set("Config file not found")
            messagebox.showerror("Error", "config.json not found. Please create it.")
        except Exception as e:
            self.model_name.set("Error fetching models")
            messagebox.showerror("Error", f"Could not fetch Ollama models: {e}")

    def start_translation_thread(self):
        thread = threading.Thread(target=self.start_translation)
        thread.start()

    def _update_gui(self, func, *args):
        if self.winfo_exists():
            self.after(0, func, *args)

    def start_translation(self):
        self.is_translating = True
        self._update_gui(self.start_button.config, {"state": "disabled"})
        self._update_gui(self.status_label.config, {"text": "Starting translation..."})
        self._update_gui(self.progress.config, {"value": 0})

        try:
            input_dir = "input"
            output_dir = "output"

            if not os.path.exists(input_dir):
                os.makedirs(input_dir)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            files = [f for f in os.listdir(input_dir) if f.endswith(".html")]
            if not files:
                self._update_gui(messagebox.showinfo, "Info", "No .html files found in the 'input' directory.")
                return

            total_text_boxes = 0
            for filename in files:
                with open(os.path.join(input_dir, filename), 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f, 'lxml')
                    total_text_boxes += len(soup.find_all('div', class_='textBox'))

            self._update_gui(self.line_count_label.config, {"text": f"0/{total_text_boxes}"})

            boxes_processed = 0
            for filename in files:
                self._update_gui(self.status_label.config, {"text": f"Translating {filename}..."})
                
                try:
                    boxes_processed = self.translate_file(os.path.join(input_dir, filename), output_dir, boxes_processed, total_text_boxes)
                except Exception as e:
                    self._update_gui(messagebox.showerror, "Error", f"Failed to translate {filename}: {e}")

            self._update_gui(self.progress.config, {"value": 100})
            self._update_gui(self.status_label.config, {"text": "Translation complete."})
            self._update_gui(messagebox.showinfo, "Success", "All pages have been translated.")
        finally:
            self.is_translating = False
            self._update_gui(self.start_button.config, {"state": "normal"})

    def check_balanced_braces(self, js_code):
        """Check if JavaScript code has balanced braces"""
        stack = []
        for char in js_code:
            if char == '{':
                stack.append(char)
            elif char == '}':
                if not stack:
                    return False
                stack.pop()
        return len(stack) == 0

    def remove_init_text_boxes(self, js_code):
        """Safely remove initTextBoxes function"""
        # Look for the function with proper brace matching
        pattern = r'function\s+initTextBoxes\s*\(\)\s*\{'
        match = re.search(pattern, js_code)
        
        if not match:
            return js_code
            
        start_pos = match.start()
        brace_start = match.end() - 1  # Position of opening brace
        
        # Count braces to find the matching closing brace
        brace_count = 1
        pos = brace_start + 1
        
        while pos < len(js_code) and brace_count > 0:
            if js_code[pos] == '{':
                brace_count += 1
            elif js_code[pos] == '}':
                brace_count -= 1
            pos += 1
        
        if brace_count == 0:
            # Found the complete function, remove it
            return js_code[:start_pos] + js_code[pos:]
        
        return js_code  # Could not find complete function

    def replace_update_properties_function(self, js_code):
        """Safely replace updateProperties function"""
        # First, let's find the function start
        function_start = js_code.find('function updateProperties()')
        if function_start == -1:
            return js_code  # Function not found, return unchanged
        
        # Find the opening brace
        brace_start = js_code.find('{', function_start)
        if brace_start == -1:
            return js_code
        
        # Count braces to find the matching closing brace
        brace_count = 1
        pos = brace_start + 1
        
        while pos < len(js_code) and brace_count > 0:
            if js_code[pos] == '{':
                brace_count += 1
            elif js_code[pos] == '}':
                brace_count -= 1
            pos += 1
        
        if brace_count == 0:
            # Found the complete function
            function_end = pos
            
            # Define the replacement function
            update_properties_replacement = '''function updateProperties() {
    if (state.textBoxBorders) {
        r.style.setProperty('--textBoxBorderHoverColor', 'rgba(237, 28, 36, 0.3)');
    } else {
        r.style.setProperty('--textBoxBorderHoverColor', 'rgba(0, 0, 0, 0)');
    }
    pc.contentEditable = state.editableText;
    if (state.displayOCR) {
        r.style.setProperty('--textBoxDisplay', 'initial');
    } else {
        r.style.setProperty('--textBoxDisplay', 'none');
    }
    if (state.fontSize === 'auto') {
        pc.classList.remove('textBoxFontSizeOverride');
    } else {
        r.style.setProperty('--textBoxFontSize', state.fontSize + 'pt');
        pc.classList.add('textBoxFontSizeOverride');
    }
    if (state.eInkMode) {
        document.getElementById('topMenu').classList.add("notransition");
    } else {
        document.getElementById('topMenu').classList.remove("notransition");
    }
    if (state.backgroundColor) {
        r.style.setProperty('--colorBackground', state.backgroundColor)
    }
    // New feature toggles
    if (state.alwaysShowTranslation) {
        pc.classList.add('always-show-translation');
    } else {
        pc.classList.remove('always-show-translation');
    }
    if (state.constrainText) {
        pc.classList.add('constrain-text');
    } else {
        pc.classList.remove('constrain-text');
    }
}'''
            
            # Replace the entire function
            new_js_code = (js_code[:function_start] + 
                          update_properties_replacement + 
                          js_code[function_end:])
            return new_js_code
        
        return js_code  # Could not find complete function

    def add_new_event_listeners(self, js_code):
        """Add new event listeners without removing existing ones"""
        # Find the location after the existing toggleOCRTextBoxes event listener
        toggle_listener_pattern = r"(document\.getElementById\('menuToggleOCRTextBoxes'\)\.addEventListener\('click',\s*function\s*\(\)\s*\{[^}]*\}\s*,\s*false\);)"
        
        new_listeners = '''

document.getElementById('menuAlwaysShowTranslation').addEventListener('click', function () {
    state.alwaysShowTranslation = document.getElementById("menuAlwaysShowTranslation").checked;
    saveState();
    updateProperties();
}, false);

document.getElementById('menuConstrainText').addEventListener('click', function () {
    state.constrainText = document.getElementById("menuConstrainText").checked;
    saveState();
    updateProperties();
}, false);'''
        
        return re.sub(toggle_listener_pattern, r'\1' + new_listeners, js_code)

    def translate_file(self, file_path, output_dir, boxes_processed, total_text_boxes):
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'lxml')

        # Part 1: CSS Modifications
        style_tag = soup.find('style')
        if style_tag:
            css = style_tag.string or ''
            
            # Add new feature styles
            css += """

/* Always show translation feature */
.always-show-translation .textBox p { 
    display: table !important; 
    background-color: rgb(255, 255, 255);
}

/* Constrain text feature */
.constrain-text .textBox p { 
    max-width: 100%; 
    overflow: hidden; 
    text-overflow: ellipsis;
    word-wrap: break-word;
    white-space: normal;
}
"""
            style_tag.string = css

        # Part 2: HTML Modifications - Add new menu options
        dropdown_content = soup.find('div', class_='dropdown-content')
        if dropdown_content:
            # Find the toggle OCR text boxes option to insert after it
            toggle_ocr_input = soup.find('input', id='menuToggleOCRTextBoxes')
            if toggle_ocr_input:
                toggle_ocr_label = toggle_ocr_input.parent
                
                # Add "Always show translation" option
                always_show_label = soup.new_tag('label', **{'class': 'dropdown-option'})
                always_show_label.string = 'Always show translation'
                always_show_input = soup.new_tag('input', type='checkbox', id='menuAlwaysShowTranslation')
                always_show_label.append(always_show_input)
                
                # Add "Constrain text" option  
                constrain_label = soup.new_tag('label', **{'class': 'dropdown-option'})
                constrain_label.string = 'Constrain text'
                constrain_input = soup.new_tag('input', type='checkbox', id='menuConstrainText')
                constrain_label.append(constrain_input)
                
                # Insert after existing toggle OCR option
                toggle_ocr_label.insert_after(always_show_label)
                always_show_label.insert_after(constrain_label)

        # Part 3: JavaScript Modifications
        script_tag = soup.find_all('script')[-1]
        if script_tag and script_tag.string:
            js_code = script_tag.string
            original_js_length = len(js_code)

            # Update defaultState - Add new properties without removing existing ones
            js_code = re.sub(r'(toggleOCRTextBoxes\s*:\s*false,)',
                             r'\1\n    alwaysShowTranslation: false,\n    constrainText: false,', js_code)

            # Update updateUI - Add new checkbox updates
            js_code = re.sub(r"(document\.getElementById\('menuToggleOCRTextBoxes'\)\.checked = state\.toggleOCRTextBoxes;)",
                             r'\1\n    document.getElementById("menuAlwaysShowTranslation").checked = state.alwaysShowTranslation;\n    document.getElementById("menuConstrainText").checked = state.constrainText;', js_code)

            # Remove initTextBoxes and its call using safe method
            js_code = self.remove_init_text_boxes(js_code)
            js_code = js_code.replace('initTextBoxes();', '')

            # Add new event listeners using safe method
            js_code = self.add_new_event_listeners(js_code)
            
            # Replace updateProperties function using safe method
            js_code = self.replace_update_properties_function(js_code)

            # Fix updatePage to show pages
            js_code = js_code.replace(
                'getPage(state.page_idx).style.display = "none";',
                '// getPage(state.page_idx).style.display = "none";'
            )
            
            # Validate JavaScript syntax
            if not self.check_balanced_braces(js_code):
                self._update_gui(messagebox.showerror, "JavaScript Error", 
                               f"Unbalanced braces detected in JavaScript for {os.path.basename(file_path)}. "
                               f"Original length: {original_js_length}, New length: {len(js_code)}")
                # Write debug file
                with open(f'debug_js_{os.path.basename(file_path)}.js', 'w', encoding='utf-8') as f:
                    f.write(js_code)
            
            script_tag.string = js_code

        # Part 4: Translation and Finalization
        page_containers = soup.find_all('div', class_='pageContainer')
        for container in page_containers:
            text_boxes = container.find_all('div', class_='textBox')
            for box in text_boxes:
                if box.has_attr('style') and 'writing-mode' in box['style']:
                    style_attr = box['style']
                    new_style = re.sub(r'writing-mode\s*:\s*vertical-rl\s*;?', '', style_attr).strip()
                    box['style'] = new_style
                if box.p:
                    original_text = box.p.get_text(separator='\n').strip()
                    if original_text:
                        try:
                            translated_text = self.ollama_api.generate(self.model_name.get(), original_text)
                            box.p.string = translated_text
                            boxes_processed += 1
                            progress_percentage = (boxes_processed / total_text_boxes) * 100
                            self._update_gui(self.progress.config, {"value": progress_percentage})
                            self._update_gui(self.line_count_label.config, {"text": f"{boxes_processed}/{total_text_boxes}"})
                            self._update_gui(self.last_translation_label.config, {"text": f"Last: {translated_text[:50]}..."})
                        except Exception as e:
                            self._update_gui(messagebox.showerror, "Translation Error", f"An error occurred during translation: {e}")
                            continue
        
        output_filename = os.path.join(output_dir, os.path.basename(file_path))
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(str(soup.prettify()))
            
        return boxes_processed

if __name__ == "__main__":
    app = MokuroTranslator()
    app.mainloop()
