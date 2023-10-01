import json
import os
import time
from typing import Mapping

from chassis.builder import DockerBuilder
from chassisml import ChassisModel
from sentence_transformers import SentenceTransformer


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


def process(data: Mapping[str, str]) -> dict[str, bytes]:
    embedding = model.encode([data["input"]])[0]
    dumped = json.dumps(embedding.tolist())
    return {"embedding": dumped.encode()}


# create chassis model object, add required dependencies, and define metadata
chassis_model = ChassisModel(process_fn=process)
chassis_model.add_requirements(["sentence_transformers"])
chassis_model.metadata.model_name = "MessageEmbedder"
chassis_model.metadata.model_version = "0.0.1"
chassis_model.metadata.add_input(
    key="input",
    accepted_media_types=["text/plain"],
    max_size="10M",
    description="Message to be encoded",
)
chassis_model.metadata.add_output(
    key="embedding",
    media_type="application/json",
    max_size="1M",
    description="Embedding for message",
)

# test model
results = chassis_model.test({"input": "TestInput"})

# build container #
builder = DockerBuilder(chassis_model)
start_time = time.time()
print("Started at ", time.localtime())
res = builder.build_image(name="message-embedder-model", tag="0.0.1", show_logs=True)
end_time = time.time()
print(res)
print(f"Container image built in {(end_time-start_time) / 60} minutes")
