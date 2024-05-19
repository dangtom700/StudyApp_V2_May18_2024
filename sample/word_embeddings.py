import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Sample keywords
keywords = ["car", "automobile", "vehicle", "truck", "bike", "motorcycle"]

# Sample word embeddings (for demonstration purpose)
word_embeddings = {}
for keyword in keywords:
    word_embeddings[keyword] = np.random.rand(100)  # Random 100-dimensional vectors

# Cluster using cosine similarity
clusters = {}
for keyword1 in keywords:
    if keyword1 not in clusters:
        clusters[keyword1] = [keyword1]
    for keyword2 in keywords:
        if keyword1 != keyword2:
            similarity = cosine_similarity([word_embeddings[keyword1]], [word_embeddings[keyword2]])[0][0]
            if similarity > 0.5:  # Threshold for similarity
                clusters[keyword1].append(keyword2)

print("Clusters:")
for cluster in clusters.values():
    print(cluster)
