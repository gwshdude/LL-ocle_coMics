
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

        self.thinking_anchor = tk.StringVar(value="think")
        
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
        think_frame = ttk.LabelFrame(main_frame, text="LLM Thinking Block Tag Name (without brackets)")
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

        # System Prompt Configuration
        prompt_frame = ttk.LabelFrame(main_frame, text="System Prompt")
        prompt_frame.pack(fill="x", expand=True, pady=5)

        prompt_buttons_frame = ttk.Frame(prompt_frame)
        prompt_buttons_frame.pack(fill="x", expand=True, padx=5, pady=5)

        change_prompt_button = ttk.Button(prompt_buttons_frame, text="Change", command=self.open_system_prompt_dialog)
        change_prompt_button.pack(side="left", fill="x", expand=True, padx=(0, 5))

        default_prompt_button = ttk.Button(prompt_buttons_frame, text="Default", command=self.reset_to_default_prompt)
        default_prompt_button.pack(side="right", fill="x", expand=True, padx=(5, 0))

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
                translated_html, boxes_processed = self.translate_file(filepath, boxes_processed, total_text_boxes, self.thinking_anchor.get())
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
            boxes_processed_start: int,
            total_text_boxes: int,
            anchor: str | None = "think"
        ) -> tuple[str, int]:
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
        boxes_processed = boxes_processed_start
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

                    # SCORCHED EARTH: Completely clear and rebuild the text box content
                    self.scorched_earth_clear_and_rebuild(box, box_translation)

                    # Add text length class for styling hints
                    text_length = len(box_translation)
                    if text_length > 200:
                        box['class'] = box.get('class', []) + ['long-text']
                    elif text_length > 100:
                        box['class'] = box.get('class', []) + ['medium-text']
                    else:
                        box['class'] = box.get('class', []) + ['short-text']

                    self.update_translation_status(boxes_processed, total_text_boxes, box_translation)
        
        return str(soup.prettify()), boxes_processed

    def save_translated_file(self, translated_html: str, output_filepath: str) -> None:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.write(translated_html)

    def _update_gui(self, func, *args, **kwargs):
        if self.winfo_exists():
            try:
                if kwargs:
                    self.after(0, lambda: func(**kwargs))
                else:
                    self.after(0, func, *args)
            except Exception as e:
                logging.error(f"GUI update failed: {e}")

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
        
        # Enforce minimum width of 130 pixels for better readability
        if width_match:
            current_width = int(width_match.group(1))
            if current_width < 130:
                # Calculate the offset needed to center the wider box
                width_increase = 130 - current_width
                left_offset = width_increase // 2
                
                # Update the data attribute to minimum width
                text_box['data-box-width'] = "130"
                # Update the actual style width to minimum width
                style = re.sub(r'width:\s*\d+', 'width:130', style)
                
                # Update left position to keep the box centered
                if left_match:
                    current_left = int(left_match.group(1))
                    new_left = current_left - left_offset
                    style = re.sub(r'left:\s*\d+', f'left:{new_left}', style)
                    text_box['data-box-left'] = str(new_left)
                
                text_box['style'] = style
                # Use the enforced width for calculations
                width = 130
            else:
                text_box['data-box-width'] = width_match.group(1)
                width = current_width
        
        if height_match:
            text_box['data-box-height'] = height_match.group(1)
        if left_match:
            text_box['data-box-left'] = left_match.group(1)
        if top_match:
            text_box['data-box-top'] = top_match.group(1)
        
        # Calculate aspect ratio for better text fitting
        if width_match and height_match:
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

    def scorched_earth_clear_and_rebuild(self, box, translation):
        """Enhanced text replacement with complete original text removal"""
        try:
            # First, ensure complete removal of all original text content
            self.ensure_complete_text_removal(box)
            
            # Find or create the paragraph element
            p_tag = box.find('p')
            if p_tag:
                # Clear existing content and set new translation
                p_tag.clear()
                p_tag.string = translation
            else:
                # Create new paragraph if none exists - get soup from the document
                soup = box.find_parent('html') or box.find_parent().find_parent()
                if soup:
                    p_tag = soup.new_tag('p')
                    p_tag.string = translation
                    box.append(p_tag)
                else:
                    logging.error("Could not find soup to create new tag")
                
        except Exception as e:
            logging.error(f"Text replacement failed: {e}")
            # Last resort: try to set text directly
            try:
                if hasattr(box, 'string'):
                    box.string = translation
            except:
                logging.error("Complete text replacement failure")

    def ensure_complete_text_removal(self, box):
        """Ensure all original text is completely removed from text box"""
        try:
            # Remove all text nodes that aren't part of the new translation
            for text_node in box.find_all(text=True):
                if text_node.parent != box.find('p'):
                    text_node.extract()
            
            # Remove any nested elements that might contain original text
            for nested_element in box.find_all(['span', 'div', 'text', 'ruby', 'rt', 'rp']):
                if nested_element != box.find('p'):
                    nested_element.extract()
            
            # Clear any data attributes that might contain original text
            if box.has_attr('data-original-text'):
                del box['data-original-text']
            if box.has_attr('title'):
                del box['title']
                
        except Exception as e:
            logging.error(f"Complete text removal failed: {e}")

    def clear_text_box_content(self, box):
        """Completely clear all text content from a text box to ensure no original text remains"""
        # Clear the main paragraph element
        if box.p:
            box.p.clear()
        
        # Also clear any other text elements that might be present
        for element in box.find_all(text=True):
            if element.parent != box.p:  # Don't clear the p tag we just cleared
                element.extract()
        
        # Remove any nested text elements or spans that might contain original text
        for nested_element in box.find_all(['span', 'div', 'text']):
            if nested_element != box.p:
                nested_element.extract()

    def translate_text_box(self, box) -> str:
        original_text = box.p.get_text(separator='\n').strip()
        if original_text:
            try:
                translated_text = self.ollama_api.generate(self.model_name.get(), original_text)
            except Exception as e:
                self._update_gui(messagebox.showerror, "Translation Error", f"An error occurred during translation: {e}")
                return ""
            
        return translated_text

    def open_system_prompt_dialog(self):
        """Open dialog to edit system prompt."""
        dialog = SystemPromptDialog(self, self.ollama_api)
        self.wait_window(dialog)

    def reset_to_default_prompt(self):
        """Reset system prompt to default."""
        if messagebox.askyesno("Reset System Prompt", 
                              "Are you sure you want to reset the system prompt to default? This will permanently remove any custom prompt."):
            if self.ollama_api.reset_to_default_prompt():
                messagebox.showinfo("Success", "System prompt has been reset to default.")
            else:
                messagebox.showerror("Error", "Failed to reset system prompt to default.")


