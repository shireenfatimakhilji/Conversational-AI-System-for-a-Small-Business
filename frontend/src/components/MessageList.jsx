import React, { useEffect, useRef } from "react";
import Message from "./Message";
import styles from "./MessageList.module.css";

/**
 * MessageList component
 * Displays all messages in the conversation with auto-scroll
 */
const MessageList = ({ messages, streamingMessage }) => {
  const messagesEndRef = useRef(null);
  const containerRef = useRef(null);
  const isUserScrollingRef = useRef(false);

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    if (messagesEndRef.current && !isUserScrollingRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage]);

  // Track if user is manually scrolling
  const handleScroll = () => {
    if (!containerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    isUserScrollingRef.current = !isAtBottom;
  };

  return (
    <div
      className={styles.messageList}
      ref={containerRef}
      onScroll={handleScroll}
    >
      {messages.length === 0 && !streamingMessage && (
        <div className={styles.emptyState}>
          <div className={styles.emptyStateIcon}>🧶</div>
          <h2>Welcome to Crochetzies!</h2>
          <p>Let's create something beautiful together.</p>
          <p className={styles.emptyStateHint}>
            Start by saying hello or tell us what you'd like to order.
          </p>
        </div>
      )}

      {messages.map((msg, index) => (
        <Message
          key={index}
          role={msg.role}
          content={msg.content}
          isStreaming={false}
        />
      ))}

      {streamingMessage && (
        <Message
          role="assistant"
          content={streamingMessage}
          isStreaming={true}
        />
      )}

      <div ref={messagesEndRef} />
    </div>
  );
};

export default MessageList;
