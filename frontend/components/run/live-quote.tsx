import type { Quote } from "../../lib/runs.generated";

export default function LiveQuote({quote, canAccept, pay}: {quote: Quote; canAccept: boolean; pay: () => void}) {
  const price = (quote.amount.amount_minor / 100).toFixed(2);
  const terms = quote.payment_terms;
  const mock = terms?.mode === "mock";
  return <>
    <h3>Quote · ${price}</h3>
    <p>{quote.work_description}</p>
    <p>{mock ? "Simulated payment" : `${price} test USDC · Base Sepolia`}. Funds are held in escrow while the dataset is produced and reviewed.</p>
    <p>The operator releases payment after you accept the verified delivery or the 60-second review ends without an unresolved dispute.</p>
    <details><summary>Agreement & payment details</summary>
      <pre className="live-data">{JSON.stringify(quote.specification.terms, null, 2)}</pre>
      <p>Buyer: {terms?.payment_info.payer}<br/>Receiver: {terms?.payment_info.receiver}<br/>Operator: {terms?.payment_info.operator}</p>
      <p>Exact amount: {terms?.amount_atomic} atomic USDC. Conversion: {terms?.pricing_rule}.</p>
      <p>Quote expires {quote.expires_at}. {quote.policy?.version}</p>
      {terms && <p>Fund by {new Date(Number(terms.payment_info.pre_approval_expiry) * 1000).toLocaleString()}. Authorization expires {new Date(Number(terms.payment_info.authorization_expiry) * 1000).toLocaleString()}.</p>}
      <p>Accepting the agreement, signing payment, submitting it and confirming held funds are separate steps. The operator controls capture and void under this agreement.</p>
    </details>
    {canAccept && <button type="button" className="btn solid" onClick={pay}>Accept & {mock ? "simulate" : "pay"} ${price}</button>}
  </>;
}
