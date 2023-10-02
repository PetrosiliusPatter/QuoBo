import json
import os

import weaviate

API_KEY = os.environ.get("API_KEY")


def create_or_update_class(
    client: weaviate.Client, class_name: str, class_definition: dict
):
    present_classes = client.schema.get()
    found = next(x for x in present_classes["classes"] if x["class"] == class_name)
    if found:
        client.schema.update_config(class_name, class_definition)
    else:
        client.schema.create_class(class_definition)


class WeaviateHandler:
    def __init__(self):
        self.client = weaviate.Client(
            url="http://localhost:8080",
            auth_client_secret=weaviate.AuthApiKey(api_key=API_KEY),
        )
        self.setup_schema()

    def setup_schema(self):
        message_class = {
            "class": "Message",
            "description": "A stored message",
            "properties": [
                {
                    "name": "plaintext",
                    "description": "Plain text of the message",
                    "dataType": ["text"],
                }
            ],
        }
        create_or_update_class(self.client, "Message", message_class)
