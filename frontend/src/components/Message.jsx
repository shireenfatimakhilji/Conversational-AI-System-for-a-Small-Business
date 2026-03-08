import React from "react";
import styles from "./Message.module.css";

/**
 * Individual message component
 * Displays a single message from either user or bot
 */
const Message = ({ role, content, isStreaming }) => {
  const isBot = role === "assistant" || role === "bot";

  return (
    <div
      className={`${styles.message} ${isBot ? styles.messageBot : styles.messageUser}`}
    >
      <div className={styles.messageHeader}>
        <div className={styles.messageAvatar}>{isBot ? "🧶" : "👤"}</div>
        <div className={styles.messageRole}>
          {isBot ? "Crochetzies" : "You"}
        </div>
      </div>
      <div className={styles.messageContent}>
        {content}
        {isStreaming && <span className={styles.cursorBlink}>▊</span>}
      </div>
    </div>
  );
};

export default Message;
