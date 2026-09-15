import { useId, type SVGProps } from "react";

export interface FacebookBannerMarkProps extends SVGProps<SVGSVGElement> {
  /** Accessible name. Omit for decorative use; the icon is then aria-hidden. */
  title?: string;
}

export function FacebookBannerMark({ title, ...props }: FacebookBannerMarkProps) {
  const titleId = useId();
  const labelled = Boolean(title || props["aria-label"] || props["aria-labelledby"]);
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      role={labelled ? "img" : undefined}
      aria-hidden={labelled ? undefined : true}
      aria-labelledby={title ? titleId : undefined}
      focusable="false"
      {...props}
    >
      {title ? <title id={titleId}>{title}</title> : null}
      <path fill="#0b6bce" d="m34.44 6.56 3.64-.06c8.16 0 12.42.64 18.65 5.98 5.53 5.84 5.12 12.85 4.94 20.41q-.05 3.26-.02 6.51C61.6 52.58 61.6 52.58 57 58c-4.55 3.62-7.58 4.51-13.37 4.53l-2.1.01-4.32-.02q-3.3-.02-6.6.02h-4.23l-3.85-.02c-5.2-.77-9.02-3.45-12.34-7.46C5.86 49 6.79 41.81 6.75 34.62l-.06-3.36c-.04-7.76.5-12.92 5.63-19 7.02-5.89 13.34-5.75 22.12-5.7" />
      <path fill="#076cce" d="m34.44 6.56 3.64-.06c8.05 0 13.08.65 18.92 6.5v4l-4-1v3h-2l-1-2c-2.06-.63-2.06-.63-4-1v1l-2.01.08c-4.04.26-7.33.62-11.05 2.3-2.68 3.62-2.63 6.83-2.8 11.25C30 33 30 33 29 34q-2.5.06-5 0l1 6h5v22c-12.98 0-12.98 0-18.43-5.43-5.8-6.35-4.78-13.83-4.82-21.95l-.06-3.36c-.04-7.76.5-12.92 5.63-19 7.02-5.89 13.34-5.75 22.12-5.7" />
      <path fill="#ecf3fa" d="M46 17c-.12 2.81-.12 2.81-1 6l-3 1.44L39 26c-.88 3.69-.88 3.69-1 7l8 1-1 7-7 1v20h-8V40l-5 1c-1-1-1-1-1.06-4.06L24 34l5-1 .01-2.23c.35-8.98.35-8.98 3.43-11.96C37.11 16.44 40.86 16.54 46 17" />
    </svg>
  );
}

export default FacebookBannerMark;
