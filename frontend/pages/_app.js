import "../styles/globals.css";

/**
 * Next.js App Component
 * Wraps all pages with global styles and providers
 */
export default function App({ Component, pageProps }) {
  return <Component {...pageProps} />;
}
