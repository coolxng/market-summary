"use client";

import { useEffect } from "react";

export default function PWARegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const basePath = window.location.pathname.startsWith("/market-summary") ? "/market-summary" : "";
    const onLoad = () => {
      navigator.serviceWorker.register(`${basePath}/sw.js`, { scope: `${basePath}/` }).catch(() => {
        // Offline support is an enhancement; a registration failure must never block the report.
      });
    };
    window.addEventListener("load", onLoad, { once: true });
    return () => window.removeEventListener("load", onLoad);
  }, []);

  return null;
}
