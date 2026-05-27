import numpy as np
import requests
from collections import Counter
from sentence_transformers import SentenceTransformer, util
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LinearRegression

# --------------------------------------------------
# EMBEDDING MODEL
# --------------------------------------------------
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# --------------------------------------------------
# STOP WORDS
# --------------------------------------------------
STOP_WORDS = {
    "is","am","are","was","were","be","been","a","an","the",
    "and","or","but","to","of","in","on","for","with","that",
    "this","it","as","by","from","at","which","when","while"
}

# --------------------------------------------------
# PREPROCESS
# --------------------------------------------------
def preprocess(text):
    return " ".join(
        w for w in text.lower().split()
        if w not in STOP_WORDS
    )

# --------------------------------------------------
# AUTOMATIC CONCEPT EXTRACTION
# --------------------------------------------------
def extract_concepts(answer_key, top_k=5):
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 3)
    )
    X = vectorizer.fit_transform([answer_key])
    scores = X.toarray()[0]
    features = vectorizer.get_feature_names_out()

    ranked = sorted(
        zip(features, scores),
        key=lambda x: x[1],
        reverse=True
    )

    return [phrase for phrase, _ in ranked[:top_k]]

# --------------------------------------------------
# SCORING METRICS
# --------------------------------------------------
def semantic_similarity(a, b):
    ea = embedder.encode(a, convert_to_tensor=True)
    eb = embedder.encode(b, convert_to_tensor=True)
    return util.cos_sim(ea, eb).item()

def concept_coverage(answer, concepts, clean_key, semantic_sim, threshold=0.45):
    # 🔹 If answers are semantically identical, full coverage
    if semantic_sim >= 0.95:
        return 1.0

    if not concepts:
        return 0.0

    ans_emb = embedder.encode(answer, convert_to_tensor=True)
    covered = 0

    for c in concepts:
        c_emb = embedder.encode(c, convert_to_tensor=True)
        if util.cos_sim(c_emb, ans_emb).item() >= threshold:
            covered += 1

    return covered / len(concepts)

def length_score(words, max_marks):
    actual = len(words)

    # 🔹 No length penalty for short questions
    if max_marks <= 3:
        return 1.0 if actual >= 5 else 0.6

    ideal_words = max_marks * 15
    ratio = actual / ideal_words

    if ratio < 0.5:
        return 0.4
    elif ratio <= 1.2:
        return 1.0
    elif ratio <= 1.5:
        return 0.8
    else:
        return 0.6
    
def clarity_score(words):
    freq = Counter(words)
    repeats = sum(1 for v in freq.values() if v > 2)
    return 1.0 if repeats == 0 else 0.7 if repeats <= 2 else 0.4

# --------------------------------------------------
# ML MODEL (REGRESSION)
# --------------------------------------------------
regressor = LinearRegression()

X_train = np.array([
    [0.9, 0.8, 1.0, 1.0],
    [0.6, 0.5, 0.8, 0.7],
    [0.3, 0.2, 0.6, 0.5],
    [0.1, 0.0, 0.4, 0.4]
])
y_train = np.array([9.5, 6.5, 4.0, 2.0])

regressor.fit(X_train, y_train)

# --------------------------------------------------
# LLaMA-3 COMMENT GENERATION (OLLAMA)
# --------------------------------------------------
def generate_comment_llama(question, semantic, coverage, length, clarity, score, max_marks):
    prompt = f"""
You are a university examiner.

Question:
{question}

Maximum Marks: {max_marks}

Evaluation Metrics:
- Semantic similarity: {semantic:.2f}
- Concept coverage: {coverage:.2f}
- Length adequacy (w.r.t marks): {length:.2f}
- Clarity score: {clarity:.2f}

Final Score: {score:.1f}/{max_marks}

Briefly justify the marks awarded.
Mention strengths, missing concepts, and length appropriateness.
Keep the explanation concise and academic.
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json()["response"].strip()

# --------------------------------------------------
# EVALUATION PIPELINE
# --------------------------------------------------
def evaluate(question, answer_key, student_answer, max_marks):
    clean_key = preprocess(answer_key)
    clean_ans = preprocess(student_answer)
    words = clean_ans.split()

    concepts = extract_concepts(clean_key)

    semantic = semantic_similarity(clean_key, clean_ans)
    coverage = concept_coverage(
    clean_ans,
    concepts,
    clean_key,
    semantic
)
    length = length_score(words, max_marks)
    clarity = clarity_score(words)
    
    if semantic < 0.35 and coverage < 0.2:
        score = 0.0
        comment = "Answer is completely unrelated to the question. No relevant concepts found."
        
        return {
            "Question": question,
            "Max Marks": max_marks,
            "Score": 0.0,
            "Semantic Similarity": round(semantic, 3),
            "Concept Coverage": round(coverage, 3),
            "Length Score": round(length, 3),
            "Clarity Score": round(clarity, 3),
            "AI Explanation": comment
        }

    features = np.array([[semantic, coverage, length, clarity]])
    raw_score = regressor.predict(features)[0]

    # Scale score to max marks
    score = (raw_score / 10) * max_marks
    score = max(0, min(max_marks, score))

    comment = generate_comment_llama(
        question, semantic, coverage, length, clarity, score, max_marks
    )

    return {
        "Question": question,
        "Max Marks": max_marks,
        "Score": round(score, 2),
        "Semantic Similarity": round(semantic, 3),
        "Concept Coverage": round(coverage, 3),
        "Length Score": round(length, 3),
        "Clarity Score": round(clarity, 3),
        "AI Explanation": comment
    }

# --------------------------------------------------