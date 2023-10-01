import json
import os
import time
from typing import Mapping

import chassis.guides as guides
from chassis.builder import DockerBuilder
from chassisml import ChassisModel
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

print("Model loaded")


def process(input_bytes: Mapping[str, str]) -> dict[str, bytes]:
    text = input_bytes["input"]
    encoded = model.encode([text])[0].tolist()

    return {"results": json.dumps({"encoded": encoded}).encode()}


# create chassis model object, add required dependencies, and define metadata
chassis_model = ChassisModel(process_fn=process)
chassis_model.add_requirements(["sentence_transformers"])
chassis_model.metadata.model_name = "MessageEncoder"
chassis_model.metadata.model_version = "0.0.1"
chassis_model.metadata.add_input(
    key="input",
    accepted_media_types=["text/plain"],
    max_size="10M",
    description="Message to be encoded",
)
chassis_model.metadata.add_output(
    key="results",
    media_type="application/json",
    max_size="1M",
    description="Encoded message",
)

# test model
results = chassis_model.test({"input": "TestInput"})
print(results)

# build container #
builder = DockerBuilder(chassis_model)
start_time = time.time()
res = builder.build_image(name="message-encoder-model", tag="0.0.1", show_logs=True)
end_time = time.time()
print(res)
print(f"Container image built in {end_time-start_time} seconds")
