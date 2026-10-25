"use client";
import {useState} from "react";

export default function ComplaintForm({disabled,submit}:{disabled:boolean;submit:(text:string)=>void}) {
  const [text,setText]=useState("");
  return <form className="live-form" onSubmit={e=>{e.preventDefault();if(!disabled && text.trim())submit(text);}}>
    <label htmlFor="complaint">Your complaint</label>
    <textarea id="complaint" value={text} required maxLength={2000} placeholder="Tell us what looks wrong or what you expected." onChange={e=>setText(e.target.value)}/>
    <button type="submit" className="btn solid" disabled={disabled || !text.trim()}>Send complaint</button>
  </form>;
}
