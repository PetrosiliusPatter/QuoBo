import os
from typing import Union

from fastapi import FastAPI
from sentence_transformers import SentenceTransformer
from torch import Tensor

default_model = "paraphrase-TinyBERT-L6-v2"
model: SentenceTransformer | None = None


def embedder(data: str) -> Tensor | None:
    if model is None:
        return None
    return model.encode([data])[0]


def to_model_path(model_name: str) -> str:
    return "./models/" + model_name


def load_model(model_name: str) -> SentenceTransformer:
    if model is not None:
        return model

    model_path = to_model_path(model_name)
    if not os.path.isfile(model_path + "/config.json"):
        print("Downloading model")
        loaded_model = SentenceTransformer(model_name)
        loaded_model.save(model_path)
    else:
        print("Loading model")
        loaded_model = SentenceTransformer(model_path)
    return loaded_model


model = load_model(default_model)
app = FastAPI()


@app.get("/embedding/{test_str}")
def read_item(test_str: str):
    res = embedder(test_str)
    if res is None:
        return {"error": "model not loaded"}
    return {"item_id": res.tolist()}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}
