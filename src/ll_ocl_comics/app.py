
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import re
from bs4 import BeautifulSoup
import threading

from apis import OllamaAPI
from mokuro_changes import (
    PROPERTIES_JS_FUNC, LISTENER_JS_FUNC,
    ALWAYS_SHOW_TRANSLATION_JS_FUNC, UPDATE_PAGE_JS_ORIGINAL,
    UPDATE_PAGE_JS_FUNC,
)
from helpers import remove_between_anchors

# Languages to translate from
SOURCE_LANGUAGES = [
    "Japanese", "Korean", "Thai",
]

class MokuroTranslator(tk.Tk):
    def __init__(self, ollama_base_url: str = "http://localhost:11434"):
        """_summary_

        Args:
            ollama_base_url (str, optional): The base URL for all ollama requests.
                Should include a port. Defaults to "http://localhost:11434".
        """
        super().__init__()
        self.title("Mokuro Translator")
        self.resizable(True, True)

        self.source_language = tk.StringVar(value=SOURCE_LANGUAGES[0])
        self.model_name = tk.StringVar()

        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()

        self.thinking_anchor = tk.StringVar(value="<think>")
        
        self.ollama_api = OllamaAPI()
        self.ollama_base_url = ollama_base_url

        self.is_translating = threading.Lock()
        self.translation_thread = None

        self.create_widgets()

        # populate LLMs
        try:
            self.populate_models()
        except Exception as e:
            self.model_name.set("Error fetching models")
            messagebox.showerror("Error", f"Could not fetch Ollama models: {e}")
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        if self.is_translating.locked():
            if messagebox.askokcancel("Quit", "Translation in progress. Are you sure you want to quit?"):
                self.is_translating.release()
                self.destroy()
        else:
            self.destroy()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)

        # Source Language Selection
        lang_frame = ttk.LabelFrame(main_frame, text="Source Language")
        lang_frame.pack(fill="x", expand=True, pady=5)

        lang_menu = ttk.OptionMenu(lang_frame, self.source_language, *SOURCE_LANGUAGES)
        lang_menu.pack(fill="x", expand=True, padx=5, pady=5)

        # Ollama Model Selection
        model_frame = ttk.LabelFrame(main_frame, text="Ollama Model")
        model_frame.pack(fill="x", expand=True, pady=5)

        self.model_menu = ttk.OptionMenu(model_frame, self.model_name, "Select a model")
        self.model_menu.pack(fill="x", expand=True, padx=5, pady=5)

        # Thinking block option
        think_frame = ttk.LabelFrame(main_frame, text="LLM Thinking Block Indicator")
        think_frame.pack(fill="x", expand=True, pady=5)

        think_entry = ttk.Entry(think_frame, width=20, textvariable=self.thinking_anchor)
        think_entry.pack(fill="x", expand=True, pady=10)

        # Input directory
        in_dir_frame = ttk.LabelFrame(main_frame, text="Input Directory")
        in_dir_frame.pack(fill="x", expand=True, pady=5)

        in_dir_button = ttk.Button(in_dir_frame, text="Select Input Directory", command=self.set_input_dir)
        in_dir_button.pack(fill="x", expand=True, pady=10)

        # Output directory
        out_dir_frame = ttk.LabelFrame(main_frame, text="Output Directory")
        out_dir_frame.pack(fill="x", expand=True, pady=5)

        out_dir_button = ttk.Button(out_dir_frame, text="Select Output Directory", command=self.set_output_dir)
        out_dir_button.pack(fill="x", expand=True, pady=10)

        # Start Button
        self.start_button = ttk.Button(main_frame, text="Start Translation", command=self.start_translation_helper)
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

    def populate_models(self) -> None:
        connected = self.ollama_api.check_connection()
        if not connected:
            raise RuntimeError("Could not connect to Ollama.")
        
        try:
            model_names = self.ollama_api.get_models()
        except Exception as e:
            messagebox.showerror("Error", f"Could not fetch Ollama models: {e}")
            return
        else:
            if not model_names or len(model_names) < 1:
                messagebox.showerror("Error", "Did not fetch any Ollama models.")
                return

        self.model_name.set(model_names[0])
        menu = self.model_menu["menu"]
        menu.delete(0, "end")
        for name in model_names:
            menu.add_command(label=name, command=lambda value=name: self.model_name.set(value))

    def set_input_dir(self) -> os.PathLike:
        self.input_dir.set(filedialog.askdirectory(mustexist=True, title="Select File Input Path", initialdir=self.input_dir.get()))

    def set_output_dir(self) -> os.PathLike:
        self.output_dir.set(filedialog.askdirectory(mustexist=False, title="Select File Output Path", initialdir=self.output_dir.get()))

    def get_html_files(self, input_dir: os.PathLike) -> list[str]:
        return [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith(".html")]

    def count_text_boxes_in_files(self, filenames: list[os.PathLike]) -> int:
        total_text_boxes = 0
        for filename in filenames:
            with open(filename, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'lxml')
                total_text_boxes += len(soup.find_all('div', class_='textBox'))
                
        return total_text_boxes

    def start_translation(
            self,
            filepaths: list[os.PathLike],
            output_dir: os.PathLike,
            total_text_boxes: int | str = "?"
        ):
        # block until lock is available
        self.is_translating.acquire()

        self._update_gui(self.line_count_label.config, {"text": f"0/{total_text_boxes}"})

        boxes_processed = 0
        for filepath in filepaths:
            filename = os.path.basename(filepath)
            self._update_gui(self.status_label.config, {"text": f"Translating {filename}..."})
            try:
                translated_html = self.translate_file(filepath, boxes_processed, total_text_boxes, self.thinking_anchor.get())
            except Exception as e:
                logging.error(e)
                self._update_gui(messagebox.showerror, "Error", f"Failed to translate {filename}: {e}")
            else:
                out_path = os.path.join(output_dir, filename)
                self.save_translated_file(translated_html, out_path)

        self._update_gui(self.progress.config, {"value": 100})
        self._update_gui(self.status_label.config, {"text": "Translation complete."})
        self._update_gui(messagebox.showinfo, "Success", "All pages have been translated.")
        self._update_gui(self.start_button.config, {"state": "normal"})

        self.is_translating.release()

    def start_translation_thread(self, filepaths: os.PathLike, output_dir: os.PathLike, total_text_boxes: int | str = "?"):
        thread = threading.Thread(target=self.start_translation, args=(filepaths, self.output_dir.get(), total_text_boxes))
        thread.start()

    def start_translation_helper(self) -> None:
        self._update_gui(self.start_button.config, {"state": "disabled"})
        self._update_gui(self.status_label.config, {"text": "Starting translation..."})
        self._update_gui(self.progress.config, {"value": 0})

        input_files = self.get_html_files(self.input_dir.get())
        if not input_files:
            self._update_gui(messagebox.showinfo, "Info", f"No .html files found in {self.input_dir.get()}.")
            return
        
        if not os.path.exists(self.output_dir.get()):
            os.makedirs(self.output_dir.get())

        total_text_boxes = self.count_text_boxes_in_files(input_files)

        self.start_translation_thread(input_files, self.output_dir.get(), total_text_boxes)
    
    def update_translation_status(self, boxes_processed: int, total_text_boxes: int, recent_text: str) -> None:
        """Updates the translation status widgets in the GUI.

        Args:
            boxes_processed (int): _description_
            total_text_boxes (int): _description_
            recent_text (str): _description_
        """
        progress_percentage = (boxes_processed / total_text_boxes) * 100
        self._update_gui(self.progress.config, {"value": progress_percentage})
        self._update_gui(self.line_count_label.config, {"text": f"{boxes_processed}/{total_text_boxes}"})
        self._update_gui(self.last_translation_label.config, {"text": f"Last: {recent_text[:50]}..."})

    def translate_file(
            self,
            filepath: os.PathLike,
            boxes_processed: int,
            total_text_boxes: int,
            anchor: str | None = "<think>"
        ) -> str:
        """Returns the translation of all text in a file.

        Args:
            filepath (os.PathLike): _description_
            boxes_processed (int): _description_
            total_text_boxes (int): _description_
            anchor (int | None): If anchor is present in the API response,
                remove all text between the first 2 occurences of anchor.

        Returns:
            str: _description_
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'lxml')

        # Part 1: Enhanced CSS Modifications
        style_tag = soup.find('style')
        if style_tag:
            css = style_tag.string or ''
            
            # Modify default textBox p styles to enable text wrapping by default
            css = css.replace(
                'white-space: nowrap;',
                'white-space: normal;\n    word-wrap: break-word;'
            )
            
            # Add enhanced feature styles
            css += ALWAYS_SHOW_TRANSLATION_JS_FUNC
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
                UPDATE_PAGE_JS_ORIGINAL,
                UPDATE_PAGE_JS_FUNC
            )
            
            # Validate JavaScript syntax
            if not self.check_balanced_braces(js_code):
                self._update_gui(messagebox.showerror, "JavaScript Error", 
                               f"Unbalanced braces detected in JavaScript for {os.path.basename(filepath)}. "
                               f"Original length: {original_js_length}, New length: {len(js_code)}")
                # Write debug file
                with open(f'debug_js_{os.path.basename(filepath)}.js', 'w', encoding='utf-8') as f:
                    f.write(js_code)
            
            script_tag.string = js_code

        # Part 4: Enhanced Text Box Processing and Translation
        page_containers = soup.find_all('div', class_='pageContainer')
        for container in page_containers:
            text_boxes = container.find_all('div', class_='textBox')
            for box in text_boxes:
                # Remove vertical writing mode for better horizontal text display
                if box.has_attr('style') and 'writing-mode' in box['style']:
                    style_attr = box['style']
                    new_style = re.sub(r'writing-mode\s*:\s*vertical-rl\s*;?', '', style_attr).strip()
                    box['style'] = new_style
                
                # Add data attributes for JavaScript processing
                self.enhance_text_box_attributes(box)
                
                # Process text content
                if box.p:
                    box_translation = self.translate_text_box(box)
                    boxes_processed += 1

                    # remove text between "thinking" blocks
                    box_translation = remove_between_anchors(box_translation, anchor)

                    box.p.string = box_translation

                    # Add text length class for styling hints
                    text_length = len(box_translation)
                    if text_length > 200:
                        box['class'] = box.get('class', []) + ['long-text']
                    elif text_length > 100:
                        box['class'] = box.get('class', []) + ['medium-text']
                    else:
                        box['class'] = box.get('class', []) + ['short-text']

                    self.update_translation_status(boxes_processed, total_text_boxes, box_translation)
        
        return str(soup.prettify())

    def save_translated_file(self, translated_html: str, output_filepath: str) -> None:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.write(translated_html)

    def _update_gui(self, func, *args):
        if self.winfo_exists():
            self.after(0, func, *args)

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
        
        if brace_count == 0:    # Found the complete function
            # Replace the entire function
            new_js_code = (js_code[:function_start] + 
                          PROPERTIES_JS_FUNC + 
                          js_code[pos:])
            return new_js_code
        
        return js_code  # Could not find complete function

    def add_new_event_listeners(self, js_code):
        """Add new event listeners without removing existing ones"""
        # Find the location after the existing toggleOCRTextBoxes event listener
        toggle_listener_pattern = r"(document\.getElementById\('menuToggleOCRTextBoxes'\)\.addEventListener\('click',\s*function\s*\(\)\s*\{[^}]*\}\s*,\s*false\);)"
        
        return re.sub(toggle_listener_pattern, r'\1' + LISTENER_JS_FUNC, js_code)

    def enhance_text_box_attributes(self, text_box):
        """Add data attributes to text boxes for JavaScript processing"""
        if not text_box.has_attr('style'):
            return
            
        style = text_box['style']
        
        # Extract dimensions from style attribute
        width_match = re.search(r'width:\s*(\d+)', style)
        height_match = re.search(r'height:\s*(\d+)', style)
        left_match = re.search(r'left:\s*(\d+)', style)
        top_match = re.search(r'top:\s*(\d+)', style)
        
        if width_match:
            text_box['data-box-width'] = width_match.group(1)
        if height_match:
            text_box['data-box-height'] = height_match.group(1)
        if left_match:
            text_box['data-box-left'] = left_match.group(1)
        if top_match:
            text_box['data-box-top'] = top_match.group(1)
        
        # Calculate aspect ratio for better text fitting
        if width_match and height_match:
            width = int(width_match.group(1))
            height = int(height_match.group(1))
            aspect_ratio = width / height if height > 0 else 1
            text_box['data-aspect-ratio'] = f"{aspect_ratio:.2f}"
            
            # Add size category based on area
            area = width * height
            if area > 50000:
                text_box['data-size-category'] = 'large'
            elif area > 10000:
                text_box['data-size-category'] = 'medium'
            else:
                text_box['data-size-category'] = 'small'

    def translate_text_box(self, box) -> str:
        original_text = box.p.get_text(separator='\n').strip()
        if original_text:
            try:
                translated_text = self.ollama_api.generate(self.model_name.get(), original_text)
            except Exception as e:
                self._update_gui(messagebox.showerror, "Translation Error", f"An error occurred during translation: {e}")
                return ""
            
        return translated_text