class SystemPromptDialog(tk.Toplevel):
    def __init__(self, parent, ollama_api):
        super().__init__(parent)
        self.ollama_api = ollama_api
        self.result = None
        
        self.title("Edit System Prompt")
        self.geometry("600x400")
        self.resizable(True, True)
        
        # Make dialog modal
        self.transient(parent)
        self.grab_set()
        
        # Center the dialog on parent
        self.geometry(f"+{parent.winfo_rootx() + 50}+{parent.winfo_rooty() + 50}")
        
        self.create_widgets()
        
        # Load current system prompt
        current_prompt = self.ollama_api.get_system_prompt()
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(1.0, current_prompt)
        
        # Focus on text area
        self.text_area.focus_set()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        # Instructions
        instruction_label = ttk.Label(main_frame, 
                                    text="Edit the system prompt that will be sent to the AI model:")
        instruction_label.pack(anchor="w", pady=(0, 10))
        
        # Text area with scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        self.text_area = tk.Text(text_frame, wrap="word", font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=scrollbar.set)
        
        self.text_area.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel)
        cancel_button.pack(side="right", padx=(10, 0))
        
        save_button = ttk.Button(button_frame, text="Save", command=self.save)
        save_button.pack(side="right")

    def save(self):
        """Save the edited system prompt."""
        new_prompt = self.text_area.get(1.0, tk.END).strip()
        
        if not new_prompt:
            messagebox.showerror("Error", "System prompt cannot be empty.")
            return
        
        if self.ollama_api.set_system_prompt(new_prompt):
            messagebox.showinfo("Success", "System prompt has been saved.")
            self.result = "saved"
            self.destroy()
        else:
            messagebox.showerror("Error", "Failed to save system prompt.")

    def cancel(self):
        """Cancel editing and close dialog."""
        self.result = "cancelled"
        self.destroy()
