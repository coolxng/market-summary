"use client";

import { useEffect, useState } from "react";

type InstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
};

export default function DeliveryPanel({ feedHref }: { feedHref: string }) {
  const [installPrompt, setInstallPrompt] = useState<InstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState(false);

  useEffect(() => {
    const updateInstalled = () => {
      const standalone = window.matchMedia("(display-mode: standalone)").matches;
      const navigatorStandalone = Boolean((navigator as Navigator & { standalone?: boolean }).standalone);
      setInstalled(standalone || navigatorStandalone);
    };
    const onPrompt = (event: Event) => {
      event.preventDefault();
      setInstallPrompt(event as InstallPromptEvent);
    };
    const onInstalled = () => {
      setInstalled(true);
      setInstallPrompt(null);
    };

    updateInstalled();
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const install = async () => {
    if (!installPrompt) return;
    await installPrompt.prompt();
    const choice = await installPrompt.userChoice;
    if (choice.outcome === "accepted") setInstalled(true);
    setInstallPrompt(null);
  };

  return (
    <section className="delivery-panel" id="delivery" aria-labelledby="delivery-title">
      <div className="report-endmatter__subhead">
        <h3 id="delivery-title"><span>Delivery</span> Make it part of the routine</h3>
        <p>Follow the archive feed or install The Daily Tape as an app. No account is required.</p>
      </div>
      <div className="delivery-grid">
        <a href={feedHref} className="delivery-card">
          <span>RSS FEED</span>
          <strong>Get every Close Tape</strong>
          <p>Subscribe in any RSS reader and receive each archived session as soon as it publishes.</p>
          <b>Open feed →</b>
        </a>
        <article className="delivery-card">
          <span>INSTALLABLE APP</span>
          <strong>{installed ? "Daily Tape is installed" : "Keep it one click away"}</strong>
          <p>Install for a standalone window and home-screen access. Market data always loads fresh; nothing is kept offline where it could go stale.</p>
          {installed ? <b>Installed ✓</b> : installPrompt ? <button onClick={install}>Install Daily Tape</button> : <b>Use your browser’s Install / Add to Home Screen option</b>}
        </article>
      </div>
    </section>
  );
}
