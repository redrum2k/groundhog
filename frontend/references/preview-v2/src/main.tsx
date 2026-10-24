import { createRoot } from "react-dom/client";
import "./styles.css";
import App from "./App";
// Planhat is a white product: pin the light theme regardless of the OS setting
document.documentElement.dataset.theme = "light";
createRoot(document.getElementById("root")!).render(<App />);
// enable state-change motion only after first paint (no page-load animation)
requestAnimationFrame(() => setTimeout(() => { document.documentElement.dataset.anim = ""; }, 300));
