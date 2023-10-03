import json
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import weaviate
from text_embedder import TextEmbedder
from utils import datetime_to_rfc3339


@dataclass
class Quote:
    group_id: str
    message_id: int
    quote_text: str
    account_id: int
    post_date: str
    last_quoted: str


@dataclass
class QuoteWithId(Quote):
    id: str


def parse_db_res(res) -> QuoteWithId:
    return QuoteWithId(
        group_id=res["group_id"],
        message_id=res["message_id"],
        quote_text=res["quote_text"],
        account_id=res["account_id"],
        post_date=res["post_date"],
        last_quoted=res["last_quoted"],
        id=res["_additional"]["id"],
    )


def distance_to_weight(distance: float) -> float:
    return distance**2


class WeaviateHandler:
    def __init__(self, api_key: str):
        self.client = weaviate.Client(
            url="http://localhost:8080",
            auth_client_secret=weaviate.AuthApiKey(api_key=api_key),
        )
        self.setup_schema()
        self.text_embedder = TextEmbedder()
        self.recalc_embeddings()

    def setup_schema(self):
        schema = self.client.schema.get()
        if len(schema["classes"]) != 0:
            print(
                "Some schema has already been generated. Skipping schema setup.\n Present schema is: ",
                schema,
            )
            return

        schema = {
            "classes": [
                {
                    "class": "Quote",
                    "description": "A stored quote",
                    "vectorizer": "none",
                    "properties": [
                        {
                            "name": "group_id",
                            "description": "Group ID",
                            "dataType": ["text"],
                        },
                        {
                            "name": "message_id",
                            "description": "Message ID",
                            "dataType": ["int"],
                        },
                        {
                            "name": "quote_text",
                            "description": "The actual quote",
                            "dataType": ["text"],
                        },
                        {
                            "name": "account_id",
                            "description": "Account ID",
                            "dataType": ["int"],
                        },
                        {
                            "name": "post_date",
                            "description": "Date of posting",
                            "dataType": ["date"],
                        },
                        {
                            "name": "last_quoted",
                            "description": "Date of last quoting",
                            "dataType": ["date"],
                        },
                        {
                            "name": "model_used",
                            "description": "Name of the model used for embedding",
                            "dataType": ["text"],
                            "tokenization": "word",
                        },
                    ],
                }
            ]
        }
        self.client.schema.create(schema)

    def recalc_embeddings(self):
        quotes_to_recalc = (
            self.client.query.get(
                "Quote",
                ["quote_text", "model_used"],
            )
            .with_additional(["id"])
            .with_where(
                {
                    "operator": "NotEqual",
                    "path": ["model_used"],
                    "valueText": self.text_embedder.model_name,
                }
            )
            .do()
        )["data"]["Get"]["Quote"]

        print("Current model", self.text_embedder.model_name)
        print("Was ne dumme scheise..", [x["model_used"] for x in quotes_to_recalc])

        print(f"Found {len(quotes_to_recalc)} quotes to recalculate.")

        quote_ids: list[str] = [x["_additional"]["id"] for x in quotes_to_recalc]
        quote_texts: list[str] = [x["quote_text"] for x in quotes_to_recalc]
        recalced_embeddings = self.text_embedder.embed([x[1] for x in quote_texts])

        for i, quote_id in enumerate(quote_ids):
            self.client.data_object.update(
                uuid=quote_id,
                class_name="Quote",
                data_object={
                    "model_used": self.text_embedder.model_name,
                },
                vector=recalced_embeddings[i],
            )

    def find_quote(self, account_id: int, quote_text: str) -> QuoteWithId | None:
        found_quotes = (
            self.client.query.get(
                "Quote",
                [
                    "group_id",
                    "message_id",
                    "quote_text",
                    "account_id",
                    "post_date",
                    "last_quoted",
                ],
            )
            .with_where(
                {
                    "operator": "And",
                    "operands": [
                        {
                            "path": ["quote_text"],
                            "operator": "Equal",
                            "valueText": quote_text,
                        },
                        {
                            "path": ["account_id"],
                            "operator": "Equal",
                            "valueInt": account_id,
                        },
                    ],
                }
            )
            .with_additional(["id"])
            .with_limit(1)
            .do()
        )["data"]["Get"]["Quote"]

        if len(found_quotes) == 0:
            return None

        existing_quote = parse_db_res(found_quotes[0])
        return existing_quote

    def find_quote_by_message_id(self, message_id: int) -> QuoteWithId | None:
        found_quotes = (
            self.client.query.get(
                "Quote",
                [
                    "group_id",
                    "message_id",
                    "quote_text",
                    "account_id",
                    "post_date",
                    "last_quoted",
                ],
            )
            .with_additional(["id"])
            .with_where(
                {
                    "path": ["message_id"],
                    "operator": "Equal",
                    "valueInt": message_id,
                },
            )
            .with_limit(1)
            .do()
        )["data"]["Get"]["Quote"]

        if len(found_quotes) == 0:
            return None

        existing_quote = parse_db_res(found_quotes[0])
        return existing_quote

    def delete_quote_by_id(self, quote_id: str):
        self.client.data_object.delete(uuid=quote_id, class_name="Quote")

    def save_quote(
        self,
        new_quote: Quote,
    ):
        quote_embedding = self.text_embedder.embed(new_quote.quote_text)
        self.client.data_object.create(
            {
                "group_id": new_quote.group_id,
                "message_id": new_quote.message_id,
                "quote_text": new_quote.quote_text,
                "account_id": new_quote.account_id,
                "post_date": new_quote.post_date,
                "last_quoted": new_quote.last_quoted,
                "model_used": self.text_embedder.model_name,
            },
            "Quote",
            vector=quote_embedding,
        )

    def quote_for_user_by_query(
        self, account_id: int, query: str
    ) -> QuoteWithId | None:
        query_embedding = self.text_embedder.embed([query])[0]
        found_quotes = (
            self.client.query.get(
                "Quote",
                [
                    "group_id",
                    "message_id",
                    "quote_text",
                    "account_id",
                    "post_date",
                    "last_quoted",
                ],
            )
            .with_additional(["id", "distance"])
            .with_where(
                {
                    "operator": "Equal",
                    "path": ["account_id"],
                    "valueInt": account_id,
                }
            )
            .with_near_vector({"vector": query_embedding.tolist()})
            .with_limit(10)
            .do()
        )["data"]["Get"]["Quote"]

        quote_options = [
            (x, x["_additional"]["distance"])
            for x in found_quotes
            if x["quote_text"] != query
        ]

        print(f"Found {len(quote_options)} quotes for query '{query}':")
        print("\n".join([str((x[1], x[0]["quote_text"])) for x in quote_options]))

        return self._choose_quote(quote_options)

    def pseudo_random_quote_for_user(self, account_id: int) -> QuoteWithId | None:
        print("Searching for pseudo-random quote for user ", account_id)
        found_quotes = (
            self.client.query.get(
                "Quote",
                [
                    "group_id",
                    "message_id",
                    "quote_text",
                    "account_id",
                    "post_date",
                    "last_quoted",
                ],
            )
            .with_additional(["id"])
            .with_where(
                {
                    "operator": "Equal",
                    "path": ["account_id"],
                    "valueInt": account_id,
                }
            )
            .do()
        )["data"]["Get"]["Quote"]
        return self._choose_quote([[x, 1] for x in found_quotes])

    def _choose_quote(
        self, found_quotes: list[tuple[Any, float]]
    ) -> QuoteWithId | None:
        if len(found_quotes) == 0:
            return None

        if len(found_quotes) == 1:
            selected_entry = found_quotes[0][0]
        else:
            choices = [entry[0] for entry in found_quotes]
            distances = [entry[1] for entry in found_quotes]

            print("Distances: ", distances)
            offset = max(distances)
            weights = [distance_to_weight(offset - d) for d in distances]
            print("Wheights: ", weights)

            selected_entry = random.choices(choices, weights)[0]

        selected_quote = parse_db_res(selected_entry)

        self.client.data_object.update(
            uuid=selected_quote.id,
            class_name="Quote",
            data_object={
                "last_quoted": datetime_to_rfc3339(datetime.now().astimezone()),
            },
        )

        return selected_quote
