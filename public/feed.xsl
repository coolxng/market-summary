<?xml version="1.0" encoding="UTF-8"?>
<!--
  Renders feed.xml as a readable page when someone opens it in a browser.
  Feed readers ignore this stylesheet and read the RSS directly.
-->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:atom="http://www.w3.org/2005/Atom">
  <xsl:output method="html" encoding="UTF-8" indent="yes" doctype-system="about:legacy-compat"/>

  <xsl:template match="/rss/channel">
    <xsl:variable name="feedUrl" select="atom:link[@rel='self']/@href"/>
    <html lang="en">
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <meta name="robots" content="noindex"/>
        <title>RSS feed · <xsl:value-of select="title"/></title>
        <style>
          /* Georgia only has old-style figures; this digits-only face keeps numbers on the baseline. */
          @font-face { font-family: "Serif Figures"; src: url(fonts/gelasio-figures-400.woff2) format("woff2"); font-weight: 400; unicode-range: U+0030-0039; font-display: swap; }
          :root { --paper: #f3f0e7; --ink: #151512; --ink-soft: #515048; --line: #c9c3b5; --panel: #ebe7dc; --accent: #ff5c35; --serif: "Serif Figures", Georgia, "Times New Roman", serif; color-scheme: light dark; }
          @media (prefers-color-scheme: dark) { :root { --paper: #080808; --ink: #f1eee3; --ink-soft: #aaa7a0; --line: #2b2b2b; --panel: #151515; --accent: #ff6c47; } }
          * { box-sizing: border-box; }
          body { margin: 0; background: var(--paper); color: var(--ink); font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; }
          main { width: min(760px, 100% - 32px); margin: 0 auto; padding: 56px 0 72px; }
          a { color: inherit; }
          .kicker { margin: 0; color: var(--accent); font-size: 10px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; }
          h1 { margin: 12px 0 0; font-family: var(--serif); font-size: clamp(38px, 8vw, 60px); font-weight: 500; letter-spacing: -.04em; line-height: 1; }
          .lede { margin: 18px 0 0; color: var(--ink-soft); font-family: var(--serif); font-size: 18px; line-height: 1.55; }
          .subscribe { display: flex; gap: 8px; margin-top: 26px; }
          .subscribe code { flex: 1; min-width: 0; overflow: hidden; padding: 12px 14px; border: 1px solid var(--line); border-radius: 10px; background: var(--panel); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
          .subscribe button { flex: none; padding: 0 16px; border: 1px solid var(--ink); border-radius: 10px; color: var(--paper); background: var(--ink); cursor: pointer; font: inherit; font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
          .back { display: inline-block; margin-top: 18px; color: var(--ink-soft); font-size: 12px; font-weight: 700; }
          ol { margin: 44px 0 0; padding: 0; border-top: 2px solid var(--ink); list-style: none; }
          li { padding: 22px 0; border-bottom: 1px solid var(--line); }
          li time { color: var(--ink-soft); font-size: 10px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; }
          li h2 { margin: 8px 0 0; font-family: var(--serif); font-size: 23px; font-weight: 500; letter-spacing: -.02em; line-height: 1.2; }
          li h2 a { text-decoration: none; }
          li h2 a:hover { color: var(--accent); }
          li p { margin: 8px 0 0; color: var(--ink-soft); font-size: 14px; line-height: 1.55; }
        </style>
      </head>
      <body>
        <main>
          <p class="kicker">RSS feed</p>
          <h1><xsl:value-of select="title"/></h1>
          <p class="lede">
            This is a feed of every market-close report. Paste the address below into a feed reader
            (Feedly, NetNewsWire, Inoreader, Reeder) to get each new session as it publishes.
          </p>
          <div class="subscribe">
            <code id="feed-url"><xsl:value-of select="$feedUrl"/></code>
            <button type="button" id="copy">Copy</button>
          </div>
          <a class="back" href="{link}">← Back to <xsl:value-of select="title"/></a>

          <ol>
            <xsl:for-each select="item">
              <li>
                <time><xsl:value-of select="substring(pubDate, 1, 16)"/></time>
                <h2><a href="{link}"><xsl:value-of select="title"/></a></h2>
                <p><xsl:value-of select="description"/></p>
              </li>
            </xsl:for-each>
          </ol>
        </main>
        <script>
          document.getElementById("copy").addEventListener("click", function (event) {
            var button = event.currentTarget;
            var url = document.getElementById("feed-url").textContent;
            navigator.clipboard.writeText(url).then(function () {
              button.textContent = "Copied";
              setTimeout(function () { button.textContent = "Copy"; }, 1600);
            });
          });
        </script>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
