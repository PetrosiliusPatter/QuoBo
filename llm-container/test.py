import os

from sentence_transformers import SentenceTransformer
from torch import Tensor


def to_model_path(model_name: str) -> str:
    return "./models/" + model_name


def load_model(model_name: str) -> SentenceTransformer:
    if not os.path.isfile(to_model_path(model_name) + "/config.json"):
        print("Downloading model")
        model = SentenceTransformer(model_name)
        model.save(to_model_path(model_name))
    else:
        model = SentenceTransformer(to_model_path(model_name))

    return model


default_model = "paraphrase-TinyBERT-L6-v2"
model = load_model(default_model)


# define process function that will serve as our inference function
def process(input_bytes: str) -> Tensor:
    return model.encode([input_bytes])[0]


if __name__ == "__main__":
    test = process("TestInput")
