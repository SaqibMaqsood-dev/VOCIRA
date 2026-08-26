from pinecone import Pinecone
from rag_engine.config import PINECONE_API_KEY

pc = Pinecone(api_key=PINECONE_API_KEY)
for name in pc.list_indexes().names():
    stats = pc.Index(name).describe_index_stats()
    print(f"{name}: {stats.get('total_vector_count', 0)} vectors")