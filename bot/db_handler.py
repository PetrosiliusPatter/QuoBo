import json
import random
from dataclasses import dataclass
from datetime import datetime

import weaviate
from utils import datetime_to_weaviate_timestamp


@dataclass
class Quote:
    group_id: str
    message_id: int
    quote_text: str
    account_id: int
    post_date: str
    last_quoted: str


class WeaviateHandler:
    def __init__(self, api_key: str):
        self.client = weaviate.Client(
            url="http://localhost:8080",
            auth_client_secret=weaviate.AuthApiKey(api_key=api_key),
        )
        self.setup_schema()

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
                    ],
                }
            ]
        }
        self.client.schema.create(schema)

    def find_quote(self, account_id: int, quote_text: str) -> Quote | None:
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
            .with_limit(1)
            .do()
        )["data"]["Get"]["Quote"]

        if len(found_quotes) == 0:
            return None

        existing_quote: Quote = Quote(**found_quotes[0])
        return existing_quote

    def save_quote(
        self,
        new_quote: Quote,
    ):
        self.client.data_object.create(
            {
                "group_id": new_quote.group_id,
                "message_id": new_quote.message_id,
                "quote_text": new_quote.quote_text,
                "account_id": new_quote.account_id,
                "post_date": new_quote.post_date,
                "last_quoted": new_quote.last_quoted,
            },
            "Quote",
        )

    def pseudo_random_quote_for_user(
        self,
        account_id: int,
    ) -> Quote | None:
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
                    "operator": "Equal",
                    "path": ["account_id"],
                    "valueInt": account_id,
                }
            )
            .with_additional(["id"])
            .do()
        )["data"]["Get"]["Quote"]

        if len(found_quotes) == 0:
            return None

        if len(found_quotes) == 1:
            selected_entry = found_quotes[0]
        else:
            max_quote_index = round(0.3 * len(found_quotes))
            selected_entry = found_quotes[random.randrange(0, max_quote_index)]

        uuid = selected_entry["_additional"]["id"]
        del selected_entry["_additional"]

        selected_quote = Quote(**selected_entry)

        self.client.data_object.update(
            uuid=uuid,
            class_name="Quote",
            data_object={
                "last_quoted": datetime_to_weaviate_timestamp(datetime.now()),
            },
        )

        return selected_quote
