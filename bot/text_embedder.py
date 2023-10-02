import os
from typing import Union

from sentence_transformers import SentenceTransformer
from torch import Tensor

default_model = "paraphrase-TinyBERT-L6-v2"


def to_model_path(model_name: str) -> str:
    return "./models/" + model_name


def load_model(model_name: str) -> SentenceTransformer:
    model_path = to_model_path(model_name)
    if not os.path.isfile(model_path + "/config.json"):
        print("Downloading model")
        loaded_model = SentenceTransformer(model_name)
        loaded_model.save(model_path)
    else:
        print("Loading model")
        loaded_model = SentenceTransformer(model_path)
    return loaded_model


class TextEmbedder:
    model: SentenceTransformer

    def __init__(self, model_name: str = default_model):
        self.model = load_model(model_name)

    def embed(self, data: str) -> Tensor:
        return self.model.encode([data])[0]
