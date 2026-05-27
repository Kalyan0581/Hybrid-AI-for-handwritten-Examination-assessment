from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
from PIL import Image
import torch
import gc
import os
import re
import json

# ==============================
# 1️⃣ Device Setup
# ==============================
device = "cuda" if torch.cuda.is_available() else "cpu"
print("🔥 Using:", device.upper())
if device == "cuda":
    print("GPU:", torch.cuda.get_device_name(0))

# ==============================
# 2️⃣ Model Path
# ==============================
model_path = "D:/prj/Qwen2_5_VL_7B_local"

# ==============================
# 3️⃣ Quantization
# ==============================
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16
)

# ==============================
# 4️⃣ Load Model (Load Once)
# ==============================
processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
from transformers import BitsAndBytesConfig

quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    llm_int8_enable_fp32_cpu_offload=True
)

model = AutoModelForImageTextToText.from_pretrained(
    model_path,
    quantization_config=quant_config,
    device_map="auto",
    trust_remote_code=True
)

# ==============================
# 5️⃣ Natural Sort Function
# ==============================
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]


# =========================================================
# 🔥 MAIN FUNCTION FOR FLASK INTEGRATION
# =========================================================
def extract_answer_script(images_folder):

    image_files = sorted(
        [f for f in os.listdir(images_folder) if f.lower().endswith(".png")],
        key=natural_sort_key
    )

    print(f"\n📄 Total Pages Found: {len(image_files)}")

    final_answers = {}

    for file_name in image_files:

        print(f"\n🔍 Processing {file_name}")

        image_path = os.path.join(images_folder, file_name)
        image = Image.open(image_path).convert("RGB")
        image.thumbnail((900, 900))

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {
                        "type": "text",
                        "text": """
Extract handwritten text exactly as written.

IMPORTANT:
- Question numbers are written as Q.1, Q.2, Q.3 , Q.11(a), Q.11(b), Q.12(b), Q.13(a) etc.
- Only treat numbers starting with "Q." as question numbers.
- Do NOT treat numbers inside answers as question numbers.
- Preserve original text formatting.
"""
                    },
                ],
            }
        ]

        prompt = processor.apply_chat_template(messages, add_generation_prompt=True)

        inputs = processor(
            text=prompt,
            images=[image],
            return_tensors="pt"
        ).to(device)

        torch.cuda.empty_cache()
        gc.collect()

        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=1024,
                temperature=0.0,
                do_sample=False
            )

        # Remove prompt tokens
        generated_ids = generated_ids[:, inputs["input_ids"].shape[1]:]

        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

        print("\n================ OCR RAW OUTPUT ================")
        print(text)
        print("================================================")

        # Fix Q misread as 8
        text = re.sub(r'^\s*8\.(\d+)', r'Q.\1', text, flags=re.MULTILINE)

        lines = text.split("\n")

        question_pattern = re.compile(r'^(?:Q\.?)?(\d{1,2})')
        subpart_pattern = re.compile(r'^\(?([ab])\)?', re.I)

        current_question = None
        current_question_number = None
        current_subpart = None

        for line in lines:

            line = line.strip()

            if not line:
                continue

            # ----------------------
            # Detect Question
            # ----------------------
            q_match = question_pattern.match(line)

            if q_match:

                q_num = int(q_match.group(1))

                current_question_number = q_num
                current_question = f"Q{q_num}"
                current_subpart = None

                if current_question not in final_answers:
                    final_answers[current_question] = ""

                line = line[q_match.end():].strip()

            # ----------------------
            # Detect Subpart ONLY if question > 10
            # ----------------------
            if current_question_number and current_question_number > 10:

                sub_match = subpart_pattern.match(line)

                if sub_match:

                    sub_letter = sub_match.group(1).lower()

                    current_subpart = f"{current_question}({sub_letter})"

                    if current_subpart not in final_answers:
                        final_answers[current_subpart] = ""

                    line = line[sub_match.end():].strip()

            # ----------------------
            # Append Text
            # ----------------------
            if current_subpart:
                final_answers[current_subpart] += line + "\n"

            elif current_question:
                final_answers[current_question] += line + "\n"

       
# 🔥 REMOVE PARENT QUESTIONS IF SUBPARTS EXIST
# ==============================

    parents_to_remove = []

    for key in final_answers.keys():
        match = re.match(r'(Q\d+)\([a-z]\)', key)
        if match:
            parents_to_remove.append(match.group(1))

    for parent in set(parents_to_remove):
        if parent in final_answers and final_answers[parent].strip() == "":
            del final_answers[parent]

        print("\n✅ Structured Extraction Completed")

    # ==============================
# 🔥 SORT QUESTIONS PROPERLY
# ==============================

    def sort_key(q):
        main_match = re.match(r'Q\.(\d+)', q)
        sub_match = re.match(r'Q\.(\d+)\(([a-zA-Z])\)', q)

        if sub_match:
            return (int(sub_match.group(1)), sub_match.group(2))
        elif main_match:
            return (int(main_match.group(1)), "")
        return (9999, "")

    sorted_answers = dict(sorted(final_answers.items(), key=lambda x: sort_key(x[0])))

    return sorted_answers

