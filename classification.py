import sqlite3
import json
import numpy as np
from os.path import basename, exists
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
import os
from random import shuffle
import joblib  # For saving/loading models

CONFIDENCE_HIGH = 0.7
CONFIDENCE_LOW = 0.3

# Load existing labeled data
def load_base_cases():
    """Load base_cases.json or return an empty dictionary if not found."""
    return json.load(open("data/base_cases.json")) if exists("data/base_cases.json") else {}

def save_base_cases(data):
    """Save updated base cases."""
    with open("data/base_cases.json", "w") as f:
        json.dump(data, f, indent=4)

# Retrieve text chunks from the database
def get_text_chunks():
    """Load text chunks from the database and group them by file name."""
    conn = sqlite3.connect('data/pdf_text.db')
    c = conn.cursor()
    c.execute("SELECT file_name, chunk_text FROM pdf_chunks")
    data = c.fetchall()
    conn.close()

    file_chunks = {}
    for file_name, text in data:
        file_chunks.setdefault(basename(file_name.removesuffix(".pdf")), []).append(text)
    
    return file_chunks

# Train a regression model for a single topic
def train_topic_model(topic, base_cases, file_chunks):
    """Train a regression model for a single topic and save it to disk."""
    texts = []
    labels = []

    for file_name, chunks in file_chunks.items():
        texts.append(" ".join(chunks))
        labels.append(1 if file_name in base_cases.get(topic, []) else 0)  # Binary label for the topic

    if sum(labels) == 0:  # Skip training if no data for this topic
        print(f"Skipping training for '{topic}' (No labeled data).")
        return None, None

    vectorizer = TfidfVectorizer(stop_words='english', max_features=5000, ngram_range=(1, 2))
    X = vectorizer.fit_transform(texts)
    y = np.array(labels)

    model = Ridge(alpha=1.0)
    model.fit(X, y)

    # Create the directory if it does not exist
    os.makedirs("models", exist_ok=True)

    # Save model and vectorizer to disk
    joblib.dump(model, f"models/{topic}_model.pkl")
    joblib.dump(vectorizer, f"models/{topic}_vectorizer.pkl")

    return model, vectorizer

# Predict topic score for a single topic
def predict_topic(model, vectorizer, file_chunks):
    """Predict topic relevance for all files using the given model."""
    texts = [" ".join(chunks) for chunks in file_chunks.values()]
    X = vectorizer.transform(texts)
    scores = model.predict(X)

    return {file_name: score for file_name, score in zip(file_chunks.keys(), scores)}

# Assign topics dynamically based on predictions
def validate_and_assign_topic(topic, base_cases, file_chunks, predictions):
    """Validate predictions for a single topic and update base cases."""
    for file_name, score in predictions.items():
        if file_name in base_cases.get(topic, []):
            continue  # Skip already labeled files

        if score > CONFIDENCE_HIGH:
            print(f"{file_name} -> Automatically assigned '{topic}' (Confidence: {score:.2f})")
            base_cases.setdefault(topic, []).append(file_name)

        elif CONFIDENCE_LOW < score <= CONFIDENCE_HIGH:
            # Automatically assign if similar files already have this topic
            similar_files = find_similar_files(file_chunks, file_name, topic)
            suggested_topics = [t for t, files in base_cases.items() if any(f in similar_files for f in files)]

            if topic in suggested_topics:
                print(f"{file_name} -> Assigned '{topic}'. Score: {score}.")
                base_cases.setdefault(topic, []).append(file_name)
            # else:
            #     corrected_topic = input(f"Assign topic '{topic}' to '{file_name}' ({score})? (y/n): ").strip().lower()
            #     if corrected_topic == "y":
            #         base_cases.setdefault(topic, []).append(file_name)

        save_base_cases(base_cases)

    return base_cases

# Find similar files using cosine similarity
def find_similar_files(file_chunks, target_file, topic):
    """Find similar files to assist in topic validation."""
    model_path = f"models/{topic}_vectorizer.pkl"
    if not exists(model_path):
        return []

    vectorizer = joblib.load(model_path)

    texts = [" ".join(chunks) for chunks in file_chunks.values()]
    file_list = list(file_chunks.keys())
    X = vectorizer.transform(texts)

    if target_file not in file_list:
        return []

    target_index = file_list.index(target_file)
    target_vector = X[target_index]

    similarities = np.dot(X, target_vector.T).toarray().flatten()
    similar_indices = np.argsort(similarities)[::-1][1:6]  # Top 5 excluding itself
    return [file_list[i] for i in similar_indices]

def exclude_files(path, all_topics):
    executed_topics = {os.path.basename(name).split("_")[0] for name in os.listdir(path)}
    return list(set(all_topics) - set(executed_topics))

# Main pipeline (Processing one topic at a time)
def main():
    print("Starting Optimized Multi-Topic Classification...")

    base_cases = load_base_cases()
    file_chunks = get_text_chunks()
    randomized_topics = exclude_files(os.getcwd() + "\\models\\", list(base_cases.keys()))
    # Remove keys that do not exist in topics
    base_cases = {k: v for k, v in base_cases.items() if k in randomized_topics}
    shuffle(randomized_topics)

    for topic in randomized_topics:
        print(f"\nProcessing Topic: {topic}")

        print("Training the model for the current topic...")
        model, vectorizer = train_topic_model(topic, base_cases, file_chunks)

        if model is None:
            continue  # Skip to next topic if no data for training

        print("Predicting topic scores for all files...")
        predictions = predict_topic(model, vectorizer, file_chunks)

        print("Validating and assigning topics...")
        base_cases = validate_and_assign_topic(topic, base_cases, file_chunks, predictions)

        print("Freeing up memory...")
        del model, vectorizer  # Ensure memory is cleared

    print("\nTopic Classification Completed!")

if __name__ == "__main__":
    main()
