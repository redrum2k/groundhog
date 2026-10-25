// The source the agent reads during a dispute: a small database in the orb's blue.
export default function Warehouse({ size = 36 }: { size?: number }) {
  return (
    <svg className="wh" width={size} height={size} viewBox="0 0 48 48" aria-hidden>
      <path d="M8 13v22c0 3.3 7.2 6 16 6s16-2.7 16-6V13" className="wh-body" />
      <path d="M8 24c0 3.3 7.2 6 16 6s16-2.7 16-6" className="wh-band" />
      <ellipse cx="24" cy="13" rx="16" ry="6" className="wh-top" />
    </svg>
  );
}
