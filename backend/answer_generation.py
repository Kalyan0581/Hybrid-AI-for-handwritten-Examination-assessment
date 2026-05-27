import PyPDF2
import numpy as np
import faiss
import requests
import json
from sentence_transformers import SentenceTransformer


# -----------------------------------
# 1. EXTRACT TEXT
# -----------------------------------
def extract_text_from_pdf(pdf_path):
    print("📘 Extracting textbook text...")
    reader = PyPDF2.PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text() + "\n"
    print("✅ Text extraction complete")
    return text


# -----------------------------------
# 2. CHUNK TEXT
# -----------------------------------
def chunk_text(text, chunk_size=400, overlap=80):
    print("✂ Chunking textbook...")
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    print(f"✅ Total chunks created: {len(chunks)}")
    return chunks


# -----------------------------------
# 3. BUILD FAISS INDEX
# -----------------------------------
def build_faiss_index(chunks):
    print("🧠 Loading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print("📊 Creating embeddings...")
    embeddings = model.encode(chunks)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(embeddings))

    print("✅ FAISS index ready")
    return index, chunks, model


# -----------------------------------
# 4. RETRIEVE CHUNKS
# -----------------------------------
def retrieve_chunks(question, index, chunks, embed_model, k=5):
    print(f"🔎 Retrieving context for: {question[:40]}...")
    q_embed = embed_model.encode([question])
    distances, indices = index.search(np.array(q_embed), k)

    results = []
    for idx in indices[0]:
        results.append(chunks[idx])

    return results


# -----------------------------------
# 5. MARK-BASED PROMPT
# -----------------------------------
def generate_prompt(question, context, marks):

    if marks is None:
        marks = 5

    if marks <= 2:
        instruction = "Give a very short answer in 2-4 lines."
    elif marks <= 5:
        instruction = "Give a moderate explanation in 6-8 lines."
    elif marks <= 10:
        instruction = "Give a detailed answer with explanation and bullet points."
    else:
        instruction = "Give a comprehensive structured answer with headings."

    prompt = f"""
You are an exam answer generator.

STRICT RULES:
- No extra commentary
- No disclaimers
- No follow-up questions
- Answer according to marks

STYLE RULE:
{instruction}

REFERENCE CONTENT:
{context}

QUESTION:
{question}

FINAL ANSWER:
"""

    return prompt


# -----------------------------------
# 6. ASK OLLAMA (SAFE VERSION)
# -----------------------------------
def ask_ollama(prompt):
    print("🤖 Calling Ollama...")

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )

    if response.status_code != 200:
        raise Exception(f"Ollama error: {response.text}")

    data = response.json()
    print("✅ Ollama response received")
    return data.get("response", "").strip()


# -----------------------------------
# 7. GENERATE ALL ANSWERS
# -----------------------------------
def generate_all_answers(question_json_path, textbook_pdf_path):

    print("📂 Loading questions.json...")
    with open(question_json_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    text = extract_text_from_pdf(textbook_pdf_path)
    chunks = chunk_text(text)
    index, chunks, embed_model = build_faiss_index(chunks)

    final_answers = []

    for q in questions:
        print(f"\n📝 Generating answer for {q['id']}")

        retrieved_chunks = retrieve_chunks(
            q["text"], index, chunks, embed_model
        )

        context = "\n\n".join(retrieved_chunks)
        prompt = generate_prompt(q["text"], context, q["marks"])

        answer = ask_ollama(prompt)

        final_answers.append({
            "id": q["id"],
            "question": q["text"],
            "marks": q["marks"],
            "answer": answer
        })

    print("\n💾 Saving answers.json...")
    with open("answers.json", "w", encoding="utf-8") as f:
        json.dump(final_answers, f, indent=4, ensure_ascii=False)

    print("✅ All answers generated successfully")
    return final_answers
