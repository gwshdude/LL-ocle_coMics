
import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
from bs4 import BeautifulSoup
import threading
from apis import OllamaAPI

# Languages to translate from
SOURCE_LANGUAGES = [
    "Japanese", "Japanese", "Korean", "Thai",
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
        self.geometry("400x350")
        self.resizable(False, False)

        self.source_language = tk.StringVar(value="Japanese")
        self.model_name = tk.StringVar()
        
        self.ollama_api = OllamaAPI()
        self.ollama_base_url = ollama_base_url

        self.is_translating = False
        self.translation_thread = None

        self.create_widgets()

        # populate LLMs
        try:
            self.populate_models()
        except:
            self.model_name.set("Error fetching models")
            messagebox.showerror("Error", f"Could not fetch Ollama models: {e}")
        
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

        lang_menu = ttk.OptionMenu(lang_frame, *SOURCE_LANGUAGES)
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

    def populate_models(self) -> None:
        connected, message = self.ollama_api.check_connection()
        if not connected:
            raise Exception(message)
        
        try:
            model_names = self.ollama_api.get_models()
        except Exception as e:
            messagebox.showerror("Error", f"Could not fetch Ollama models: {e}")
        else:
            if not model_names or len(model_names) < 1:
                messagebox.showerror("Error", "Did not fetch any Ollama models.")

        self.model_name.set(model_names[0])
        menu = self.model_menu["menu"]
        menu.delete(0, "end")
        for name in model_names:
            menu.add_command(label=name, command=lambda value=name: self.model_name.set(value))

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
            
            # Define the replacement function with enhanced functionality
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
        // Apply smart font scaling when constrain text is enabled
        applySmartFontScaling();
    } else {
        pc.classList.remove('constrain-text');
        // Reset font sizes when constrain text is disabled
        resetFontSizes();
    }
}

// Smart font scaling function
function applySmartFontScaling() {
    const textBoxes = document.querySelectorAll('.textBox');
    textBoxes.forEach(textBox => {
        const paragraph = textBox.querySelector('p');
        if (!paragraph || !paragraph.textContent.trim()) return;
        
        // Get text box dimensions from style attribute
        const style = textBox.getAttribute('style');
        const widthMatch = style.match(/width:\s*(\d+)/);
        const heightMatch = style.match(/height:\s*(\d+)/);
        
        if (!widthMatch || !heightMatch) return;
        
        const boxWidth = parseInt(widthMatch[1]);
        const boxHeight = parseInt(heightMatch[1]);
        
        // Account for padding
        const availableWidth = boxWidth - 4;
        const availableHeight = boxHeight - 4;
        
        // Start with current font size or default
        let fontSize = parseInt(window.getComputedStyle(paragraph).fontSize) || 16;
        const minFontSize = 16;  // Minimum font size to prevent too small text
        const maxFontSize = 60;
        
        // Binary search for optimal font size
        let low = minFontSize;
        let high = Math.min(fontSize, maxFontSize);
        let bestSize = minFontSize;
        
        while (low <= high) {
            const testSize = Math.floor((low + high) / 2);
            paragraph.style.fontSize = testSize + 'px';
            
            // Force reflow to get accurate measurements
            paragraph.offsetHeight;
            
            const textWidth = paragraph.scrollWidth;
            const textHeight = paragraph.scrollHeight;
            
            if (textWidth <= availableWidth && textHeight <= availableHeight) {
                bestSize = testSize;
                low = testSize + 1;
            } else {
                high = testSize - 1;
            }
        }
        
        // Apply the best font size found
        paragraph.style.fontSize = bestSize + 'px';
        textBox.setAttribute('data-scaled-font-size', bestSize);
    });
}

// Reset font sizes function
function resetFontSizes() {
    const textBoxes = document.querySelectorAll('.textBox');
    textBoxes.forEach(textBox => {
        const paragraph = textBox.querySelector('p');
        if (paragraph) {
            paragraph.style.fontSize = '';
            textBox.removeAttribute('data-scaled-font-size');
        }
    });
}

// Measure text dimensions utility
function measureTextDimensions(element) {
    const rect = element.getBoundingClientRect();
    return {
        width: element.scrollWidth,
        height: element.scrollHeight,
        displayWidth: rect.width,
        displayHeight: rect.height
    };
}

