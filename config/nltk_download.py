import nltk
def download_nltk():
    print("Downloading NLTK resources...")
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('punkt_tab')
    print("NLTK resources downloaded.")

download_nltk()