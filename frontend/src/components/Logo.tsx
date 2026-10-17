export const Logo = ({ className = "h-7 w-7" }: { className?: string }) => (
  <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
    <rect width="32" height="32" rx="8" className="fill-accent" />
    <path
      d="M7 21c3 0 4-10 8-10s3 8 6 8 3-5 4-5"
      fill="none"
      className="stroke-accent-fg"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <circle cx="7" cy="21" r="2" className="fill-accent-fg" />
    <circle cx="25" cy="14" r="2.4" fill="#fbbf24" />
  </svg>
);
