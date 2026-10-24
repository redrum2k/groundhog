"use client";
import { IcLock, IcSheet } from "./icons";
import { basescan, type Coin } from "../../lib/run/fold";

// The agent's mascot: a flat blue orb with two eyes, carrying the order's money as a coin.
// Moods are state indicators (like a spinner): their loops run only in that state, and the
// reduced-motion version holds a still pose instead.
export type Mood = "float" | "carry" | "look" | "blink";

export default function Orb({ x, y, mood, coin, label }: { x: number; y: number; mood: Mood; coin: Coin | null; label: string }) {
  return (
    <div className={`orb-at m-${mood}`} style={{ transform: `translate(${x}px, ${y}px)` }}>
      <span className="orb" role="img" aria-label={label}>
        <span className="eyes"><i /><i /></span>
        {mood === "carry" && <span className="orb-sheet"><IcSheet size={11} /></span>}
      </span>
      {coin && (
        <span className={`coin c-${coin.state}`} role="status">
          <span className="coin-face" aria-hidden>{coin.state === "locked" ? <IcLock size={10} strokeWidth={1.8} /> : "$"}</span>
          <span key={coin.state} className="coin-t">
            ${coin.amount} {coin.state}
            {coin.state === "captured" && (coin.mock
              ? <span className="faint"> · mock</span>
              : coin.tx && <> · <a href={basescan(coin.tx)} target="_blank" rel="noreferrer">Basescan</a></>)}
          </span>
        </span>
      )}
    </div>
  );
}

/** The orb's face on its own, for chat lines and the workspace mark. */
export const OrbMark = ({ size = 18 }: { size?: number }) => (
  <span className="orb mark" style={{ width: size, height: size }} aria-hidden><span className="eyes"><i /><i /></span></span>
);
