
import unittest

from src import ll_ocl_comics

class TestRemoveBetweenAnchors(unittest.TestCase):
    def test_remove_between_anchors(self):
        text = "<think> I think I am string. </think> Strong!"
        anchor = "think"
        self.assertEqual(ll_ocl_comics.remove_between_anchors(text, anchor), "Strong!")

    def test_llm_response(self):
        text = """ <think> Okay, the user provided the Japanese text "俺は" and wants it translated into English. Let me start by breaking down the components. "俺" is a first-person pronoun, typically used by males to refer to themselves. It can be translated as "I" or "me," but the context here is crucial. Since it's part of a sentence like "俺は..." (I am...), the translation should capture the speaker's identity. Now, considering the user's instruction to avoid censorship and provide a direct translation, I need to ensure that the term "俺" is accurately rendered. In English, "I" is the most straightforward equivalent. However, sometimes "me" is used in certain contexts, like "Me, I..." but that's less common. The user might be looking for a natural-sounding translation that's commonly used in comics or manga, so "I" is the safest bet here. Wait, but sometimes in manga, characters might use "me" for emphasis or a more casual tone. For example, "Me, I'm going to fight!" But without more context, it's hard to say. The original text is just "俺は," which is a fragment. Translating it as "I am" makes sense if it's part of a longer sentence. However, since the user only provided "俺は," maybe they want the direct translation without adding extra words. Let me check if there's any nuance I'm missing. "俺" can sometimes imply a more rugged or masculine persona, but in translation, that's usually conveyed through context rather than the pronoun itself. So "I" is still appropriate. Another angle: sometimes in English, people use "me" for a more colloquial or informal feel. But again, without context, it's better to stick with "I." Also, considering the user's instruction to not censor, there's no sensitive content here, so "I" is fine. Hmm, maybe the user is looking for a direct translation where "俺" becomes "I" and "は" is the topic marker, which in English might not translate directly. So the translation would be "I am" but since the original is just "俺は," maybe it's part of a larger sentence. However, the user only provided this fragment. In conclusion, the most accurate and natural translation here is "I am" or just "I," depending on the context. Since the user might be using this in a sentence like "I am the hero," translating it as "I am" makes sense. But if it's just the pronoun, "I" is sufficient. The user might need to add more context, but based on the given text, "I" is the best choice. </think> I am """
        anchor = "think"
        self.assertEqual(ll_ocl_comics.remove_between_anchors(text, anchor), "I am")
