
# LL-ocle_coMics

## What is this?

This project simplifies the process of machine-translating comics into the English language. By using OCR (optical character recognition), LLM machine translation, and HTML formatting, the program makes use of mokuro and ollama to display the original image overlaid with the translated text.

## License

LL-ocle_coMics is licensed under the UNLICENSE. See `LICENSE.md` for license information.

## Getting Started

### Requirements

1. [Ollama](https://ollama.com/download)
2. A LLM capable of translating Japanese to English (https://huggingface.co/darkc0de/XortronCriminalComputingConfig is recommended)
3. [Mokuro](https://github.com/kha-white/mokuro) Python module or `pip install mokuro`
4. This app

### To Run

1. In your terminal, run `ollama serve` to start Ollama's background process.
2. Use Mokuro to convert your image files into HTML files containing OCR data for each file. (mokuro path/to/images)
3. Navigate to the folder that you cloned this repo to and go as deep in the src folder as you can until you see all the files
4. `python -m venv venv`
5. `source venv/bin/activate`
6. `python main.py`
7. Choose the input directory as the folder with the HTML file that mokuro generated, and choose any output directory you want
8. Choose your ollama model. I recommend XortronCriminalComputingConfig. Run the biggest quant you can physically fit into your system if you're running over night.
9. *OPTIONAL* Edit the prompt or supply additional context via dropping a text/md document into the RAG box.
10. *OPTIONAL* Use the "Generate Model Story Context" button and then find the text document it produced in your output folder and drop that into the RAG box. (this option requires more memory than just doing translation. You may have to skip it if you don't have enough. It will take much longer than the progress bar makes it seem. I recommend both this option and the actual translation be run overnight or while you're at work, as it'll take a while.)
11. Click "Start Translation"
12. The resulting HTML file will require you to put it just outside the images folder to open correctly (rename it to whatever you want and stick it in the folder you specified as the input folder)
13. Enjoy

## Why do it this way?

The problem of automatic translation has traditionally been that word-for-word machine translation leads to many strange and inaccurate translations that can be confusing, and LLM's typically don't have a large enough effective context window to translate an entire work if it's long enough, or they aren't very good at reading text on an image. This approach solves the issue by doing OCR on the images first, then using stateless requests to Ollama by entire textbox groups. In short, the LLM receives an entire phrase or sentence at once to have more context for a higher quality translation, but lacks context of the rest of the work so that it can be handled in chunks. If your hardware is strong enough, you can also generate a model context summary to essentially re-add the context of the whole work to the LLM via RAG for translation.

## Further Considerations

This is an early version of a personal project. It may contain undocumented glitches and bugs.

This approach takes substantial hardware to run at a high quality at time of writing.

If the license allows it, integrating mokuro into the GUI would further simplify the use of the app.
