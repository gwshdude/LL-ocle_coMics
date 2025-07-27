
# LL-ocle_coMics

## What is this?

This project simplifies the process of machine-translating comics into the English language. By using OCR (optical character recognition), machine translation, and HTML formatting, the program displays the original image overlaid with the translated text.

## License

LL-ocle_coMics is licensed under the UNLICENSE. See `LICENSE.md` for license information.

## Getting Started

### Requirements

1. [Ollama](https://ollama.com/download)
2. A LLM capable of translating Japanese to English ([RpR-v4-Fast-30B-A3B](hf.co/mradermacher/RpR-v4-Fast-30B-A3B) is recommended)
3. [Mokuro](https://github.com/kha-white/mokuro) Python module or `pip install mokuro`
4. This module

### To Run

1. In your terminal, run `ollama serve` to start Ollama's background process.
2. Use Mokuro to convert your image files into HTML files containing OCR data for each file.
3. Navigate to the folder that you cloned this repo to and go as deep in the src folder as you can until you see all the files
4. `python -m venv venv`
5. `source venv/bin/activate`
6. `python main.py`
7. Choose the input directory as the folder with the HTML file that mokuro generated, and choose any output directory you want
8. Choose your ollama model. I recommend XortronCriminalComputingConfig. Run the biggest quant you can physically fit into your system if you're running over night.
9. *OPTIONAL* Edit the prompt or supply additional context via dropping a text/md document into the RAG box.
10. *OPTIONAL* Use the "Generate Model Story Context" button and then find the text document it produced in your output folder and drop that into the RAG box. (this option requires more memory than just doing translation. You may have to skip it if you don't have enough. It will take much longer than the progress bar makes it seem. I recommend both this option and the actual translation be run overnight or while you're at work, as it'll take a while.)
11. Click "Start Translation"
12. Enjoy

## Why do it this way?

The problem of automatic translation has traditionally been that word-for-word machine translation leads to many strange and inaccurate translations that can be confusing, and LLM's simply don't have a large enough context window to translate an entire work if it's long enough. This approach solves the issue by using stateless requests to Ollama by entire textbox groups. In short, the LLM receives an entire phrase or sentence at once to have more context for a higher quality translation, but lacks context of the rest of the work so that it can be handled in chunks.

## Further Considerations

This is an early version of a personal project. It may contain undocumented glitches and bugs.

The program could be extended by including other text boxes in the context. This would require considering the user's remaining context window size.
