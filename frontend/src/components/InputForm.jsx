import React, { useState, useRef, useEffect } from "react";
import styles from "./InputForm.module.css";

/**
 * InputForm component
 * Handles user message input with send button
 */
const InputForm = React.forwardRef(({ onSend, disabled, isConnected }, ref) => {
  const [message, setMessage] = useState("");
  const textareaRef = useRef(null);

  // Expose focus method to parent via ref
  React.useImperativeHandle(ref, () => ({
    focus: () => {
      if (textareaRef.current) {
        textareaRef.current.focus();
      }
    },
  }));

  const handleSubmit = (e) => {
    e.preventDefault();

    const trimmedMessage = message.trim();
    if (trimmedMessage && !disabled && isConnected) {
      onSend(trimmedMessage);
      setMessage("");

      // Reset textarea height and refocus
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.focus();
      }
    }
  };

  const handleKeyDown = (e) => {
    // Send on Enter, new line on Shift+Enter
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Auto-resize textarea
  const handleInput = (e) => {
    setMessage(e.target.value);

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  };

  // Focus input on mount
  useEffect(() => {
    if (textareaRef.current && isConnected) {
      textareaRef.current.focus();
    }
  }, [isConnected]);

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
            isConnected
              ? "Type your message... (Enter to send, Shift+Enter for new line)"
              : "Connecting..."
          }
          disabled={disabled || !isConnected}
          rows="1"
        />
        <button
          type="submit"
          className={styles.sendButton}
          disabled={disabled || !isConnected || !message.trim()}
          title="Send message"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            className={styles.sendIcon}
          >
            <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
          </svg>
        </button>
      </div>

      {!isConnected && (
        <div className={styles.connectionStatus}>
          <span
            className={`${styles.statusIndicator} ${styles.disconnected}`}
          ></span>
          Connecting to server...
        </div>
      )}
    </form>
  );
});

InputForm.displayName = "InputForm";

export default InputForm;