// Debounced resize handler for responsive font scaling
let resizeTimeout;
function handleResize() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        if (state.constrainText) {
            applySmartFontScaling();
        }
    }, 250);
}

// Add resize listener
window.addEventListener('resize', handleResize);'''
            
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

    def translate_file(self, file_path, output_dir, boxes_processed, total_text_boxes):
        with open(file_path, 'r', encoding='utf-8') as f:
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
            css += """

/* Always show translation feature */
.always-show-translation .textBox p { 
    display: table !important; 
    background-color: rgb(255, 255, 255);
}

/* Enhanced constrain text feature with smart font scaling */
.constrain-text .textBox {
    overflow: visible;
}

.constrain-text .textBox p { 
    white-space: normal;
    word-wrap: break-word;
    word-break: break-word;
    overflow-wrap: break-word;
    hyphens: auto;
    line-height: 1.1em;
    margin: 0;
    padding: 2px;
    box-sizing: border-box;
    height: 100%;
    display: flex;
    align-items: flex-start;
    justify-content: flex-start;
}

/* Text alignment options */
.align-center .textBox p { 
    text-align: center; 
    align-items: center;
    justify-content: center;
}

.align-top-center .textBox p { 
    text-align: center; 
    align-items: flex-start;
    justify-content: center;
}

.align-bottom .textBox p { 
    align-items: flex-end;
}

.align-middle .textBox p { 
    align-items: center;
}

/* Font scaling classes */
.font-scaled .textBox p {
    font-size: var(--scaled-font-size, 16pt) !important;
}

/* Improved text rendering */
.textBox p {
    text-rendering: optimizeLegibility;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* Text length specific styles */
.short-text .textBox p {
    font-size: 1.1em;
    line-height: 1.2em;
}

.medium-text .textBox p {
    font-size: 1em;
    line-height: 1.1em;
}

.long-text .textBox p {
    font-size: 0.9em;
    line-height: 1.05em;
    letter-spacing: -0.02em;
}

/* Size category specific styles */
.textBox[data-size-category="small"] p {
    padding: 1px;
    font-size: 0.85em;
}

.textBox[data-size-category="medium"] p {
    padding: 2px;
}

.textBox[data-size-category="large"] p {
    padding: 3px;
    line-height: 1.15em;
}

/* Aspect ratio specific adjustments */
.textBox[data-aspect-ratio] p {
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
}

/* Wide boxes (aspect ratio > 2) */
.textBox[data-aspect-ratio^="2."], 
.textBox[data-aspect-ratio^="3."], 
.textBox[data-aspect-ratio^="4."], 
.textBox[data-aspect-ratio^="5."] {
    /* Wide boxes get left-aligned text */
}

.textBox[data-aspect-ratio^="2."] p, 
.textBox[data-aspect-ratio^="3."] p, 
.textBox[data-aspect-ratio^="4."] p, 
.textBox[data-aspect-ratio^="5."] p {
    text-align: left;
    justify-content: flex-start;
    align-items: flex-start;
}

/* Tall boxes (aspect ratio < 0.5) */
.textBox[data-aspect-ratio^="0.1"], 
.textBox[data-aspect-ratio^="0.2"], 
.textBox[data-aspect-ratio^="0.3"], 
.textBox[data-aspect-ratio^="0.4"] {
    /* Tall boxes get centered text */
}

.textBox[data-aspect-ratio^="0.1"] p, 
.textBox[data-aspect-ratio^="0.2"] p, 
.textBox[data-aspect-ratio^="0.3"] p, 
.textBox[data-aspect-ratio^="0.4"] p {
    text-align: center;
    justify-content: center;
    align-items: center;
    writing-mode: horizontal-tb;
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
                    original_text = box.p.get_text(separator='\n').strip()
                    if original_text:
                        try:
                            translated_text = self.ollama_api.generate(self.model_name.get(), original_text)
                            box.p.string = translated_text
                            
                            # Add text length class for styling hints
                            text_length = len(translated_text)
                            if text_length > 200:
                                box['class'] = box.get('class', []) + ['long-text']
                            elif text_length > 100:
                                box['class'] = box.get('class', []) + ['medium-text']
                            else:
                                box['class'] = box.get('class', []) + ['short-text']
                            
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

def main():
    app = MokuroTranslator()
    app.mainloop()

if __name__ == "__main__":
    main()
    