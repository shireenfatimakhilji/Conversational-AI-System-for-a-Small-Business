import React, { useState, useRef, useEffect } from "react";
import styles from "./InputForm.module.css";

const InputForm = React.forwardRef(({ onSend, disabled, isConnected, isSpeaking }, ref) => {
  const [message, setMessage] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const textareaRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  React.useImperativeHandle(ref, () => ({
    focus: () => {
      if (textareaRef.current) textareaRef.current.focus();
    },
  }));

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmedMessage = message.trim();
    if (trimmedMessage && !disabled && isConnected) {
      onSend(trimmedMessage);
      setMessage("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.focus();
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleInput = (e) => {
    setMessage(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  };

  useEffect(() => {
    if (textareaRef.current && isConnected) textareaRef.current.focus();
  }, [isConnected]);

  // ── Mic logic ──────────────────────────────────────────────────────────────
  const handleMicClick = async () => {
    if (isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;
        chunksRef.current = [];

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunksRef.current.push(e.data);
        };

        mediaRecorder.onstop = async () => {
          stream.getTracks().forEach((t) => t.stop());
          setIsTranscribing(true);
          try {
            const blob = new Blob(chunksRef.current, { type: "audio/webm" });
            const formData = new FormData();
            formData.append("audio", blob, "recording.webm");

            const res = await fetch("/api/asr/transcribe", {
              method: "POST",
              body: formData,
            });

            if (!res.ok) throw new Error("Transcription failed");
            const data = await res.json();

            setMessage(data.text);
            if (textareaRef.current) {
              textareaRef.current.style.height = "auto";
              textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
              textareaRef.current.focus();
            }
          } catch (err) {
            console.error("ASR error:", err);
            alert("Could not transcribe audio. Is the backend running?");
          } finally {
            setIsTranscribing(false);
          }
        };

        mediaRecorder.start();
        setIsRecording(true);
      } catch (err) {
        console.error("Mic error:", err);
        alert("Microphone access denied. Please allow mic permissions.");
      }
    }
  };

  const micTitle = isRecording
    ? "Stop recording"
    : isTranscribing
    ? "Transcribing..."
    : isSpeaking
    ? "Bot is speaking..."
    : "Speak your message";

  return (
    <form className={styles.inputForm} onSubmit={handleSubmit}>
      <div className={styles.inputContainer}>
        <textarea
          ref={textareaRef}
          className={styles.inputField}
          value={message}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={
            isTranscribing
              ? "Transcribing your voice..."
              : isSpeaking
              ? "Bot is speaking..."
              : isConnected
              ? "Type your message... (Enter to send, Shift+Enter for new line)"
              : "Connecting..."
          }
          disabled={disabled || !isConnected || isTranscribing}
          rows="1"
        />

        {/* ── Mic Button ── */}
        <button
          type="button"
          className={`${styles.micButton} ${isRecording ? styles.micRecording : ""} ${isTranscribing ? styles.micTranscribing : ""} ${isSpeaking ? styles.micSpeaking : ""}`}
          onClick={handleMicClick}
          disabled={disabled || !isConnected || isTranscribing || isSpeaking}
          title={micTitle}
        >
          {isTranscribing ? (
            <svg className={styles.spinnerIcon} viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4" strokeDashoffset="10" />
            </svg>
          ) : isSpeaking ? (
            // Speaker wave icon while bot talks
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={styles.micIcon}>
              <path d="M13.5 4.06c0-1.336-1.616-2.005-2.56-1.06l-4.5 4.5H4.508c-1.141 0-2.318.664-2.66 1.905A9.76 9.76 0 001.5 12c0 .898.121 1.768.35 2.595.341 1.24 1.518 1.905 2.659 1.905h1.93l4.5 4.5c.945.945 2.561.276 2.561-1.06V4.06zM18.584 5.106a.75.75 0 011.06 0c3.808 3.807 3.808 9.98 0 13.788a.75.75 0 11-1.06-1.06 8.25 8.25 0 000-11.668.75.75 0 010-1.06z" />
              <path d="M15.932 7.757a.75.75 0 011.061 0 6 6 0 010 8.486.75.75 0 01-1.06-1.061 4.5 4.5 0 000-6.364.75.75 0 010-1.061z" />
            </svg>
          ) : isRecording ? (
            // Stop icon while recording
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={styles.micIcon}>
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          ) : (
            // Mic icon at rest
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={styles.micIcon}>
              <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm-1.5 14.93A7.001 7.001 0 0 1 5 9H3a9 9 0 0 0 8 8.94V21H9v2h6v-2h-2v-3.07A9 9 0 0 0 21 9h-2a7 7 0 0 1-5.5 6.93z"/>
            </svg>
          )}
        </button>

        {/* ── Send Button ── */}
        <button
          type="submit"
          className={styles.sendButton}
          disabled={disabled || !isConnected || !message.trim()}
          title="Send message"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={styles.sendIcon}>
            <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
          </svg>
        </button>
      </div>

      {/* ── Status bars ── */}
      {isRecording && (
        <div className={styles.recordingStatus}>
          <span className={styles.recordingDot}></span>
          Recording... tap the button again to stop
        </div>
      )}

      {isTranscribing && (
        <div className={styles.transcribingStatus}>
          <span className={styles.transcribingDot}></span>
          Transcribing your voice...
        </div>
      )}

      {isSpeaking && (
        <div className={styles.speakingStatus}>
          <span className={styles.speakingDot}></span>
          Bot is speaking...
        </div>
      )}

      {!isConnected && (
        <div className={styles.connectionStatus}>
          <span className={`${styles.statusIndicator} ${styles.disconnected}`}></span>
          Connecting to server...
        </div>
      )}
    </form>
  );
});

InputForm.displayName = "InputForm";
export default InputForm;