from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer

# Sample keywords
keywords = ["car", "automobile", "vehicle", "truck", "bike", "motorcycle"]

# Convert keywords to TF-IDF vectors

vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(keywords)

# Perform DBSCAN clustering
dbscan = DBSCAN(eps=0.5, min_samples=1)
dbscan.fit(X)

# Print clusters
labels = dbscan.labels_
clusters = {}
for i, label in enumerate(labels):
    if label not in clusters:
        clusters[label] = []
    clusters[label].append(keywords[i])

print("Clusters:")
for cluster in clusters.values():
    print(cluster)
