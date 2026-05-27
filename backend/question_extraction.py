import pdfplumber
import re
import json
import os

MAIN_Q_PATTERN = re.compile(r'^(\d{1,2})\s+(?=[A-Z])')
SUB_Q_PATTERN = re.compile(r'^(\d{1,2})\s*(?:\(\s*([a-z])\s*\)|([a-z])\.)\s+', re.I)

def extract_marks_from_text(text):
    nums = re.findall(r'\((\d+)\)', text)
    nums = [int(n) for n in nums if int(n) <= 50]
    return max(nums) if nums else None

def is_noise(line):
    return bool(re.match(r'^(page|part|\*+|co\d+|\(k\d+\))', line.lower()))

def is_table_row(line):
    return bool(re.match(r'^[0-9?\s]+(yes|no)?$', line.lower()))

def clean_text(text):
    text = re.sub(r'\(k\d+\)', '', text, flags=re.I)
    text = re.sub(r'co\d+', '', text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()

def extract_questions(pdf_path):
    questions = []
    current = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for raw in text.split("\n"):
                line = raw.strip()
                if not line or is_noise(line):
                    continue

                # -------- SUB QUESTION --------
                m = SUB_Q_PATTERN.match(line)
                if m:
                    if current:
                        if current["marks"] is None:
                            current["marks"] = extract_marks_from_text(current["text"])
                        questions.append(current)

                    qno = int(m.group(1))
                    sub = m.group(2) or m.group(3)

                    current = {
                        "id": f"Q{qno}{sub}",
                        "question_number": qno,
                        "sub_question": sub,
                        "text": clean_text(line),
                        "marks": None
                    }
                    continue

                # -------- MAIN QUESTION --------
                m = MAIN_Q_PATTERN.match(line)
                if m and any(c.isalpha() for c in line):
                    if current:
                        if current["marks"] is None:
                            current["marks"] = extract_marks_from_text(current["text"])
                        questions.append(current)

                    qno = int(m.group(1))

                    current = {
                        "id": f"Q{qno}",
                        "question_number": qno,
                        "sub_question": None,
                        "text": clean_text(line),
                        "marks": 2 if qno <= 10 else None
                    }
                    continue

                # -------- CONTINUATION --------
                if current:
                    current["text"] += " " + (line if is_table_row(line) else clean_text(line))

    # finalize last question
    if current:
        if current["marks"] is None:
            current["marks"] = extract_marks_from_text(current["text"])
        questions.append(current)

    return questions


def save_to_json(data, output_path="questions.json"):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    PDF_PATH = "qp1.pdf"

    questions = extract_questions(PDF_PATH)
    save_to_json(questions)

    print(f"\n✅ Extracted {len(questions)} questions.")
    print("📁 Saved to questions.json")
