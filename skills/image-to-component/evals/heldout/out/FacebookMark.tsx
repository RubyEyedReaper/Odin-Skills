import { useId, type SVGProps } from "react";

export interface FacebookMarkProps extends SVGProps<SVGSVGElement> {
  /** Accessible name. Omit for decorative use; the icon is then aria-hidden. */
  title?: string;
}

export function FacebookMark({ title, ...props }: FacebookMarkProps) {
  const titleId = useId();
  const labelled = Boolean(title || props["aria-label"] || props["aria-labelledby"]);
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 52 52"
      role={labelled ? "img" : undefined}
      aria-hidden={labelled ? undefined : true}
      aria-labelledby={title ? titleId : undefined}
      focusable="false"
      {...props}
    >
      {title ? <title id={titleId}>{title}</title> : null}
      <path fill="#0296db" d="M19.5 8.54h2.18q2.28 0 4.55.05 3.48.05 6.97.04l4.42.03h2.11c3.63.08 5.16.27 8.27 2.34 1.14 3.43 1.13 6.1 1.13 9.72v20.12c-.1 2.6-.26 4.72-1.13 7.16-2.76 2.23-4.16 1.99-7.75 1.63L37 49V35l5-1v-5l-4-1c-1.13-4.75-1.13-4.75 0-7 2.06-.62 2.06-.62 4-1l1-4-4.38.3-2.46.19c-2.16.5-2.16.5-4.16 3.5q-.6 3.5-1 7l-5 1v6h5c1.44 2.9 1.1 5.43 1.06 8.64L32 49c-3.26 1.63-6.8 1.27-10.38 1.3l-2.33.1c-5.69.07-5.69.07-8.77-2.3C6.8 42.96 7.73 36.97 7.7 30.84q-.04-3.29-.1-6.56 0-2.1-.03-4.17l-.04-3.83C8 13 8 13 9.55 10.59c3.3-2.14 6.16-2.13 9.95-2.05" />
      <path fill="#0281be" d="M9 12h1c.88 9.37 1.12 18.6 1 28h4v3l3 1v2l11 1 1-13c2 2 2 2 2.2 5.04l-.08 3.58-.05 3.61L32 49c-3.26 1.63-6.8 1.27-10.38 1.31l-2.32.09c-5.69.06-5.69.06-8.78-2.29-2.77-3.84-2.65-6.32-2.65-11.05l-.01-2.07.01-4.33-.01-6.65.01-4.2v-3.88C8 13 8 13 9 12" />
      <path fill="#01a9f0" d="M12 10q6.56-.08 13.12-.12l3.76-.06 3.63-.02 3.33-.03c3.34.24 6.04 1.04 9.16 2.23v1l-9 1v2c-3.46 3-3.46 3-6 3v7h-3c-.12-6.75-.12-6.75 1-9l-5-1v-2l-11-2z" />
    </svg>
  );
}

export default FacebookMark;
