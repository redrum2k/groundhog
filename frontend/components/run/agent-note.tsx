import {IcLogo} from "./icons";

export default function AgentNote({text, settled, shifted}: {text: string; settled: boolean; shifted: boolean}) {
  return <aside className={`caption agent-note${shifted ? " shifted" : ""}`} aria-label="Agent update">
    <div className="agent-note-head"><IcLogo size={16}/><span>Groundhog</span><span className="agent-note-label">{settled ? "Complete" : "Working note"}</span></div>
    <div className="agent-note-body" aria-live="polite" aria-atomic="true"><p key={text} className="cap-text">{text || "Waiting for the next update."}</p></div>
  </aside>;
}
