import type { FundingPreparation } from "../runs.generated";
export interface BuyerWallet { request(args: {method:string;params?:unknown[]}): Promise<unknown> }
export async function signFunding(wallet: BuyerWallet | undefined, preparation: FundingPreparation) {
  if (!wallet) throw new Error("Connect a browser wallet to sign the prepared Base Sepolia authorization.");
  const accounts = await wallet.request({method:"eth_requestAccounts"}) as string[];
  const payer = preparation.terms.payment_info.payer;
  if (!accounts[0] || accounts[0].toLowerCase() !== payer.toLowerCase()) throw new Error("Connected wallet differs from the accepted payer. Obtain a new quote for this payer.");
  if (await wallet.request({method:"eth_chainId"}) !== "0x14a34") throw new Error("Select Base Sepolia (84532) in your wallet.");
  const signature = await wallet.request({method:"eth_signTypedData_v4",params:[payer,JSON.stringify(preparation.typed_data)]});
  if (typeof signature !== "string" || !/^0x[0-9a-fA-F]{130}$/.test(signature)) throw new Error("Wallet returned an invalid signature; no funding was submitted.");
  if ((await wallet.request({method:"eth_accounts"}) as string[])[0]?.toLowerCase() !== payer.toLowerCase()) throw new Error("Wallet account changed during signing; no funding was submitted.");
  if (await wallet.request({method:"eth_chainId"}) !== "0x14a34") throw new Error("Wallet network changed during signing; no funding was submitted.");
  return signature;
}
