"use client";

import { useState } from "react";

/** Letters for the fallback mark: "^GSPC" → "GS", "BTC-USD" → "BTC", "GC=F" → "GC". */
function monogram(symbol: string) {
  return symbol.replace(/^\^/, "").split(/[-=.]/)[0].slice(0, 3);
}

/**
 * Circular asset mark: the company logo when one is known, otherwise the
 * symbol's letters, so rows of mixed assets stay aligned. Decorative only;
 * the name beside it carries the meaning.
 */
export default function AssetLogo({ src, symbol, size = 32 }: { src: string | null; symbol: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  const letters = monogram(symbol);
  return (
    <span className="asset-logo" style={{ width: size, height: size, fontSize: Math.round(size * (letters.length > 2 ? 0.3 : 0.36)) }} aria-hidden="true">
      {src && !failed
        // eslint-disable-next-line @next/next/no-img-element -- static export; remote logo
        ? <img src={src} alt="" width={size} height={size} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} />
        : letters}
    </span>
  );
}
