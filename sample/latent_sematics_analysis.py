from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

# Sample keywords
keywords = ["car", "automobile", "vehicle", "truck", "bike", "motorcycle"]

# Convert keywords to TF-IDF vectors
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(keywords)

# Apply Latent Semantic Analysis (LSA)
lsa = TruncatedSVD(n_components=2)
X_lsa = lsa.fit_transform(X)

# Print LSA components
print("LSA Components:")
print(lsa.components_)
#check sample