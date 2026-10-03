from payments_rag.retrieval import retrieve_chunks


def test_retrieval_prefers_relevant_payment_chunk() -> None:
    chunks = [
        "Authorization checks whether the card is valid before processing.",
        "Settlement moves funds after a payment is processed and reconciled.",
        "A dispute happens when a customer challenges a transaction.",
    ]

    results = retrieve_chunks("What is settlement in payments?", chunks, top_k=1)

    assert results[0][0] == "Settlement moves funds after a payment is processed and reconciled."
