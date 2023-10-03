import random
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

from qdrant_client import QdrantClient, models
from qdrant_client.conversions.common_types import Record
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

    def to_tsv(self) -> str:
        return "\t".join(
            [
                self.group_id,
                str(self.message_id),
                self.quote_text,
                str(self.account_id),
                self.post_date,
                self.last_quoted,
            ]
        )


@dataclass
class QuoteWithId(Quote):
    id: str


# Receives a dict from the database and converts it to a QuoteWithId object
def parse_db_res(id: str, res: dict) -> QuoteWithId:
    return QuoteWithId(id=id, **res)


def distance_to_weight(distance: float) -> float:
    return distance**2


class DBHandler:
    def __init__(self):
        self.client = QdrantClient("localhost", port=6333)
        self.text_embedder = TextEmbedder()
        self.setup_schema()

    def setup_schema(self):
        present_collections = self.client.get_collections()
        quote_collection = next(
            (x for x in present_collections.collections if x.name == "Quote"), None
        )
        if quote_collection:
            return

        vector_size = self.text_embedder.model.get_sentence_embedding_dimension()
        self.client.create_collection(
            collection_name="Quote",
            vectors_config=models.VectorParams(
                size=vector_size, distance=models.Distance.COSINE, on_disk=True
            ),
        )

    def clear_db(self):
        self.client.delete_collection(collection_name="Quote")
        self.setup_schema()

    def get_all_entries(self) -> list[QuoteWithId]:
        out: list[Quote] = []
        offset = "initial"
        while offset:
            curr_batch = self.client.scroll(
                collection_name="Quote",
                with_payload=True,
                offset=None if offset == "initial" else offset,
            )
            offset = curr_batch[1]
            out.extend([parse_db_res(x.id, x.payload) for x in curr_batch[0]])
        return out

    def find_quote(self, account_id: int, quote_text: str) -> QuoteWithId | None:
        found_quote_points = self.client.scroll(
            collection_name="Quote",
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="quote_text",
                        match=models.MatchValue(value=quote_text),
                    ),
                    models.FieldCondition(
                        key="account_id",
                        match=models.MatchValue(value=account_id),
                    ),
                ]
            ),
            limit=1,
        )[0]

        if len(found_quote_points) == 0:
            return None

        existing_quote = parse_db_res(
            found_quote_points[0].id, found_quote_points[0].payload
        )
        return existing_quote

    def find_quote_by_message_id(self, message_id: int) -> QuoteWithId | None:
        found_quote_points = self.client.scroll(
            collection_name="Quote",
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="message_id",
                        match=models.MatchValue(value=message_id),
                    )
                ]
            ),
            limit=1,
        )[0]

        if len(found_quote_points) == 0:
            return None

        existing_quote = parse_db_res(
            found_quote_points[0].id, found_quote_points[0].payload
        )
        return existing_quote

    def delete_quote_by_id(self, quote_id: str):
        self.client.delete(
            collection_name="Quote",
            points_selector=models.PointIdsList(
                points=[quote_id],
            ),
        )

    def save_quotes(
        self,
        new_quotes: list[Quote],
    ):
        ids = [str(uuid.uuid4()) for _ in new_quotes]
        payloads = [asdict(x) for x in new_quotes]
        vectors = [
            x.tolist()
            for x in self.text_embedder.embed([x.quote_text for x in new_quotes])
        ]
        self.client.upsert(
            collection_name="Quote",
            points=models.Batch(
                ids=ids,
                payloads=payloads,
                vectors=vectors,
            ),
        )

    def quote_for_user_by_query(
        self, account_id: int, query: str
    ) -> QuoteWithId | None:
        query_embedding = self.text_embedder.embed([query])[0]

        found_quote_points = self.client.search(
            collection_name="Quote",
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="account_id",
                        match=models.MatchValue(value=account_id),
                    )
                ],
                must_not=[
                    models.FieldCondition(
                        key="quote_text",
                        match=models.MatchValue(value=query),
                    )
                ],
            ),
            search_params=models.SearchParams(hnsw_ef=128, exact=False),
            query_vector=query_embedding.tolist(),
            limit=5,
        )

        choices = [(x, x.score) for x in found_quote_points]

        print(f"Found {len(choices)} quotes for query '{query}':")
        print("\n".join([str((x[0].payload["quote_text"], x[1])) for x in choices]))

        return self._choose_quote(choices)

    def pseudo_random_quote_for_user(self, account_id: int) -> QuoteWithId | None:
        found_quote_points = self.client.scroll(
            collection_name="Quote",
            with_payload=True,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="account_id",
                        match=models.MatchValue(value=account_id),
                    )
                ]
            ),
        )[0]
        choices = [[x, 1] for x in found_quote_points]
        return self._choose_quote(choices)

    def _choose_quote(
        self, found_quotes: list[tuple[Record, float]]
    ) -> QuoteWithId | None:
        if len(found_quotes) == 0:
            return None

        if len(found_quotes) == 1:
            selected_entry = found_quotes[0][0]
        else:
            choices = [entry[0] for entry in found_quotes]
            weights = [entry[1] for entry in found_quotes]

            selected_entry = random.choices(choices, weights)[0]

        selected_quote = parse_db_res(selected_entry.id, selected_entry.payload)

        self.client.set_payload(
            collection_name="Quote",
            payload={
                "last_quoted": datetime_to_rfc3339(datetime.now().astimezone()),
            },
            points=[selected_quote.id],
        )
        return selected_quote
