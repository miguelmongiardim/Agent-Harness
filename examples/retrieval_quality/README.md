# Retrieval Quality Demo

This directory is reserved for the V5 local-first retrieval quality demo.

The runnable demo lands after the retrieval CLI, local index lifecycle, hybrid
query, scorecard, and policy-filtered context-manifest slices are implemented.
The planned golden path remains local-first: lexical retrieval in the base
install, optional local dense retrieval through FastEmbed and Qdrant, loopback
developer infrastructure only, and no remote embeddings or cloud vector
services.

The final demo will include local documents, policy-filtering examples,
expected retrieval artifacts, and scorecard fixtures.
