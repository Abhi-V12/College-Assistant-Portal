"""
Run this FIRST after `pip install -r requirements.txt`, before starting the
server, to confirm sentence-transformers + faiss installed correctly and the
embedding model downloads/loads. Isolates any install problem here instead
of inside a live API call.

Usage:
    python -m app.test_rag_setup
"""

import time

print("Loading sentence-transformers model (first run downloads ~80MB from Hugging Face)...")
t0 = time.time()
from sentence_transformers import SentenceTransformer  # noqa: E402

model = SentenceTransformer("all-MiniLM-L6-v2")
print(f"Model loaded in {time.time() - t0:.1f}s")

import faiss  # noqa: E402
import numpy as np  # noqa: E402

questions = [
    "how much is the annual tuition fee",
    "what are the hostel mess timings",
    "when do semester exams start",
]
query = "tell me about hostel food timings"

embeddings = np.asarray(model.encode(questions, normalize_embeddings=True), dtype="float32")
query_embedding = np.asarray(model.encode([query], normalize_embeddings=True), dtype="float32")

index = faiss.IndexFlatIP(embeddings.shape[1])
index.add(embeddings)
scores, idx = index.search(query_embedding, 1)

print(f"\nQuery:       {query!r}")
print(f"Best match:  {questions[idx[0][0]]!r}")
print(f"Score:       {scores[0][0]:.3f}")
print("\nIf that match makes sense (hostel food -> hostel mess timings), "
      "your embeddings + FAISS setup is working correctly. Start the real "
      "server next.")
