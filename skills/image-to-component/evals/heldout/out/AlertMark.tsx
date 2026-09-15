import { useId, type SVGProps } from "react";

export interface AlertMarkProps extends SVGProps<SVGSVGElement> {
  /** Accessible name. Omit for decorative use; the icon is then aria-hidden. */
  title?: string;
}

export function AlertMark({ title, ...props }: AlertMarkProps) {
  const titleId = useId();
  const labelled = Boolean(title || props["aria-label"] || props["aria-labelledby"]);
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 74 70"
      role={labelled ? "img" : undefined}
      aria-hidden={labelled ? undefined : true}
      aria-labelledby={title ? titleId : undefined}
      focusable="false"
      {...props}
    >
      {title ? <title id={titleId}>{title}</title> : null}
      <path fill="#e5102a" d="M55.46 11.63c6.46 5.3 11.7 12.74 12.78 21.25a32.8 32.8 0 0 1-7.5 22.56c-5.46 5.76-12.28 8.63-20.18 8.9-9.04.14-15.72-.86-22.61-7.24C11.43 50.05 9.03 43.58 9 34c.65-8.64 5.08-15.47 11.25-21.37 9.84-7.81 24.9-7.84 35.2-1" />
      <path fill="#f0c7ca" d="M39.06 17.94 42 18c1.25 2.5 1.03 4 .88 6.79l-.15 2.85-.17 2.99-.16 3L42 41l-6 1a2137 2137 0 0 1-.73-14.73l-.15-3.14-.14-2.9c.03-3.5.53-3.22 4.08-3.3" />
      <path fill="#ecaeb2" d="M38.56 45.94 41 46c1.36 2.73 1.13 4.98 1 8-1 1-1 1-3.56 1.06L36 55c-1.4-2.3-2.08-3.48-1.69-6.18 1.05-2.77 1.17-2.8 4.25-2.88" />
      <path fill="#e10821" d="M33 37c3 2 3 2 4 5 2.56 1.19 2.56 1.19 5 2v2l-7 2-1 4h-3q.73-3.77 1.56-7.5c.45-2.55.51-4.92.44-7.5" />
    </svg>
  );
}

export default AlertMark;
