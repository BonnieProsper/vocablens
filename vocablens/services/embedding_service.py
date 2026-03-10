import numpy as np
from openai import OpenAI


class EmbeddingService:

    def __init__(self):
        self.client = OpenAI()

    def embed(self, text: str):

        result = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )

        return np.array(result.data[0].embedding)

    def similarity(self, a, b):

        return np.dot(a, b) / (
            np.linalg.norm(a) * np.linalg.norm(b)
        )