
# LL-ocle_coMics

## What is this?

This project simplifies the process of machine-translating comics into the English language. By using OCR (optical character recognition), machine translation, and HTML formatting, the program displays the original image overlaid with the translated text.

## License

LL-ocle_coMics is licensed under the UNLICENSE. See `LICENSE.md` for license information.

## Why do it this way?

The problem of automatic translation has traditionally been that word-for-word machine translation leads to many strange and inaccurate translations that can be confusing, and LLM's simply don't have a large enough context window to translate an entire work if it's long enough. This approach solves the issue by using stateless requests to Ollama by entire textbox groups. In short, the LLM receives an entire phrase or sentence at once to have more context for a higher quality translation, but lacks context of the rest of the work so that it can be handled in chunks. The could potentilly be improved further by including the previous and the next text box in the context, but to maintain compatability this would have to be implemented with a way to calculate how much context length the user's system can handle with the current model.

## Further Considerations

This is an early version of a personal project. It may contain undocumented glitches and bugs.
