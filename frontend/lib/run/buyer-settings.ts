"use client";
import { useSyncExternalStore } from "react";
import { isBuyerAddress } from "./wallet";

const KEY = "datumco.buyer-wallet.v1";
const CHANGED = "datumco:buyer-wallet-changed";

function readAddress(): string {
  try {
    const address = localStorage.getItem(KEY);
    return isBuyerAddress(address) ? address : "";
  } catch {
    return "";
  }
}

function subscribe(notify: () => void) {
  window.addEventListener("storage", notify);
  window.addEventListener(CHANGED, notify);
  return () => {
    window.removeEventListener("storage", notify);
    window.removeEventListener(CHANGED, notify);
  };
}

export function useBuyerAddress() {
  return useSyncExternalStore(subscribe, readAddress, () => "");
}

export function saveBuyerAddress(address: string) {
  if (address && !isBuyerAddress(address)) throw new Error("Choose a valid Buyer wallet.");
  try {
    if (address) localStorage.setItem(KEY, address);
    else localStorage.removeItem(KEY);
  } catch {
    throw new Error("Wallet settings could not be saved. Allow site storage and try again.");
  }
  window.dispatchEvent(new Event(CHANGED));
}
