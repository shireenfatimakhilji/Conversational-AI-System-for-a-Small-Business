import { useEffect, useRef, useCallback, useState } from "react";

/**
 * Custom hook for managing WebSocket connection to Crochetzies chatbot
 * Handles:
 * - Connection lifecycle
 * - Streaming token responses
 * - Session management
 * - Automatic reconnection
 */
export const useWebSocket = (sessionId, onMessage, onSessionEnd) => {
  const wsRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const reconnectTimeoutRef = useRef(null);

  const connect = useCallback(() => {
    if (!sessionId || isConnecting || wsRef.current) return;

    setIsConnecting(true);
    const wsUrl = `ws://localhost:8000/ws/chat/${sessionId}`;

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setIsConnected(true);
        setIsConnecting(false);
        wsRef.current = ws;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          switch (data.type) {
            case "token":
              // Stream individual tokens
              if (onMessage) {
                onMessage({ type: "token", content: data.data });
              }
              break;

            case "done":
              // End of current response
              if (onMessage) {
                onMessage({ type: "done" });
              }
              break;

            case "session_end":
              // Order confirmed, session closing
              if (onSessionEnd) {
                onSessionEnd(data.data);
              }
              break;

            case "error":
              console.error("Server error:", data.data);
              if (onMessage) {
                onMessage({ type: "error", content: data.data });
              }
              break;

            default:
              console.warn("Unknown message type:", data.type);
          }
        } catch (error) {
          console.error("Failed to parse message:", error);
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setIsConnecting(false);
      };

      ws.onclose = () => {
        setIsConnected(false);
        setIsConnecting(false);
        wsRef.current = null;

        // Attempt to reconnect after 2 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          if (sessionId) {
            connect();
          }
        }, 2000);
      };
    } catch (error) {
      console.error("Failed to create WebSocket:", error);
      setIsConnecting(false);
    }
  }, [sessionId, onMessage, onSessionEnd, isConnecting]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
    setIsConnecting(false);
  }, []);

  const sendMessage = useCallback((message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ message }));
      return true;
    } else {
      console.error("WebSocket is not connected");
      return false;
    }
  }, []);

  // Connect when sessionId changes
  useEffect(() => {
    if (sessionId) {
      connect();
    }

    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  return {
    isConnected,
    isConnecting,
    sendMessage,
    disconnect,
  };
};
