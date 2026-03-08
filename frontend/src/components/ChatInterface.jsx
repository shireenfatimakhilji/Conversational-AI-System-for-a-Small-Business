import React, { useState, useCallback, useEffect, useRef } from "react";
import MessageList from "./MessageList";
import InputForm from "./InputForm";
import { useWebSocket } from "../hooks/useWebSocket";
import styles from "./ChatInterface.module.css";

/**
 * ChatInterface - Main chat component
 * Manages conversation state, session lifecycle, and WebSocket communication
 */
const ChatInterface = () => {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [streamingMessage, setStreamingMessage] = useState("");
  const [isWaitingForResponse, setIsWaitingForResponse] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const inputRef = useRef(null);

  // Handle incoming WebSocket messages
  const handleWebSocketMessage = useCallback((data) => {
    switch (data.type) {
      case "token":
        // Append token to streaming message
        setStreamingMessage((prev) => prev + data.content);
        break;

      case "done":
        // Response complete - save to messages
        setStreamingMessage((current) => {
          if (current) {
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content: current,
              },
            ]);
          }
          return "";
        });
        setIsWaitingForResponse(false);
        // Refocus input after response
        setTimeout(() => {
          if (inputRef.current) {
            inputRef.current.focus();
          }
        }, 0);
        break;

      case "error":
        console.error("Server error:", data.content);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `Error: ${data.content}`,
          },
        ]);
        setStreamingMessage("");
        setIsWaitingForResponse(false);
        break;

      default:
        break;
    }
  }, []);

  // Handle session end
  const handleSessionEnd = useCallback((message) => {
    setSessionEnded(true);
    setIsWaitingForResponse(false);
  }, []);

  // Initialize WebSocket connection
  const { isConnected, sendMessage } = useWebSocket(
    sessionId,
    handleWebSocketMessage,
    handleSessionEnd,
  );

  // Create new session
  const createNewSession = async () => {
    setIsCreatingSession(true);
    setMessages([]);
    setStreamingMessage("");
    setSessionEnded(false);
    setIsWaitingForResponse(false);

    try {
      const response = await fetch("/api/session/new", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error("Failed to create session");
      }

      const data = await response.json();
      setSessionId(data.session_id);

      // Add greeting message
      setMessages([
        {
          role: "assistant",
          content: data.greeting,
        },
      ]);
    } catch (error) {
      console.error("Error creating session:", error);
      alert(
        "Failed to create session. Please make sure the backend server is running.",
      );
    } finally {
      setIsCreatingSession(false);
    }
  };

  // Delete current session
  const deleteSession = async () => {
    if (!sessionId) return;

    try {
      await fetch(`/api/session/${sessionId}`, {
        method: "DELETE",
      });
    } catch (error) {
      console.error("Error deleting session:", error);
    }
  };

  // Handle send message
  const handleSendMessage = useCallback(
    (message) => {
      if (!isConnected || isWaitingForResponse || sessionEnded) return;

      // Add user message to history
      setMessages((prev) => [
        ...prev,
        {
          role: "user",
          content: message,
        },
      ]);

      // Send via WebSocket
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

  // Handle new session button
  const handleNewSession = async () => {
    // Delete current session and create new one
    if (sessionId) {
      await deleteSession();
    }
    createNewSession();
  };

  // Create initial session on mount
  useEffect(() => {
    createNewSession();

    // Cleanup on unmount
    return () => {
      if (sessionId) {
        deleteSession();
      }
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
        />
      </div>
    </>
  );
};

export default ChatInterface;
