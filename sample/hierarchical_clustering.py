from scipy.cluster.hierarchy import dendrogram, linkage
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import TfidfVectorizer

# Sample keywords
keywords = ["car", "automobile", "vehicle", "truck", "bike", "motorcycle"]

# Convert keywords to TF-IDF vectors
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(keywords)

# Perform hierarchical clustering
Z = linkage(X.toarray(), 'ward')

# Plot dendrogram
plt.figure(figsize=(8, 5))
dendrogram(Z, labels=keywords)
plt.title("Hierarchical Clustering Dendrogram")
plt.xlabel("Keywords")
plt.ylabel("Distance")
plt.show()
