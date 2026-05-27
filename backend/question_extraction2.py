import pdfplumber
import re
import json

PDF_PATH = "qp2.pdf"

MAIN_Q_PATTERN = re.compile(r'^(\d{1,2})[.)]\s+')
SUB_Q_PATTERN = re.compile(r'^(\d{1,2})\s*([a-z])', re.I)


def extract_marks_from_text(text, qid=None):
    nums = re.findall(r'\b\d{1,2}\b', text)
    nums = [int(n) for n in nums if int(n) <= 50]

    # remove question number
    if qid:
        qnum = int(re.findall(r'\d+', qid)[0])
        nums = [n for n in nums if n != qnum]

    if not nums:
        return None

    # if marks like 12 + 3
    if len(nums) > 1:
        return sum(nums)

    return nums[0]


def clean_text(text):
    text = re.sub(r'^\d{1,2}\s*[a-z]?\s*[\.\)]?\s*', '', text, flags=re.I)
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

                if not line:
                    continue

                # -------- SUB QUESTION --------
                m = SUB_Q_PATTERN.match(line)
                if m:

                    if current:
                        if current["marks"] is None:
                            current["marks"] = extract_marks_from_text(
                                current["text"], current["id"]
                            )
                        questions.append(current)

                    qno = m.group(1)
                    sub = m.group(2)

                    current = {
                        "id": f"Q{qno}{sub}",
                        "question_number": int(qno),
                        "sub_question": sub,
                        "text": clean_text(line),
                        "marks": None
                    }

                    continue

                # -------- MAIN QUESTION --------
                m = MAIN_Q_PATTERN.match(line)
                if m:

                    if current:
                        if current["marks"] is None:
                            current["marks"] = extract_marks_from_text(
                                current["text"], current["id"]
                            )
                        questions.append(current)

                    qno = m.group(1)

                    current = {
                        "id": f"Q{qno}",
                        "question_number": int(qno),
                        "sub_question": None,
                        "text": clean_text(line),
                        "marks": 2 if int(qno) <= 10 else None
                    }

                    continue

                # -------- CONTINUATION --------
                if current:
                    current["text"] += " " + clean_text(line)

    # finalize last question
    if current:
        if current["marks"] is None:
            current["marks"] = extract_marks_from_text(current["text"], current["id"])
        questions.append(current)

    return questions


def save_to_json(data, output_path="questions.json"):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    questions = extract_questions(PDF_PATH)
    save_to_json(questions)

    print(f"\n✅ Extracted {len(questions)} questions.")
    print("📁 Saved to questions.json")