from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

# Sample keywords
keywords = ["car", "automobile", "vehicle", "truck", "bike", "motorcycle"]

# Convert keywords to TF-IDF vectors
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(keywords)

# Cluster the keywords using K-means
kmeans = KMeans(n_clusters=2)
kmeans.fit(X)

# Print cluster centers
print("Cluster Centers:")
print(vectorizer.inverse_transform(kmeans.cluster_centers_))
