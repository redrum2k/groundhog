import type { FundingPreparation } from "../runs.generated";
export interface BuyerWallet { request(args: {method:string;params?:unknown[]}): Promise<unknown> }
export function isBuyerAddress(value: unknown): value is string {
  return typeof value === "string" && /^0x[0-9a-fA-F]{40}$/.test(value) && !/^0x0{40}$/i.test(value);
}
export function browserWallet(): BuyerWallet | undefined {
  return (window as Window & {ethereum?: BuyerWallet}).ethereum;
}
export async function connectBuyer(wallet: BuyerWallet | undefined): Promise<string> {
  if (!wallet) throw new Error("Open this page in a browser with MetaMask installed.");
  const accounts = await wallet.request({method:"eth_requestAccounts"});
  const address: unknown = Array.isArray(accounts) ? accounts[0] : undefined;
  if (!isBuyerAddress(address)) throw new Error("Select your Buyer account in MetaMask.");
  if (await wallet.request({method:"eth_chainId"}) !== "0x14a34") throw new Error("Select Base Sepolia in MetaMask, then connect again.");
  const current = await wallet.request({method:"eth_accounts"});
  if (!Array.isArray(current) || typeof current[0] !== "string" || current[0].toLowerCase() !== address.toLowerCase()) throw new Error("Wallet account changed. Select your Buyer account and connect again.");
  return address;
}
export async function signFunding(wallet: BuyerWallet | undefined, preparation: FundingPreparation) {
  if (!wallet) throw new Error("Connect a browser wallet to sign the prepared Base Sepolia authorization.");
  // Connection is handled in settings before checkout; payment asks only for a signature.
  const accounts = await wallet.request({method:"eth_accounts"}) as string[];
  if (!accounts[0]) throw new Error("Connect your Buyer account in Wallet settings before paying.");
  const payer = preparation.terms.payment_info.payer;
  if (!accounts[0] || accounts[0].toLowerCase() !== payer.toLowerCase()) throw new Error("Connected wallet differs from the accepted payer. Obtain a new quote for this payer.");
  if (await wallet.request({method:"eth_chainId"}) !== "0x14a34") throw new Error("Select Base Sepolia (84532) in your wallet.");
  const signature = await wallet.request({method:"eth_signTypedData_v4",params:[payer,JSON.stringify(preparation.typed_data)]});
  if (typeof signature !== "string" || !/^0x[0-9a-fA-F]{130}$/.test(signature)) throw new Error("Wallet returned an invalid signature; no funding was submitted.");
  if ((await wallet.request({method:"eth_accounts"}) as string[])[0]?.toLowerCase() !== payer.toLowerCase()) throw new Error("Wallet account changed during signing; no funding was submitted.");
  if (await wallet.request({method:"eth_chainId"}) !== "0x14a34") throw new Error("Wallet network changed during signing; no funding was submitted.");
  return signature;
}
