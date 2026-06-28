import { useCallback, useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from "react";
import { createPortal } from "react-dom";

interface Props {
  text: string;
  className?: string;
}

const TOOLTIP_WIDTH = 224; // w-56
const GAP = 6;

function TooltipPortal({
  text,
  anchorRef,
}: {
  text: string;
  anchorRef: RefObject<HTMLElement | null>;
}) {
  const tooltipRef = useRef<HTMLSpanElement>(null);
  const [style, setStyle] = useState<CSSProperties>({ visibility: "hidden" });

  const updatePosition = useCallback(() => {
    const anchor = anchorRef.current;
    const tooltip = tooltipRef.current;
    if (!anchor || !tooltip) return;

    const rect = anchor.getBoundingClientRect();
    const tooltipHeight = tooltip.offsetHeight;
    const viewportPadding = 8;

    let top = rect.top - tooltipHeight - GAP;
    if (top < viewportPadding) {
      top = rect.bottom + GAP;
    }

    let left = rect.left + rect.width / 2 - TOOLTIP_WIDTH / 2;
    left = Math.max(
      viewportPadding,
      Math.min(left, window.innerWidth - TOOLTIP_WIDTH - viewportPadding)
    );

    setStyle({
      position: "fixed",
      top,
      left,
      width: TOOLTIP_WIDTH,
      visibility: "visible",
      zIndex: 9999,
    });
  }, [anchorRef]);

  useLayoutEffect(() => {
    updatePosition();
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);
    return () => {
      window.removeEventListener("scroll", updatePosition, true);
      window.removeEventListener("resize", updatePosition);
    };
  }, [updatePosition]);

  return createPortal(
    <span
      ref={tooltipRef}
      style={style}
      className="px-2.5 py-2 text-[0.7rem] font-normal normal-case tracking-normal text-slate-700 bg-white border border-border rounded-lg shadow-xl pointer-events-none leading-snug"
      role="tooltip"
    >
      {text}
    </span>,
    document.body
  );
}

export function InfoTip({ text, className = "" }: Props) {
  const [visible, setVisible] = useState(false);
  const anchorRef = useRef<HTMLSpanElement>(null);

  return (
    <span
      ref={anchorRef}
      className={`inline-flex align-middle ${className}`}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
      role="img"
      aria-label={text}
    >
      <span
        tabIndex={0}
        className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-slate-300 text-[0.6rem] font-bold text-slate-500 leading-none hover:border-slate-500 hover:text-slate-700 select-none"
      >
        i
      </span>
      {visible && <TooltipPortal text={text} anchorRef={anchorRef} />}
    </span>
  );
}

/** Label text with an adjacent (i) tooltip */
export function LabelWithTip({
  label,
  tip,
  className = "",
}: {
  label: string;
  tip: string;
  className?: string;
}) {
  return (
    <span className={`inline-flex items-center gap-1 ${className}`}>
      {label}
      <InfoTip text={tip} />
    </span>
  );
}
