"use client";

const DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];

/**
 * A formatted number whose digits roll vertically to their new value, like an
 * odometer. Characters are keyed from the right so the decimal point and cents
 * stay put when the integer part gains or loses a digit. Motion is dropped for
 * readers who prefer reduced motion (see .rolling-number in globals.css).
 */
export default function RollingNumber({ value, className = "" }: { value: string; className?: string }) {
  const chars = [...value];
  return (
    <span className={`rolling-number ${className}`.trim()}>
      <span className="visually-hidden">{value}</span>
      {chars.map((char, index) => {
        const key = chars.length - index;
        const digit = DIGITS.indexOf(char);
        if (digit < 0) return <span key={`c${key}`} className="rolling-number__char" aria-hidden="true">{char}</span>;
        return (
          <span key={`d${key}`} className="rolling-number__digit" aria-hidden="true">
            <span className="rolling-number__column" style={{ transform: `translateY(${-digit * 10}%)` }}>
              {DIGITS.map((d) => <span key={d}>{d}</span>)}
            </span>
            {/* Invisible copy sets the slot's width to this digit. */}
            <span className="rolling-number__sizer">{char}</span>
          </span>
        );
      })}
    </span>
  );
}
