"use client";

import { useState } from "react";

type ShareMetrics = {
  sp500: string;
  nasdaq: string;
  vix: string;
  breadth: string;
};

function wrapText(context: CanvasRenderingContext2D, text: string, maxWidth: number) {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let line = "";
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (context.measureText(candidate).width > maxWidth && line) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines.slice(0, 4);
}

export default function ShareSummaryButton({
  headline,
  session,
  metrics,
}: {
  headline: string;
  session: string;
  metrics: ShareMetrics;
}) {
  const [state, setState] = useState<"idle" | "working" | "copied">("idle");

  const share = async () => {
    setState("working");
    try {
      const dark = document.documentElement.dataset.theme === "ink";
      const canvas = document.createElement("canvas");
      canvas.width = 1200;
      canvas.height = 630;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Canvas unavailable");

      const background = dark ? "#080808" : "#f3f0e7";
      const foreground = dark ? "#f1eee3" : "#151512";
      const muted = dark ? "#aaa7a0" : "#515048";
      const line = dark ? "#2b2b2b" : "#c9c3b5";
      const accent = dark ? "#ff6c47" : "#ff5c35";

      context.fillStyle = background;
      context.fillRect(0, 0, 1200, 630);

      context.fillStyle = accent;
      context.fillRect(72, 58, 8, 42);

      context.fillStyle = foreground;
      context.font = "700 24px Arial, sans-serif";
      context.fillText("THE DAILY TAPE", 100, 88);

      context.fillStyle = muted;
      context.font = "700 15px Arial, sans-serif";
      context.fillText(session.toUpperCase(), 72, 138);

      context.strokeStyle = line;
      context.lineWidth = 2;
      context.beginPath();
      context.moveTo(72, 164);
      context.lineTo(1128, 164);
      context.stroke();

      context.fillStyle = foreground;
      context.font = "500 58px Georgia, serif";
      const lines = wrapText(context, headline, 940);
      lines.forEach((value, index) => {
        context.fillStyle = index === lines.length - 1 && lines.length > 1 ? accent : foreground;
        context.fillText(value, 72, 242 + index * 66);
      });

      const metricY = 500;
      const cells = [
        ["S&P 500", metrics.sp500],
        ["NASDAQ", metrics.nasdaq],
        ["VIX", metrics.vix],
        ["BREADTH", metrics.breadth],
      ];
      cells.forEach(([label, value], index) => {
        const x = 72 + index * 264;
        context.fillStyle = muted;
        context.font = "700 13px Arial, sans-serif";
        context.fillText(label, x, metricY);
        context.fillStyle = foreground;
        context.font = "650 30px Arial, sans-serif";
        context.fillText(value, x, metricY + 42);
      });

      context.fillStyle = muted;
      context.font = "500 13px Arial, sans-serif";
      context.fillText("coolxng.github.io/market-summary", 72, 594);

      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
      if (!blob) throw new Error("Image export unavailable");

      const file = new File([blob], "daily-tape.png", { type: "image/png" });
      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: "The Daily Tape",
          text: headline,
        });
      } else {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "daily-tape.png";
        link.click();
        URL.revokeObjectURL(url);
      }
      setState("copied");
      window.setTimeout(() => setState("idle"), 1800);
    } catch {
      setState("idle");
    }
  };

  return (
    <button className="share-card-button" onClick={share} disabled={state === "working"}>
      {state === "working" ? "Building card…" : state === "copied" ? "Card ready ✓" : "Share card ↗"}
    </button>
  );
}
