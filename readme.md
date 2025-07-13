What is this?

    It's a personal project to make it easier to automatically translate comics to English. Technically speaking, it should work for translating any text from an image   format into English overlayed on the original image in an html doc.

Why do it this way?

    The problem of automatic translation has traditionally been that word-for-word machine translation leads to many strange and inaccurate translations that can be confusing, and LLM's simply don't have a large enough context window to translate an entire work if it's long enough. This approach solves the issue by using stateless requests to Ollama by entire textbox groups. In short, the LLM receives an entire phrase or sentence at once to have more context for a higher quality translation, but lacks context of the rest of the work so that it can be handled in chunks. The could potentilly be improved further by including the previous and the next text box in the context, but to maintain compatability this would have to be implemented with a way to calculate how much context length the user's system can handle with the current model.
    

It's probably bad and riddled with bugs, but I'm sharing it incase someone else finds it useful. Go wild, use or modify it however you want.
