// Run copy joins two parts with " · " ("Contract line 5 · every SF ZIP", "$120 captured · mock").
// On screen that becomes hierarchy instead of a dot: one part at full weight, the other quieter.
export default function Label({ text, quiet = "head" }: { text: string; quiet?: "head" | "tail" }) {
  const [head, ...rest] = text.split(" · ");
  if (!rest.length) return <>{text}</>;
  const tail = rest.join(", ");
  return quiet === "head" ? <><span className="lbl-q">{head}</span> {tail}</> : <>{head} <span className="lbl-q">{tail}</span></>;
}
