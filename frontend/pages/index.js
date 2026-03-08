import Head from "next/head";
import ChatInterface from "../src/components/ChatInterface";

/**
 * Home Page
 * Main entry point for the Crochetzies chatbot
 */
export default function Home() {
  return (
    <>
      <Head>
        <title>Crochetzies Chatbot</title>
        <meta
          name="description"
          content="Crochetzies - Custom Crochet Order Chatbot"
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>
      <div className="app-container">
        <ChatInterface />
      </div>
    </>
  );
}
