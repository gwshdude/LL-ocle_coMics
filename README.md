
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
3. Copy the HTML files Mokuro generated to (TODO)
4. TODO: directions on running this module with `python -m`
5. TODO: explain how to replace the translated OCR file in the Mokuro folder

## Why do it this way?

The problem of automatic translation has traditionally been that word-for-word machine translation leads to many strange and inaccurate translations that can be confusing, and LLM's simply don't have a large enough context window to translate an entire work if it's long enough. This approach solves the issue by using stateless requests to Ollama by entire textbox groups. In short, the LLM receives an entire phrase or sentence at once to have more context for a higher quality translation, but lacks context of the rest of the work so that it can be handled in chunks.

## Further Considerations

This is an early version of a personal project. It may contain undocumented glitches and bugs.

The program could be extended by including other text boxes in the context. This would require considering the user's remaining context window size.
