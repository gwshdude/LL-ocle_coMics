
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinterdnd2 import DND_FILES, TkinterDnD
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

class MokuroTranslator(TkinterDnD.Tk):
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
        self.context_length = tk.IntVar(value=13000)
        self.temperature = tk.DoubleVar(value=0.7)
        
        # RAG context files storage
        self.rag_files = []  # List of dictionaries with 'path' and 'content' keys
        self.rag_content_cache = ""  # Cached formatted RAG content
        
        self.ollama_api = OllamaAPI()
        self.ollama_base_url = ollama_base_url
        
        # Load saved context length, but only if it exists and is different from default
        saved_context_length = self.ollama_api.load_context_length()
        # Only override the default if a different value was explicitly saved
        if saved_context_length != 13000:
            self.context_length.set(saved_context_length)
        
        # Load saved temperature
        saved_temperature = self.ollama_api.load_temperature()
        self.temperature.set(saved_temperature)

        self.is_translating = threading.Lock()
        self.translation_thread = None

        self.create_widgets()
        
        # Initialize labels with current values
        self.update_context_label()
        self.update_temperature_label()

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

        # Temperature Configuration
        temp_frame = ttk.LabelFrame(main_frame, text="Temperature (creativity)")
        temp_frame.pack(fill="x", expand=True, pady=5)

        self.temp_slider = ttk.Scale(
            temp_frame, 
            from_=0.0, 
            to=2.0,
            orient="horizontal",
            variable=self.temperature,
            command=self.on_temperature_change
        )
        self.temp_slider.pack(fill="x", padx=5, pady=5)

        self.temp_label = ttk.Label(temp_frame, text="Temperature: 0.7")
        self.temp_label.pack(pady=5)

        # Thinking block option
        think_frame = ttk.LabelFrame(main_frame, text="LLM Thinking Block Tag Name (without brackets)")
        think_frame.pack(fill="x", expand=True, pady=5)

        think_entry = ttk.Entry(think_frame, width=20, textvariable=self.thinking_anchor)
        think_entry.pack(fill="x", expand=True, pady=10)

        # Context Length Configuration
        context_frame = ttk.LabelFrame(main_frame, text="Context Length (tokens)")
        context_frame.pack(fill="x", expand=True, pady=5)

        self.context_slider = ttk.Scale(
            context_frame, 
            from_=512, 
            to=32768,  # Hardcoded maximum context length
            orient="horizontal",
            variable=self.context_length,
            command=self.on_context_change
        )
        self.context_slider.pack(fill="x", padx=5, pady=5)

        self.context_label = ttk.Label(context_frame, text="Context: 13000 tokens")
        self.context_label.pack(pady=5)

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

        # Generate Summary Button
        self.summary_button = ttk.Button(main_frame, text="Generate Model Context Summary", command=self.generate_summary_helper)
        self.summary_button.pack(fill="x", expand=True, pady=5)

        # RAG Context Files Section
        rag_frame = ttk.LabelFrame(main_frame, text="RAG Context Files (Drag & Drop)")
        rag_frame.pack(fill="x", expand=True, pady=5)

        # Drop area
        self.rag_drop_area = tk.Frame(rag_frame, bg="lightgray", relief="sunken", bd=2, height=80)
        self.rag_drop_area.pack(fill="x", padx=5, pady=5)
        self.rag_drop_area.pack_propagate(False)

        # Drop area label
        self.rag_drop_label = tk.Label(self.rag_drop_area, text="Drop text files here for RAG context\n(Supports .txt, .md, .json files)", 
                                      bg="lightgray", fg="gray", font=("Arial", 10))
        self.rag_drop_label.pack(expand=True)

        # Configure drag and drop
        self.rag_drop_area.drop_target_register(DND_FILES)
        self.rag_drop_area.dnd_bind('<<Drop>>', self.on_rag_files_dropped)
        self.rag_drop_area.dnd_bind('<<DragEnter>>', self.on_rag_drag_enter)
        self.rag_drop_area.dnd_bind('<<DragLeave>>', self.on_rag_drag_leave)

        # File list and controls
        rag_controls_frame = ttk.Frame(rag_frame)
        rag_controls_frame.pack(fill="x", padx=5, pady=5)

        # File listbox with scrollbar
        rag_list_frame = ttk.Frame(rag_controls_frame)
        rag_list_frame.pack(fill="x", pady=(0, 5))

        self.rag_files_listbox = tk.Listbox(rag_list_frame, height=4, selectmode=tk.EXTENDED)
        rag_scrollbar = ttk.Scrollbar(rag_list_frame, orient="vertical", command=self.rag_files_listbox.yview)
        self.rag_files_listbox.configure(yscrollcommand=rag_scrollbar.set)

        self.rag_files_listbox.pack(side="left", fill="both", expand=True)
        rag_scrollbar.pack(side="right", fill="y")

        # Control buttons
        rag_buttons_frame = ttk.Frame(rag_controls_frame)
        rag_buttons_frame.pack(fill="x")

        self.rag_remove_button = ttk.Button(rag_buttons_frame, text="Remove Selected", command=self.remove_selected_rag_files)
        self.rag_remove_button.pack(side="left", padx=(0, 5))

        self.rag_clear_button = ttk.Button(rag_buttons_frame, text="Clear All", command=self.clear_all_rag_files)
        self.rag_clear_button.pack(side="left", padx=(0, 5))

        # RAG info label
        self.rag_info_label = ttk.Label(rag_controls_frame, text="No RAG files loaded")
        self.rag_info_label.pack(side="right")

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
            menu.add_command(label=name, command=lambda value=name: self.on_model_selection(value))
        
        # Set up initial model context length
        if model_names:
            self.on_model_selection(model_names[0])

    def on_model_selection(self, model_name):
        """Called when model selection changes - set model and context length."""
        self.model_name.set(model_name)
        
        if model_name and model_name != "Select a model":
            # Set to 13,000 tokens (slider max is now hardcoded to 32,768)
            target_context = 13000
            self.context_length.set(target_context)
            self.update_context_label()
            logging.info(f"Model {model_name} selected, context set to: {target_context}")

    def on_context_change(self, value):
        """Called when context length slider changes."""
        context_value = int(float(value))
        self.context_length.set(context_value)
        self.update_context_label()
        
        # Save the context length setting
        self.ollama_api.save_context_length(context_value)

    def update_context_label(self):
        """Update the context length label display."""
        context_value = self.context_length.get()
        self.context_label.config(text=f"Context: {context_value} tokens")

    def on_temperature_change(self, value):
        """Called when temperature slider changes."""
        temp_value = round(float(value), 1)
        self.temperature.set(temp_value)
        self.update_temperature_label()
        
        # Save the temperature setting
        self.ollama_api.save_temperature(temp_value)

    def update_temperature_label(self):
        """Update the temperature label display."""
        temp_value = self.temperature.get()
        self.temp_label.config(text=f"Temperature: {temp_value}")

    def set_input_dir(self) -> os.PathLike:
        self.input_dir.set(filedialog.askdirectory(mustexist=True, title="Select File Input Path", initialdir=self.input_dir.get()))

    def set_output_dir(self) -> os.PathLike:
        self.output_dir.set(filedialog.askdirectory(mustexist=False, title="Select File Output Path", initialdir=self.output_dir.get()))

    def get_html_files(self, input_dir: os.PathLike) -> list[str]:
        return [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith(".html")]

    def count_pages_in_files(self, filenames: list[os.PathLike]) -> int:
        total_pages = 0
        for filename in filenames:
            with open(filename, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'lxml')
                total_pages += len(soup.find_all('div', class_='pageContainer'))
                
        return total_pages

    def start_translation(
            self,
            filepaths: list[os.PathLike],
            output_dir: os.PathLike,
            total_pages: int | str = "?"
        ):
        # block until lock is available
        self.is_translating.acquire()

        self._update_gui(self.line_count_label.config, {"text": f"0/{total_pages}"})

        pages_processed = 0
        global_textbox_counter = 0  # Global counter across all files
        
        for filepath in filepaths:
            filename = os.path.basename(filepath)
            self._update_gui(self.status_label.config, {"text": f"Translating {filename}..."})
            try:
                translated_html, pages_processed, global_textbox_counter = self.translate_file(
                    filepath, pages_processed, total_pages, global_textbox_counter, self.thinking_anchor.get()
                )
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

        total_pages = self.count_pages_in_files(input_files)

        self.start_translation_thread(input_files, self.output_dir.get(), total_pages)
    
    def generate_summary_helper(self) -> None:
        """Helper method to start summary generation in a separate thread."""
        # Validate inputs
        if not self.input_dir.get():
            messagebox.showinfo("Info", "Please select an input directory first.")
            return
        
        if not self.output_dir.get():
            messagebox.showinfo("Info", "Please select an output directory first.")
            return
        
        if not self.model_name.get() or self.model_name.get() == "Select a model":
            messagebox.showinfo("Info", "Please select a model first.")
            return
        
        # Check if already processing
        if self.is_translating.locked():
            messagebox.showinfo("Info", "Translation is in progress. Please wait for it to complete.")
            return
        
        # Disable buttons and start processing
        self._update_gui(self.summary_button.config, {"state": "disabled"})
        self._update_gui(self.start_button.config, {"state": "disabled"})
        self._update_gui(self.status_label.config, {"text": "Generating summary..."})
        self._update_gui(self.progress.config, {"value": 0})
        
        # Start summary generation in background thread
        summary_thread = threading.Thread(target=self.generate_model_context_summary)
        summary_thread.start()
    
    def generate_model_context_summary(self):
        """Generate a comprehensive story summary from all textboxes."""
        try:
            # Get input files
            input_files = self.get_html_files(self.input_dir.get())
            if not input_files:
                self._update_gui(messagebox.showinfo, "Info", f"No .html files found in {self.input_dir.get()}.")
                return
            
            # Ensure output directory exists
            if not os.path.exists(self.output_dir.get()):
                os.makedirs(self.output_dir.get())
            
            # Collect all textboxes from all files
            self._update_gui(self.status_label.config, {"text": "Collecting textboxes..."})
            all_textboxes_data = self.collect_all_textboxes(input_files)
            
            if not all_textboxes_data:
                self._update_gui(messagebox.showinfo, "Info", "No textboxes found in the HTML files.")
                return
            
            # Format the request
            self._update_gui(self.status_label.config, {"text": "Formatting request..."})
            summary_request = self.format_summary_request(all_textboxes_data)
            
            # Check context length
            estimated_tokens = len(summary_request.split())
            context_limit = self.context_length.get()
            
            if estimated_tokens > context_limit:
                self._update_gui(messagebox.showwarning, "Warning", 
                               f"Request size ({estimated_tokens} tokens) exceeds context limit ({context_limit} tokens). "
                               f"Summary may be incomplete.")
            
            # Generate summary
            self._update_gui(self.status_label.config, {"text": "Generating summary with AI model..."})
            self._update_gui(self.progress.config, {"value": 50})
            
            summary_system_prompt = "In English, output a markdown format summary of the story, and then a summary of each page."
            
            # Use a custom API call with the summary system prompt
            summary_response = self.generate_summary_with_custom_prompt(summary_request, summary_system_prompt)
            
            # Save summary to file
            self._update_gui(self.status_label.config, {"text": "Saving summary..."})
            self._update_gui(self.progress.config, {"value": 90})
            
            summary_file_path = os.path.join(self.output_dir.get(), "SummaryForRAG.txt")
            self.save_summary_file(summary_response, summary_file_path)
            
            # Complete
            self._update_gui(self.progress.config, {"value": 100})
            self._update_gui(self.status_label.config, {"text": "Summary generation complete."})
            self._update_gui(messagebox.showinfo, "Success", f"Summary saved to: {summary_file_path}")
            
        except Exception as e:
            logging.error(f"Summary generation failed: {e}")
            self._update_gui(messagebox.showerror, "Error", f"Failed to generate summary: {e}")
            self._update_gui(self.status_label.config, {"text": "Summary generation failed."})
        
        finally:
            # Re-enable buttons
            self._update_gui(self.summary_button.config, {"state": "normal"})
            self._update_gui(self.start_button.config, {"state": "normal"})
    
    def collect_all_textboxes(self, filepaths: list[os.PathLike]) -> list[dict]:
        """Collect all textboxes from all HTML files with page grouping.
        
        Args:
            filepaths: List of HTML file paths to process
            
        Returns:
            List of dictionaries containing textbox data with page information
        """
        all_textboxes = []
        global_textbox_counter = 0
        global_page_counter = 0
        
        # Sort files for consistent ordering
        sorted_filepaths = sorted(filepaths)
        
        for filepath in sorted_filepaths:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f, 'lxml')
                
                # Find all page containers
                page_containers = soup.find_all('div', class_='pageContainer')
                
                for page_container in page_containers:
                    global_page_counter += 1
                    page_textboxes = []
                    
                    # Find all textboxes in this page
                    textboxes = page_container.find_all('div', class_='textBox')
                    
                    for textbox in textboxes:
                        global_textbox_counter += 1
                        text_content = self.extract_textbox_text(textbox)
                        
                        if text_content.strip():  # Only include non-empty textboxes
                            page_textboxes.append({
                                'textbox_number': global_textbox_counter,
                                'text': text_content.strip()
                            })
                    
                    # Add page data if it has textboxes
                    if page_textboxes:
                        all_textboxes.append({
                            'page_number': global_page_counter,
                            'file_name': os.path.basename(filepath),
                            'textboxes': page_textboxes
                        })
                        
            except Exception as e:
                logging.error(f"Failed to process file {filepath}: {e}")
                continue
        
        return all_textboxes
    
    def format_summary_request(self, all_textboxes_data: list[dict]) -> str:
        """Format the collected textbox data into a request string.
        
        Args:
            all_textboxes_data: List of page data with textboxes
            
        Returns:
            Formatted request string with page groupings
        """
        request_parts = []
        
        for page_data in all_textboxes_data:
            page_num = page_data['page_number']
            textboxes = page_data['textboxes']
            
            # Add page header
            request_parts.append(f"[Page {page_num}]")
            
            # Add all textboxes for this page
            for textbox_data in textboxes:
                textbox_num = textbox_data['textbox_number']
                text = textbox_data['text']
                request_parts.append(f"Textbox {textbox_num}: \"{text}\"")
            
            # Add blank line between pages
            request_parts.append("")
        
        return '\n'.join(request_parts)
    
    def generate_summary_with_custom_prompt(self, request_text: str, system_prompt: str) -> str:
        """Generate summary using a custom system prompt.
        
        Args:
            request_text: The formatted request with all textboxes
            system_prompt: Custom system prompt for summary generation
            
        Returns:
            Generated summary text
        """
        try:
            # Temporarily store the original system prompt
            original_prompt = self.ollama_api.get_system_prompt()
            
            # Set the custom system prompt
            self.ollama_api.current_system_prompt = system_prompt
            
            # Add RAG context to the summary request
            rag_enhanced_request = self.format_request_with_rag(request_text)
            
            # Generate the summary
            response = self.ollama_api.generate(
                self.model_name.get(),
                rag_enhanced_request,
                context_length=self.context_length.get(),
                temperature=self.temperature.get()
            )
            
            # Restore the original system prompt
            self.ollama_api.current_system_prompt = original_prompt
            
            return response
            
        except Exception as e:
            # Ensure we restore the original prompt even if there's an error
            self.ollama_api.current_system_prompt = original_prompt
            raise e
    
    def save_summary_file(self, summary_content: str, file_path: str) -> None:
        """Save the summary content to a text file.
        
        Args:
            summary_content: The generated summary text
            file_path: Path where to save the summary file
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(summary_content)
            logging.info(f"Summary saved to: {file_path}")
        except Exception as e:
            logging.error(f"Failed to save summary file: {e}")
            raise e
    
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
            pages_processed_start: int,
            total_pages: int,
            global_textbox_counter: int,
            anchor: str | None = "think"
        ) -> tuple[str, int, int]:
        """Returns the translation of all text in a file using page-based translation.

        Args:
            filepath (os.PathLike): Path to the HTML file to translate
            pages_processed_start (int): Number of pages already processed
            total_pages (int): Total number of pages across all files
            global_textbox_counter (int): Global textbox counter across all files
            anchor (str | None): If anchor is present in the API response,
                remove all text between the first 2 occurences of anchor.

        Returns:
            tuple[str, int, int]: (translated HTML, total pages processed, updated global textbox counter)
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

            # Restore proper page navigation (ensure pages are properly hidden/shown)
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

        # Part 4: Page-Based Translation Processing
        pages_processed = pages_processed_start
        page_containers = soup.find_all('div', class_='pageContainer')
        
        # Use the global textbox counter passed from the calling function
        textbox_counter = global_textbox_counter
        
        # Process each page independently
        for page_index, page_container in enumerate(page_containers):
            try:
                # Translate this page and update counter
                textbox_counter = self.translate_page(page_container, textbox_counter, anchor)
                pages_processed += 1
                
                # Update progress
                progress_percentage = (pages_processed / total_pages) * 100
                self._update_gui(self.progress.config, {"value": progress_percentage})
                self._update_gui(self.line_count_label.config, {"text": f"Page {pages_processed}/{total_pages}"})
                
                # Update status with current page info
                filename = os.path.basename(filepath)
                self._update_gui(self.status_label.config, {"text": f"Translating {filename} - Page {page_index + 1}"})
                
            except Exception as e:
                logging.error(f"Failed to translate page {page_index + 1} in {filepath}: {e}")
                # Continue with next page even if this one fails
                textbox_counter += len(page_container.find_all('div', class_='textBox'))
                continue
        
        return str(soup.prettify()), pages_processed, textbox_counter

    def translate_page(self, page_container, textbox_counter_start, anchor, max_retries=3, retry_delay=1):
        """Translate all textboxes in a single page using page-based translation with retry logic.
        
        Args:
            page_container: BeautifulSoup page container element
            textbox_counter_start: Starting textbox number for this page
            anchor: Thinking block anchor for removal
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Delay in seconds between retry attempts (default: 1)
            
        Returns:
            int: Updated textbox counter after processing this page
        """
        import time
        
        textboxes = page_container.find_all('div', class_='textBox')
        
        if not textboxes:
            return textbox_counter_start
        
        # Enhance textbox attributes for all textboxes
        for textbox in textboxes:
            # Remove vertical writing mode for better horizontal text display
            if textbox.has_attr('style') and 'writing-mode' in textbox['style']:
                style_attr = textbox['style']
                new_style = re.sub(r'writing-mode\s*:\s*vertical-rl\s*;?', '', style_attr).strip()
                textbox['style'] = new_style
            
            # Add data attributes for JavaScript processing
            self.enhance_text_box_attributes(textbox)
        
        # Build request string for this page
        request_parts = []
        textbox_texts = []
        
        for i, textbox in enumerate(textboxes):
            textbox_num = textbox_counter_start + i + 1
            text = self.extract_textbox_text(textbox)
            if text.strip():
                request_parts.append(f'Textbox {textbox_num}: "{text}"')
                textbox_texts.append(text)
            else:
                textbox_texts.append("")
        
        if not request_parts:
            return textbox_counter_start + len(textboxes)
        
        # Send to Ollama with context length
        full_request = '\n'.join(request_parts)
        
        # Initialize merged translations dictionary
        merged_translations = {}
        
        # Retry loop for page translation
        for attempt in range(max_retries):
            logging.info(f"=== TRANSLATION REQUEST (Attempt {attempt + 1}/{max_retries}) ===")
            logging.info(f"Model: {self.model_name.get()}")
            logging.info(f"Context Length: {self.context_length.get()}")
            logging.info(f"Temperature: {self.temperature.get()}")
            logging.info(f"Request:\n{full_request}")
            logging.info(f"=== END REQUEST ===")
            
            try:
                # Add RAG context to the request
                rag_enhanced_request = self.format_request_with_rag(full_request)
                
                response = self.ollama_api.generate(
                    self.model_name.get(), 
                    rag_enhanced_request, 
                    context_length=self.context_length.get(),
                    temperature=self.temperature.get()
                )
                
                # Debug logging: Log the raw response
                logging.info(f"=== RAW RESPONSE (Attempt {attempt + 1}) ===")
                logging.info(f"Response length: {len(response)} characters")
                logging.info(f"Response:\n{response}")
                logging.info(f"=== END RESPONSE ===")
                
                # Parse this attempt's translations
                attempt_translations = self.parse_ollama_response(response)
                
                # Merge successful translations (don't overwrite existing good translations)
                for textbox_num, translation in attempt_translations.items():
                    if translation and translation.strip():  # Only merge non-empty translations
                        merged_translations[textbox_num] = translation
                        logging.info(f"Attempt {attempt + 1}: Successfully translated textbox {textbox_num}")
                
                # Check if we have all translations
                expected_textbox_nums = set(range(textbox_counter_start + 1, textbox_counter_start + len(textboxes) + 1))
                translated_textbox_nums = set(merged_translations.keys())
                missing_textboxes = expected_textbox_nums - translated_textbox_nums
                
                if not missing_textboxes:
                    logging.info(f"=== PAGE TRANSLATION COMPLETE ===")
                    logging.info(f"All {len(textboxes)} textboxes translated successfully after {attempt + 1} attempt(s)")
                    logging.info(f"=== END PAGE TRANSLATION ===")
                    break
                else:
                    logging.warning(f"Attempt {attempt + 1}: Missing translations for textboxes: {sorted(missing_textboxes)}")
                    if attempt < max_retries - 1:  # Don't delay after the last attempt
                        logging.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                
            except Exception as e:
                logging.error(f"Translation request failed on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    logging.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                continue
        
        # Apply all merged translations to textboxes
        self.apply_merged_translations(textboxes, merged_translations, textbox_counter_start, anchor)
        
        # Final success report
        expected_count = len([t for t in textbox_texts if t.strip()])  # Only count non-empty textboxes
        actual_count = len(merged_translations)
        success_rate = (actual_count / expected_count * 100) if expected_count > 0 else 100
        
        logging.info(f"=== FINAL PAGE RESULTS ===")
        logging.info(f"Successfully translated {actual_count}/{expected_count} textboxes ({success_rate:.1f}%)")
        if actual_count < expected_count:
            missing_nums = set(range(textbox_counter_start + 1, textbox_counter_start + len(textboxes) + 1)) - set(merged_translations.keys())
            logging.warning(f"Final missing textboxes: {sorted(missing_nums)}")
        logging.info(f"=== END PAGE RESULTS ===")
        
        return textbox_counter_start + len(textboxes)
    
    def apply_merged_translations(self, textboxes, merged_translations, counter_start, anchor):
        """Apply merged translations from multiple attempts to textboxes"""
        try:
            successful_translations = 0
            for i, textbox in enumerate(textboxes):
                expected_num = counter_start + i + 1
                
                if expected_num in merged_translations:
                    translation = merged_translations[expected_num]
                    if translation:  # Don't apply empty translations
                        # Remove thinking blocks
                        cleaned_translation = remove_between_anchors(translation, anchor)
                        
                        # Apply translation to textbox
                        self.scorched_earth_clear_and_rebuild(textbox, cleaned_translation)
                        
                        # Add text length class for styling hints
                        text_length = len(cleaned_translation)
                        if text_length > 200:
                            textbox['class'] = textbox.get('class', []) + ['long-text']
                        elif text_length > 100:
                            textbox['class'] = textbox.get('class', []) + ['medium-text']
                        else:
                            textbox['class'] = textbox.get('class', []) + ['short-text']
                        
                        successful_translations += 1
                        
                        # Update last translation display
                        self._update_gui(self.last_translation_label.config, 
                                       {"text": f"Last: {cleaned_translation[:50]}..."})
                    else:
                        logging.warning(f"Empty translation for textbox {expected_num}")
                else:
                    logging.warning(f"Missing translation for textbox {expected_num}")
                    # Keep original text
            
            logging.info(f"Successfully applied {successful_translations}/{len(textboxes)} translations")
            
        except Exception as e:
            logging.error(f"Translation application failed: {e}")
            # Fallback: keep all original text
            logging.info("Keeping original text due to application failure")
    
    def parse_and_apply_translations(self, textboxes, response, counter_start, anchor):
        """Parse Ollama response and apply translations to textboxes"""
        try:
            translations = self.parse_ollama_response(response)
            
            # Apply translations
            successful_translations = 0
            for i, textbox in enumerate(textboxes):
                expected_num = counter_start + i + 1
                
                if expected_num in translations:
                    translation = translations[expected_num]
                    if translation:  # Don't apply empty translations
                        # Remove thinking blocks
                        cleaned_translation = remove_between_anchors(translation, anchor)
                        
                        # Apply translation to textbox
                        self.scorched_earth_clear_and_rebuild(textbox, cleaned_translation)
                        
                        # Add text length class for styling hints
                        text_length = len(cleaned_translation)
                        if text_length > 200:
                            textbox['class'] = textbox.get('class', []) + ['long-text']
                        elif text_length > 100:
                            textbox['class'] = textbox.get('class', []) + ['medium-text']
                        else:
                            textbox['class'] = textbox.get('class', []) + ['short-text']
                        
                        successful_translations += 1
                        
                        # Update last translation display
                        self._update_gui(self.last_translation_label.config, 
                                       {"text": f"Last: {cleaned_translation[:50]}..."})
                    else:
                        logging.warning(f"Empty translation for textbox {expected_num}")
                else:
                    logging.warning(f"Missing translation for textbox {expected_num}")
                    # Keep original text
            
            logging.info(f"Successfully applied {successful_translations}/{len(textboxes)} translations")
            
        except Exception as e:
            logging.error(f"Translation parsing failed: {e}")
            # Fallback: keep all original text
            logging.info("Keeping original text due to parsing failure")
    
    def parse_ollama_response(self, response):
        """Parse Ollama response with multiple fallback strategies"""
        
        logging.info(f"=== PARSING RESPONSE ===")
        
        # Strategy 1: Exact format match
        pattern1 = r'Textbox\s+(\d+):\s*"([^"]*)"'
        matches = re.findall(pattern1, response, re.MULTILINE | re.DOTALL)
        
        logging.info(f"Strategy 1 (exact format) found {len(matches)} matches: {matches}")
        
        if matches:
            result = self.process_matches(matches)
            logging.info(f"Strategy 1 result: {result}")
            return result
        
        # Strategy 2: Handle missing quotes
        pattern2 = r'Textbox\s+(\d+):\s*([^\n\r]+)'
        matches = re.findall(pattern2, response, re.MULTILINE)
        
        logging.info(f"Strategy 2 (missing quotes) found {len(matches)} matches: {matches}")
        
        if matches:
            # Clean up matches that might have quotes or other formatting
            cleaned_matches = []
            for num, text in matches:
                # Remove surrounding quotes if present
                text = text.strip().strip('"\'')
                cleaned_matches.append((num, text))
            result = self.process_matches(cleaned_matches)
            logging.info(f"Strategy 2 result: {result}")
            return result
        
        # Strategy 3: Line-by-line parsing for malformed responses
        logging.info("Falling back to line-by-line parsing")
        result = self.parse_line_by_line(response)
        logging.info(f"Strategy 3 result: {result}")
        logging.info(f"=== END PARSING ===")
        return result
    
    def process_matches(self, matches):
        """Convert regex matches to clean translations dictionary"""
        translations = {}
        for textbox_num_str, translation in matches:
            textbox_num = int(textbox_num_str)
            cleaned_translation = self.clean_translation(translation)
            translations[textbox_num] = cleaned_translation
        return translations
    
    def clean_translation(self, raw_translation):
        """Clean translation text according to requirements"""
        # Strip leading/trailing whitespace
        cleaned = raw_translation.strip()
        
        # Remove solo periods (periods that are alone, not part of other text)
        # This handles cases like: "Yeah sure." -> "Yeah sure"
        # But preserves: "Mr. Smith" or "..." or "Really!?"
        
        # Remove trailing solo period
        if cleaned.endswith('.') and len(cleaned) > 1 and cleaned[-2] != '.':
            # Check if it's truly a solo period (not part of abbreviation, etc.)
            if not re.search(r'[A-Z]\.$', cleaned):  # Not an abbreviation like "Mr."
                cleaned = cleaned[:-1].rstrip()
        
        # Remove leading solo period (less common but possible)
        if cleaned.startswith('.') and len(cleaned) > 1 and cleaned[1] != '.':
            cleaned = cleaned[1:].lstrip()
        
        return cleaned
    
    def parse_line_by_line(self, response):
        """Fallback parser for when regex fails"""
        translations = {}
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for any line that starts with "Textbox" and a number
            if line.lower().startswith('textbox'):
                # Try to extract number and text
                parts = line.split(':', 1)
                if len(parts) == 2:
                    # Extract textbox number
                    textbox_part = parts[0].strip()
                    num_match = re.search(r'(\d+)', textbox_part)
                    
                    if num_match:
                        textbox_num = int(num_match.group(1))
                        translation = parts[1].strip().strip('"\'')
                        cleaned = self.clean_translation(translation)
                        translations[textbox_num] = cleaned
        
        return translations

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

    def get_context_window(self, textboxes, current_index, context_length):
        """Calculate the actual available context for a given textbox position.
        
        Args:
            textboxes: List of textbox elements
            current_index: Index of current textbox being translated
            context_length: Requested context length from GUI
            
        Returns:
            tuple: (prev_contexts, current_textbox, future_contexts)
        """
        # Calculate actual available previous contexts
        prev_start = max(0, current_index - context_length)
        prev_contexts = textboxes[prev_start:current_index]
        
        # Calculate actual available future contexts  
        future_end = min(len(textboxes), current_index + context_length + 1)
        future_contexts = textboxes[current_index + 1:future_end]
        
        return prev_contexts, textboxes[current_index], future_contexts

    def build_context_request(self, prev_contexts, current_text, future_contexts):
        """Build the formatted request string with context markers.
        
        Args:
            prev_contexts: List of previous textbox texts
            current_text: Current textbox text to translate
            future_contexts: List of future textbox texts
            
        Returns:
            str: Formatted request string with context markers
        """
        request_parts = []
        
        # Add previous contexts (only if they exist)
        for prev_text in prev_contexts:
            if prev_text.strip():  # Only add non-empty contexts
                request_parts.append(f"\\{prev_text.strip()}\\")
        
        # Add current text (always present)
        request_parts.append(f"|{current_text.strip()}|")
        
        # Add future contexts (only if they exist)  
        for future_text in future_contexts:
            if future_text.strip():  # Only add non-empty contexts
                request_parts.append(f"/{future_text.strip()}/")
        
        return " ".join(request_parts)

    def extract_textbox_text(self, textbox):
        """Extract text content from a textbox element.
        
        Args:
            textbox: BeautifulSoup textbox element
            
        Returns:
            str: Extracted text content
        """
        # Try multiple extraction methods to get complete text
        text_parts = []
        
        # Method 1: Get text from p tag
        if textbox.p:
            p_text = textbox.p.get_text(separator=' ', strip=True)
            if p_text:
                text_parts.append(p_text)
        
        # Method 2: Get all text content directly from textbox
        all_text = textbox.get_text(separator=' ', strip=True)
        if all_text and all_text not in text_parts:
            text_parts.append(all_text)
        
        # Method 3: Check for nested elements that might contain text
        for element in textbox.find_all(['span', 'div', 'ruby', 'rt', 'rp']):
            element_text = element.get_text(separator=' ', strip=True)
            if element_text and element_text not in text_parts:
                text_parts.append(element_text)
        
        # Combine all found text parts
        combined_text = ' '.join(text_parts).strip()
        
        # Log what we extracted for debugging
        logging.info(f"Extracted text from textbox: '{combined_text}'")
        
        return combined_text

    def translate_text_box(self, box, context_texts=None, current_index=None) -> str:
        """Translate a textbox with optional context.
        
        Args:
            box: Current textbox element
            context_texts: List of all textbox texts for context (optional)
            current_index: Index of current textbox in context_texts (optional)
            
        Returns:
            str: Translated text
        """
        original_text = box.p.get_text(separator='\n').strip()
        if not original_text:
            return ""
            
        # Determine if we should use context
        context_length = self.context_length.get()
        
        if context_length > 0 and context_texts is not None and current_index is not None:
            # Use context-aware translation
            prev_contexts, current_text, future_contexts = self.get_context_window(
                context_texts, current_index, context_length
            )
            
            # Build the context request
            request_text = self.build_context_request(prev_contexts, current_text, future_contexts)
        else:
            # Use original stateless translation (context_length = 0)
            request_text = original_text
            
        try:
            translated_text = self.ollama_api.generate(self.model_name.get(), request_text)
        except Exception as e:
            self._update_gui(messagebox.showerror, "Translation Error", f"An error occurred during translation: {e}")
            return ""
            
        return translated_text

    def on_rag_files_dropped(self, event):
        """Handle files dropped onto the RAG drop area."""
        try:
            # Get the list of files from the drop event
            files = self.tk.splitlist(event.data)
            
            added_files = 0
            for file_path in files:
                if self.load_rag_file(file_path):
                    added_files += 1
            
            if added_files > 0:
                self.update_rag_display()
                messagebox.showinfo("Files Added", f"Successfully added {added_files} RAG file(s).")
            else:
                messagebox.showwarning("No Files Added", "No valid text files were added.")
                
        except Exception as e:
            logging.error(f"Error handling dropped files: {e}")
            messagebox.showerror("Error", f"Failed to process dropped files: {e}")
    
    def on_rag_drag_enter(self, event):
        """Handle drag enter event for visual feedback."""
        self.rag_drop_area.config(bg="lightblue")
        self.rag_drop_label.config(bg="lightblue", text="Drop files here!")
    
    def on_rag_drag_leave(self, event):
        """Handle drag leave event to restore normal appearance."""
        self.rag_drop_area.config(bg="lightgray")
        self.rag_drop_label.config(bg="lightgray", text="Drop text files here for RAG context\n(Supports .txt, .md, .json files)")
    
    def load_rag_file(self, file_path: str) -> bool:
        """Load a RAG file and add it to the collection.
        
        Args:
            file_path: Path to the file to load
            
        Returns:
            bool: True if file was successfully loaded, False otherwise
        """
        try:
            # Check if file already exists
            for existing_file in self.rag_files:
                if existing_file['path'] == file_path:
                    logging.info(f"File already loaded: {file_path}")
                    return False
            
            # Check file extension
            _, ext = os.path.splitext(file_path.lower())
            if ext not in ['.txt', '.md', '.json', '.csv', '.log']:
                logging.warning(f"Unsupported file type: {ext}")
                return False
            
            # Check file size (limit to 10MB)
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                messagebox.showwarning("File Too Large", f"File {os.path.basename(file_path)} is too large (>10MB). Skipping.")
                return False
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().strip()
            
            if not content:
                logging.warning(f"Empty file: {file_path}")
                return False
            
            # Add to RAG files collection
            self.rag_files.append({
                'path': file_path,
                'name': os.path.basename(file_path),
                'content': content,
                'size': len(content)
            })
            
            # Invalidate cache
            self.rag_content_cache = ""
            
            logging.info(f"Successfully loaded RAG file: {file_path}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to load RAG file {file_path}: {e}")
            return False
    
    def remove_selected_rag_files(self):
        """Remove selected files from the RAG collection."""
        try:
            selected_indices = self.rag_files_listbox.curselection()
            if not selected_indices:
                messagebox.showinfo("No Selection", "Please select files to remove.")
                return
            
            # Remove files in reverse order to maintain indices
            for index in reversed(selected_indices):
                if 0 <= index < len(self.rag_files):
                    removed_file = self.rag_files.pop(index)
                    logging.info(f"Removed RAG file: {removed_file['name']}")
            
            # Invalidate cache and update display
            self.rag_content_cache = ""
            self.update_rag_display()
            
        except Exception as e:
            logging.error(f"Error removing RAG files: {e}")
            messagebox.showerror("Error", f"Failed to remove files: {e}")
    
    def clear_all_rag_files(self):
        """Clear all RAG files."""
        if not self.rag_files:
            messagebox.showinfo("No Files", "No RAG files to clear.")
            return
        
        if messagebox.askyesno("Clear All Files", f"Are you sure you want to remove all {len(self.rag_files)} RAG files?"):
            self.rag_files.clear()
            self.rag_content_cache = ""
            self.update_rag_display()
            logging.info("Cleared all RAG files")
    
    def update_rag_display(self):
        """Update the RAG files display."""
        # Clear listbox
        self.rag_files_listbox.delete(0, tk.END)
        
        # Add files to listbox
        for rag_file in self.rag_files:
            size_kb = rag_file['size'] / 1024
            display_text = f"{rag_file['name']} ({size_kb:.1f} KB)"
            self.rag_files_listbox.insert(tk.END, display_text)
        
        # Update info label
        if self.rag_files:
            total_size = sum(f['size'] for f in self.rag_files)
            total_size_kb = total_size / 1024
            self.rag_info_label.config(text=f"{len(self.rag_files)} files ({total_size_kb:.1f} KB)")
        else:
            self.rag_info_label.config(text="No RAG files loaded")
    
    def get_rag_context(self) -> str:
        """Get formatted RAG context for inclusion in requests.
        
        Returns:
            str: Formatted RAG context or empty string if no files
        """
        if not self.rag_files:
            return ""
        
        # Use cached content if available
        if self.rag_content_cache:
            return self.rag_content_cache
        
        # Build RAG context
        context_parts = ["=== RAG CONTEXT ==="]
        
        for rag_file in self.rag_files:
            context_parts.append(f"\n--- {rag_file['name']} ---")
            context_parts.append(rag_file['content'])
        
        context_parts.append("\n=== END RAG CONTEXT ===\n")
        
        # Cache the result
        self.rag_content_cache = '\n'.join(context_parts)
        return self.rag_content_cache
    
    def format_request_with_rag(self, original_request: str) -> str:
        """Format a request with RAG context if available.
        
        Args:
            original_request: The original request text
            
        Returns:
            str: Request with RAG context prepended, or original if no RAG
        """
        rag_context = self.get_rag_context()
        if not rag_context:
            return original_request
        
        return f"{rag_context}\n{original_request}"

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
