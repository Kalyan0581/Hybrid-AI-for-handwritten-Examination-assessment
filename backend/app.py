from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import traceback
from question_extraction2 import extract_questions, save_to_json
from answer_generation import generate_all_answers
from answer_extraction2 import extract_answer_script
import json


app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "./uploads"
TEXTBOOK_PATH = "D:/AI_Evaluator/backend/books/Recommender-Systems.pdf"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/upload-question-paper", methods=["POST"])
def upload_question_paper():

    print("\n==============================")
    print("📥 New Question Paper Uploaded")
    print("==============================")

    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]

        if file.filename == "":
            return jsonify({"error": "Empty filename"}), 400

        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)

        print("📄 File saved:", file_path)

        # STEP 1
        print("\n🔹 STEP 1: Extracting Questions")
        questions = extract_questions(file_path)
        save_to_json(questions, "questions.json")
        print("✅ Questions extracted:", len(questions))

        # STEP 2
        print("\n🔹 STEP 2: Generating Answers")
        answers = generate_all_answers(
            question_json_path="questions.json",
            textbook_pdf_path=TEXTBOOK_PATH
        )

        print("\n🎉 Process Completed Successfully")

        return jsonify({
            "message": "Extraction and Answer Generation Successful",
            "total_questions": len(questions),
            "questions": questions,
            "answers": answers
        })

    except Exception as e:
        print("\n❌ ERROR OCCURRED")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/upload-answer-script", methods=["POST"])

def upload_answer_script():

    print("\n==============================")
    print("📥 New Answer Script Uploaded")
    print("==============================")

    try:
        if "files" not in request.files:
            return jsonify({"error": "No files uploaded"}), 400

        files = request.files.getlist("files")

        ANSWER_FOLDER = "answer2"
        os.makedirs(ANSWER_FOLDER, exist_ok=True)

        # Clear old pages
        for f in os.listdir(ANSWER_FOLDER):
            os.remove(os.path.join(ANSWER_FOLDER, f))

        # Save uploaded images
        for file in files:
            file_path = os.path.join(ANSWER_FOLDER, file.filename)
            file.save(file_path)

        print("✅ Pages saved")

        # Run OCR + Structuring
        structured_answers = extract_answer_script(ANSWER_FOLDER)

        # ==============================
        # 🔥 Save JSON file
        # ==============================
        OUTPUT_JSON = "structured_answers.json"

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(structured_answers, f, indent=4, ensure_ascii=False)

        print(f"✅ Answers saved to {OUTPUT_JSON}")

        return jsonify({
            "message": "Answer Script Processed Successfully",
            "total_answers_detected": len(structured_answers),
            "json_file": OUTPUT_JSON,
            "answers": structured_answers
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

import re

def normalize_answer_keys(student_answers):

    normalized = {}

    for key, value in student_answers.items():

        # Convert Q11(a) -> Q11a
        match = re.match(r"Q(\d+)\(([a-z])\)", key, re.I)

        if match:
            qnum = int(match.group(1))
            sub = match.group(2)

            # If question <=10 remove subpart
            if qnum <= 10:
                new_key = f"Q{qnum}"
            else:
                new_key = f"Q{qnum}{sub}"

        else:
            # Normal Q1,Q2 etc
            match2 = re.match(r"Q(\d+)", key)
            if match2:
                new_key = f"Q{match2.group(1)}"
            else:
                new_key = key

        # Merge text if same key occurs
        if new_key in normalized:
            normalized[new_key] += "\n" + value
        else:
            normalized[new_key] = value

    return normalized


@app.route("/evaluate", methods=["POST"])
def evaluate_answers():
    try:
        
        import json
        from evaluation import evaluate

        # -----------------------------
        # Load files
        # -----------------------------
        print('hello')
        with open("structured_answers.json", "r", encoding="utf-8") as f:
            student_answers = json.load(f)

# Normalize keys
            student_answers = normalize_answer_keys(student_answers)
        
        with open("answers.json", "r", encoding="utf-8") as f:
            answer_key = json.load(f)

        with open("questions.json", "r", encoding="utf-8") as f:
            questions_list = json.load(f)

        # -----------------------------
        # Build lookup dictionary
        # -----------------------------
        question_lookup = {}
        # print(questions_list)

        for q in questions_list:
            if q["sub_question"] is None:
                key = f"Q{q['question_number']}"
            else:
                key = f"Q{q['question_number']}{q['sub_question']}"

            question_lookup[key] = {
                "text": q["text"],
                "marks": q["marks"]
            }
            print(key, "q")
        answer_lookup = {}

        for item in answer_key:
            answer_lookup[item["id"]] = item["answer"]

        # -----------------------------
        # Evaluate
        # -----------------------------
        results = {}
        total_score = 0
        total_max = 0
    
        
        for extracted_q, student_answer in student_answers.items():

            # Convert extracted format to match question.json ID
            # Q.11(a) → Q11a
            clean_q = extracted_q.replace("Q.", "Q").replace("(", "").replace(")", "")
            import re

# Convert Q.11(a) → Q11a
            clean_q = re.sub(r"Q\.(\d+)\((\w)\)", r"Q\1\2", extracted_q)

            # Convert Q.1 → Q1
            clean_q = re.sub(r"Q\.(\d+)", r"Q\1", clean_q)
            print(clean_q in question_lookup , clean_q in answer_lookup)

            if clean_q in question_lookup and clean_q in answer_lookup:

                question_text = question_lookup[clean_q]["text"]
                max_marks = question_lookup[clean_q]["marks"]
                key_answer = answer_lookup[clean_q]
                result = evaluate(
                    question_text,
                    key_answer,
                    student_answer,
                    max_marks
                )
                print("Evaluating Qno:",clean_q)

                results[extracted_q] = result
                total_score += result["Score"]
                total_max += max_marks

        return jsonify({
            "results": results,
            "total_score": round(total_score, 2),
            "total_max_marks": 50
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/submit-voice-answers", methods=["POST"])
def submit_voice_answers():
    try:
        data = request.json  # { "Q1": "answer...", "Q2": "answer..." }

        if not data:
            return jsonify({"error": "No answers received"}), 400

        # Save same format as OCR output
        with open("structured_answers.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        return jsonify({"message": "Voice answers saved successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=False)
