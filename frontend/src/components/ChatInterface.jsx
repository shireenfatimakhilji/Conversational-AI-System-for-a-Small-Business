import React, { useState, useCallback, useEffect, useRef } from "react";
import MessageList from "./MessageList";
import InputForm from "./InputForm";
import { useWebSocket } from "../hooks/useWebSocket";
import styles from "./ChatInterface.module.css";

const ChatInterface = () => {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [streamingMessage, setStreamingMessage] = useState("");
  const [isWaitingForResponse, setIsWaitingForResponse] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const inputRef = useRef(null);
  const audioRef = useRef(null);

  const playTTS = useCallback(async (text) => {
    try {
      setIsSpeaking(true);
      const res = await fetch("/api/tts/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error("TTS failed");

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }

      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onended = () => {
        setIsSpeaking(false);
        URL.revokeObjectURL(url);
      };
      audio.onerror = () => {
        setIsSpeaking(false);
        URL.revokeObjectURL(url);
      };

      await audio.play();
    } catch (err) {
      console.error("TTS error:", err);
      setIsSpeaking(false);
    }
  }, []);

  const handleWebSocketMessage = useCallback((data) => {
    switch (data.type) {
      case "token":
        setStreamingMessage((prev) => prev + data.content);
        break;

      case "done":
        setStreamingMessage((current) => {
          if (current) {
            setMessages((prev) => [
              ...prev,
              { role: "assistant", content: current },
            ]);
            playTTS(current);
          }
          return "";
        });
        setIsWaitingForResponse(false);
        setTimeout(() => {
          if (inputRef.current) inputRef.current.focus();
        }, 0);
        break;

      case "error":
        console.error("Server error:", data.content);
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Error: ${data.content}` },
        ]);
        setStreamingMessage("");
        setIsWaitingForResponse(false);
        break;

      default:
        break;
    }
  }, [playTTS]);

  const handleSessionEnd = useCallback(() => {
    setSessionEnded(true);
    setIsWaitingForResponse(false);
  }, []);

  const { isConnected, sendMessage } = useWebSocket(
    sessionId,
    handleWebSocketMessage,
    handleSessionEnd,
  );

  const createNewSession = async () => {
    setIsCreatingSession(true);
    setMessages([]);
    setStreamingMessage("");
    setSessionEnded(false);
    setIsWaitingForResponse(false);
    setIsSpeaking(false);

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    try {
      const response = await fetch("/api/session/new", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!response.ok) throw new Error("Failed to create session");

      const data = await response.json();
      setSessionId(data.session_id);
      setMessages([{ role: "assistant", content: data.greeting }]);
      // No TTS for greeting — browser blocks autoplay before user interaction
    } catch (error) {
      console.error("Error creating session:", error);
      alert("Failed to create session. Please make sure the backend server is running.");
    } finally {
      setIsCreatingSession(false);
    }
  };

  const deleteSession = async () => {
    if (!sessionId) return;
    try {
      await fetch(`/api/session/${sessionId}`, { method: "DELETE" });
    } catch (error) {
      console.error("Error deleting session:", error);
    }
  };

  const handleSendMessage = useCallback(
    (message) => {
      if (!isConnected || isWaitingForResponse || sessionEnded) return;

      setMessages((prev) => [...prev, { role: "user", content: message }]);
      const success = sendMessage(message);
      if (success) {
        setIsWaitingForResponse(true);
        setStreamingMessage("");
      } else {
        alert("Failed to send message. Please check your connection.");
      }
    },
    [isConnected, sendMessage, isWaitingForResponse, sessionEnded],
  );

  const handleNewSession = async () => {
    if (sessionId) await deleteSession();
    createNewSession();
  };

  useEffect(() => {
    createNewSession();
    return () => {
      if (sessionId) deleteSession();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <div className={styles.chatInterface}>
        <div className={styles.chatHeader}>
          <div className={styles.headerContent}>
            <div className={styles.headerTitle}>
              <span className={styles.headerIcon}>🧶</span>
              <div>
                <h1>Crochetzies</h1>
                <p className={styles.headerSubtitle}>Custom Crochet Orders</p>
              </div>
            </div>

            <div className={styles.headerActions}>
              {isSpeaking && (
                <div className={styles.speakingBadge}>
                  🔊 Speaking...
                </div>
              )}
              <button
                className={styles.newSessionButton}
                onClick={handleNewSession}
                disabled={isCreatingSession}
                title="Start a new conversation"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                  className={styles.buttonIcon}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 4.5v15m7.5-7.5h-15"
                  />
                </svg>
                New Chat
              </button>
            </div>
          </div>
        </div>

        {sessionEnded && (
          <div className={styles.sessionEndedBanner}>
            <span className={styles.bannerIcon}>✓</span>
            Order confirmed! Thank you for choosing Crochetzies.
            <button className={styles.bannerButton} onClick={handleNewSession}>
              Start New Order
            </button>
          </div>
        )}

        <MessageList messages={messages} streamingMessage={streamingMessage} />

        <InputForm
          ref={inputRef}
          onSend={handleSendMessage}
          disabled={isWaitingForResponse || sessionEnded || isCreatingSession}
          isConnected={isConnected && !isCreatingSession}
          isSpeaking={isSpeaking}
        />
      </div>
    </>
  );
};

export default ChatInterface;