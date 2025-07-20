
# JavaScript code to use in Mokuro
# IMPORTANT: All JavaScript code below is stored in Python string literals.
# This means backslashes need to be escaped (\\s becomes \s in JavaScript, \\d becomes \d).
# Do NOT change regex patterns like /width:\\s*(\\d+)/ to /width:\s*(\d+)/ as this will
# cause Python SyntaxWarnings due to invalid escape sequences in the Python string.
PROPERTIES_JS_FUNC = """
function updateProperties() {
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
        // Update text background positioning after DOM is ready
        setTimeout(updateTextBackgrounds, 0);
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
        // NOTE: Double backslashes below are intentional - this JavaScript code lives inside a Python string,
        const widthMatch = style.match(/width:\\s*(\\d+)/);
        const heightMatch = style.match(/height:\\s*(\\d+)/);
        
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
window.addEventListener('resize', handleResize);

// Function to update text background positioning and sizing
function updateTextBackgrounds() {
    if (!state.alwaysShowTranslation) return;
    
    const textBoxes = document.querySelectorAll('.always-show-translation .textBox');
    textBoxes.forEach(textBox => {
        const paragraph = textBox.querySelector('p');
        if (!paragraph || !paragraph.textContent.trim()) return;
        
        // Force a reflow to get accurate measurements
        paragraph.offsetHeight;
        
        // Get text dimensions
        const textRect = paragraph.getBoundingClientRect();
        const boxRect = textBox.getBoundingClientRect();
        
        // Calculate relative position within the textBox
        const relativeLeft = textRect.left - boxRect.left;
        const relativeTop = textRect.top - boxRect.top;
        
        // Add 5px extension in all directions
        const backgroundLeft = relativeLeft - 5;
        const backgroundTop = relativeTop - 5;
        const backgroundWidth = textRect.width + 10; // 5px on each side
        const backgroundHeight = textRect.height + 10; // 5px on each side
        
        // Apply styles to the ::after pseudo-element via CSS custom properties
        textBox.style.setProperty('--text-bg-left', backgroundLeft + 'px');
        textBox.style.setProperty('--text-bg-top', backgroundTop + 'px');
        textBox.style.setProperty('--text-bg-width', backgroundWidth + 'px');
        textBox.style.setProperty('--text-bg-height', backgroundHeight + 'px');
    });
}

// Update text backgrounds when window resizes
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        if (state.constrainText) {
            applySmartFontScaling();
        }
        if (state.alwaysShowTranslation) {
            updateTextBackgrounds();
        }
    }, 250);
});
"""

LISTENER_JS_FUNC = """
document.getElementById('menuAlwaysShowTranslation').addEventListener('click', function () {
    state.alwaysShowTranslation = document.getElementById("menuAlwaysShowTranslation").checked;
    saveState();
    updateProperties();
}, false);

document.getElementById('menuConstrainText').addEventListener('click', function () {
    state.constrainText = document.getElementById("menuConstrainText").checked;
    saveState();
    updateProperties();
}, false);
"""

ALWAYS_SHOW_TRANSLATION_JS_FUNC = """
/* Always show translation feature - proper three-layer implementation */
/* Layer 1: White box that fills the entire textBox bounds (outline fill) */
.always-show-translation .textBox::before {
    content: '' !important;
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    background-color: white !important;
    z-index: 5 !important;
    pointer-events: none !important;
}

/* Layer 2: White background behind text that extends 5px past text edges */
.always-show-translation .textBox::after {
    content: '' !important;
    position: absolute !important;
    background-color: white !important;
    border-radius: 4px !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.15) !important;
    z-index: 8 !important;
    pointer-events: none !important;
    /* Size and position set by JavaScript based on text content */
    left: var(--text-bg-left, 0) !important;
    top: var(--text-bg-top, 0) !important;
    width: var(--text-bg-width, 0) !important;
    height: var(--text-bg-height, 0) !important;
}

/* Layer 3: Text content - preserve original positioning, no background */
.always-show-translation .textBox p { 
    display: block !important;
    background-color: transparent !important;
    color: black !important;
    opacity: 1 !important;
    visibility: visible !important;
    z-index: 10 !important;
    padding: 0 !important;
    margin: 0 !important;
    font-weight: normal !important;
    text-shadow: none !important;
    white-space: normal !important;
    word-wrap: break-word !important;
    overflow-wrap: break-word !important;
    line-height: 1.3 !important;
    text-rendering: optimizeLegibility !important;
    -webkit-font-smoothing: antialiased !important;
    -moz-osx-font-smoothing: grayscale !important;
    position: relative !important;
}

/* Text sizing for different lengths - no padding since background is separate */
.always-show-translation .short-text .textBox p {
    font-size: 1.1em !important;
    line-height: 1.2em !important;
}

.always-show-translation .medium-text .textBox p {
    font-size: 1em !important;
    line-height: 1.1em !important;
}

.always-show-translation .long-text .textBox p {
    font-size: 0.9em !important;
    line-height: 1.05em !important;
    letter-spacing: -0.02em !important;
}

/* Size category specific text sizing */
.always-show-translation .textBox[data-size-category="small"] p {
    font-size: 0.85em !important;
}

.always-show-translation .textBox[data-size-category="large"] p {
    line-height: 1.15em !important;
}

/* Ensure translation text is always visible */
.always-show-translation .textBox p * {
    color: black !important;
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

UPDATE_PAGE_JS_ORIGINAL = """getPage(state.page_idx).style.display = "none";"""

UPDATE_PAGE_JS_FUNC = """// getPage(state.page_idx).style.display = "none";"""
