import React, { useState } from "react";
import axios from "axios";

const UploadPage = () => {
  const [questionFile, setQuestionFile] = useState(null);
  const [answerFiles, setAnswerFiles] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [voiceAnswers, setVoiceAnswers] = useState({});
  const [recordingQ, setRecordingQ] = useState(null);
  const [loading, setLoading] = useState(false);
  const [evaluationResults, setEvaluationResults] = useState(null);

  // ============================
  // File Handlers
  // ============================
  const handleQuestionChange = (e) => {
    if (e.target.files.length > 0) {
      setQuestionFile(e.target.files[0]);
    }
  };

  const handleAnswerChange = (e) => {
    setAnswerFiles(Array.from(e.target.files));
  };

  // ============================
  // Upload Question Paper
  // ============================
  const uploadQuestionPaper = async () => {
    if (!questionFile) return alert("Please select a question paper.");

    const formData = new FormData();
    formData.append("file", questionFile);

    try {
      setLoading(true);

      const res = await axios.post(
        "http://127.0.0.1:5000/upload-question-paper",
        formData
      );

      setQuestions(res.data.questions || []);
      alert("Question paper uploaded successfully!");
    } catch (err) {
      console.error(err);
      alert("Failed to upload question paper");
    } finally {
      setLoading(false);
    }
  };

  // ============================
  // Upload Answer Scripts (OCR)
  // ============================
  const uploadAnswerScripts = async () => {
    if (answerFiles.length === 0)
      return alert("Please select answer scripts.");

    const formData = new FormData();
    answerFiles.forEach((file) => {
      formData.append("files", file);
    });

    try {
      setLoading(true);

      await axios.post(
        "http://127.0.0.1:5000/upload-answer-script",
        formData
      );

      alert("Answer scripts uploaded successfully!");
    } catch (err) {
      console.error(err);
      alert("Failed to upload answer scripts");
    } finally {
      setLoading(false);
    }
  };

  // ============================
  // 🎤 Voice Recording
  // ============================
  const startRecording = (qKey) => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Speech Recognition not supported");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.interimResults = false;

    setRecordingQ(qKey);
    recognition.start();

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;

      setVoiceAnswers((prev) => ({
        ...prev,
        [qKey]: transcript,
      }));

      setRecordingQ(null);
    };

    recognition.onerror = () => {
      alert("Speech recognition error");
      setRecordingQ(null);
    };

    // Auto stop after 15 seconds
    setTimeout(() => recognition.stop(), 15000);
  };

  // ============================
  // Submit Voice Answers
  // ============================
  const submitVoiceAnswers = async () => {
    if (Object.keys(voiceAnswers).length === 0) {
      return alert("No voice answers recorded!");
    }

    try {
      setLoading(true);

      await axios.post(
        "http://127.0.0.1:5000/submit-voice-answers",
        voiceAnswers
      );

      alert("Voice answers submitted successfully!");
    } catch (err) {
      console.error(err);
      alert("Failed to submit voice answers");
    } finally {
      setLoading(false);
    }
  };

  // ============================
  // Evaluate
  // ============================
  const handleEvaluate = async () => {
    try {
      setLoading(true);

      const res = await axios.post(
        "http://127.0.0.1:5000/evaluate"
      );

      setEvaluationResults(res.data);
    } catch (err) {
      console.error(err);
      alert("Evaluation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <h1 className="title">GradeMate</h1>

      <div className="cards">
        {/* STEP 1 */}
        <div className="card">
          <h2>Upload Question Paper</h2>

          <label className="file-upload">
            <input
              type="file"
              accept="application/pdf"
              onChange={handleQuestionChange}
            />
            <span>📄 Select Question PDF</span>
          </label>

          {questionFile && (
            <p className="file-name">{questionFile.name}</p>
          )}

          <button onClick={uploadQuestionPaper}>
            Upload PDF
          </button>
        </div>

        {/* STEP 2 */}
        <div className="card">
          <h2>Upload Answer Scripts</h2>

          <label className="file-upload">
            <input
              type="file"
              multiple
              accept="image/*"
              onChange={handleAnswerChange}
            />
            <span>🖼 Select Answer Images</span>
          </label>

          {answerFiles.length > 0 && (
            <p className="file-name">
              {answerFiles.length} files selected
            </p>
          )}

          <button className="success" onClick={uploadAnswerScripts}>
            Upload Images
          </button>
        </div>

        {/* STEP 3 */}
        <div className="card">
          <h2>Evaluate</h2>

          <button
            className="purple"
            onClick={handleEvaluate}
            disabled={!questionFile}
          >
            Evaluate
          </button>
        </div>
      </div>

      {/* ================= VIVA SECTION ================= */}
      <div className="card" style={{ marginTop: "30px" }}>
        <h2>Viva Voice</h2>

        {questions.length === 0 && (
          <p>Upload question paper first to start viva</p>
        )}

        {questions.map((q) => {
          const key = q.sub_question
            ? `Q${q.question_number}${q.sub_question}`
            : `Q${q.question_number}`;

          return (
            <div key={key} style={{ marginBottom: "15px" }}>
              <p>
                <b>{key}:</b> {q.text}
              </p>

              <button onClick={() => startRecording(key)}>
                🎤{" "}
                {recordingQ === key
                  ? "Recording..."
                  : "Record Answer"}
              </button>

              {voiceAnswers[key] && (
                <p style={{ marginTop: "5px" }}>
                  📝 {voiceAnswers[key]}
                </p>
              )}
            </div>
          );
        })}

        <button className="success" onClick={submitVoiceAnswers}>
          Submit Voice Answers
        </button>
      </div>

      {loading && <p className="loading">Processing...</p>}

      {/* RESULTS */}
      {evaluationResults && (
        <div className="results-box">
          <h2>
            Total Score: {evaluationResults.total_score} /{" "}
            {evaluationResults.total_max_marks}
          </h2>

          <table>
            <thead>
              <tr>
                <th>Question</th>
                <th>Score</th>
                <th>Feedback</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(evaluationResults.results)
                .sort(([a], [b]) => {
                  const parse = (q) => {
                    const match = q.match(/Q\.?(\d+)(?:\((\w)\))?/);
                    if (!match) return [999, ""];
                    return [parseInt(match[1]), match[2] || ""];
                  };

                  const [numA, subA] = parse(a);
                  const [numB, subB] = parse(b);

                  if (numA !== numB) return numA - numB;
                  return subA.localeCompare(subB);
                })
                .map(([q, r]) => (
                  <tr key={q}>
                    <td>{q}</td>
                    <td>
                      {r.Score} / {r["Max Marks"]}
                    </td>
                    <td>{r["AI Explanation"]}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default UploadPage;