"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import { saveBuyerAddress, useBuyerAddress } from "../../lib/run/buyer-settings";
import { browserWallet, connectBuyer } from "../../lib/run/wallet";
import { IcX } from "./icons";

export default function WalletSettings() {
  const address = useBuyerAddress();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function connect() {
    setBusy(true);
    setError(undefined);
    try {
      saveBuyerAddress(await connectBuyer(browserWallet()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Wallet connection failed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function forget() {
    setError(undefined);
    try {
      saveBuyerAddress("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Wallet settings could not be cleared.");
    }
  }

  return <Dialog.Root>
    <Dialog.Trigger asChild>
      <button type="button" className="btn" aria-label="Wallet settings">
        {address ? `Buyer · ${address.slice(0, 6)}…${address.slice(-4)}` : "Wallet settings"}
      </button>
    </Dialog.Trigger>
    <Dialog.Portal>
      <Dialog.Overlay className="wallet-overlay" />
      <Dialog.Content className="wallet-settings">
        <div className="wallet-heading">
          <Dialog.Title>Buyer wallet</Dialog.Title>
          <Dialog.Close asChild><button type="button" className="sq" aria-label="Close wallet settings"><IcX/></button></Dialog.Close>
        </div>
        <Dialog.Description>Connect your Buyer account once. We’ll use it for new quotes on this browser.</Dialog.Description>
        <span className="tag">Base Sepolia · test USDC</span>
        <div className="wallet-account" aria-live="polite">
          {address ? <><span className="faint">Saved buyer account</span><p>{address}</p></> : <p>No buyer wallet saved yet.</p>}
        </div>
        <p className="faint">Select Buyer in MetaMask before connecting. You’ll still review and sign each payment in MetaMask.</p>
        {address && <p className="faint">Changing this setting applies to new quotes. Existing agreements keep their original buyer.</p>}
        {error && <p className="tools-err" role="alert">{error}</p>}
        <div className="wallet-actions">
          <button type="button" className="btn solid" disabled={busy} onClick={connect}>{busy ? "Connecting…" : address ? "Change buyer wallet" : "Connect MetaMask"}</button>
          {address && <button type="button" className="btn" disabled={busy} onClick={forget}>Forget wallet</button>}
        </div>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
