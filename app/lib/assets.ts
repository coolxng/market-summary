export type AssetDefinition = {
  slug: string;
  symbol: string;
  name: string;
  category: "Index" | "Volatility" | "Rates" | "FX" | "Commodity" | "Crypto" | "Equity" | "ETF" | "Sector ETF" | "Credit";
  pricePrefix?: string;
  priceSuffix?: string;
  digits?: number;
  /** TradingView logo slug (equities only); drawn as a circular mark. */
  logo?: string;
};

export function logoUrl(asset: AssetDefinition) {
  return asset.logo ? `https://s3-symbol-logo.tradingview.com/${asset.logo}--big.svg` : null;
}

export const assetCatalog: AssetDefinition[] = [
  { slug: "spx", symbol: "^GSPC", name: "S&P 500", category: "Index" },
  { slug: "nasdaq", symbol: "^IXIC", name: "Nasdaq Composite", category: "Index" },
  { slug: "dow", symbol: "^DJI", name: "Dow Jones", category: "Index" },
  { slug: "russell-2000", symbol: "^RUT", name: "Russell 2000", category: "Index" },
  { slug: "nikkei-225", symbol: "^N225", name: "Nikkei 225", category: "Index" },
  { slug: "euro-stoxx-50", symbol: "^STOXX50E", name: "Euro Stoxx 50", category: "Index" },
  { slug: "ftse-100", symbol: "^FTSE", name: "FTSE 100", category: "Index" },
  { slug: "hang-seng", symbol: "^HSI", name: "Hang Seng", category: "Index" },
  { slug: "vix", symbol: "^VIX", name: "CBOE Volatility Index", category: "Volatility" },
  { slug: "move", symbol: "^MOVE", name: "ICE BofA MOVE Index", category: "Volatility" },
  { slug: "us-3m", symbol: "^IRX", name: "U.S. 13-Week Treasury Yield", category: "Rates", priceSuffix: "%" },
  { slug: "us-5y", symbol: "^FVX", name: "U.S. 5-Year Treasury Yield", category: "Rates", priceSuffix: "%" },
  { slug: "us-10y", symbol: "^TNX", name: "U.S. 10-Year Treasury Yield", category: "Rates", priceSuffix: "%" },
  { slug: "us-30y", symbol: "^TYX", name: "U.S. 30-Year Treasury Yield", category: "Rates", priceSuffix: "%" },
  { slug: "dxy", symbol: "DX-Y.NYB", name: "U.S. Dollar Index", category: "FX" },
  { slug: "gold", symbol: "GC=F", name: "Gold", category: "Commodity", pricePrefix: "$" },
  { slug: "wti", symbol: "CL=F", name: "WTI Crude", category: "Commodity", pricePrefix: "$" },
  { slug: "silver", symbol: "SI=F", name: "Silver", category: "Commodity", pricePrefix: "$" },
  { slug: "natural-gas", symbol: "NG=F", name: "Natural Gas", category: "Commodity", pricePrefix: "$", digits: 3 },
  { slug: "copper", symbol: "HG=F", name: "Copper", category: "Commodity", pricePrefix: "$", digits: 3 },
  { slug: "bitcoin", symbol: "BTC-USD", name: "Bitcoin", category: "Crypto", pricePrefix: "$", digits: 0 },
  { slug: "ethereum", symbol: "ETH-USD", name: "Ethereum", category: "Crypto", pricePrefix: "$", digits: 0 },
  { slug: "solana", symbol: "SOL-USD", name: "Solana", category: "Crypto", pricePrefix: "$" },
  { slug: "xrp", symbol: "XRP-USD", name: "XRP", category: "Crypto", pricePrefix: "$", digits: 4 },
  { slug: "aapl", symbol: "AAPL", name: "Apple", category: "Equity", pricePrefix: "$", logo: "apple" },
  { slug: "msft", symbol: "MSFT", name: "Microsoft", category: "Equity", pricePrefix: "$", logo: "microsoft" },
  { slug: "nvda", symbol: "NVDA", name: "Nvidia", category: "Equity", pricePrefix: "$", logo: "nvidia" },
  { slug: "amzn", symbol: "AMZN", name: "Amazon", category: "Equity", pricePrefix: "$", logo: "amazon" },
  { slug: "meta", symbol: "META", name: "Meta Platforms", category: "Equity", pricePrefix: "$", logo: "meta-platforms" },
  { slug: "sndk", symbol: "SNDK", name: "SanDisk", category: "Equity", pricePrefix: "$", logo: "sandisk" },
  { slug: "amd", symbol: "AMD", name: "Advanced Micro Devices", category: "Equity", pricePrefix: "$", logo: "advanced-micro-devices" },
  { slug: "intc", symbol: "INTC", name: "Intel", category: "Equity", pricePrefix: "$", logo: "intel" },
  { slug: "mu", symbol: "MU", name: "Micron Technology", category: "Equity", pricePrefix: "$", logo: "micron-technology" },
  { slug: "googl", symbol: "GOOGL", name: "Alphabet", category: "Equity", pricePrefix: "$", logo: "alphabet" },
  { slug: "tsla", symbol: "TSLA", name: "Tesla", category: "Equity", pricePrefix: "$", logo: "tesla" },
  { slug: "avgo", symbol: "AVGO", name: "Broadcom", category: "Equity", pricePrefix: "$", logo: "broadcom" },
  { slug: "tsm", symbol: "TSM", name: "Taiwan Semiconductor", category: "Equity", pricePrefix: "$", logo: "taiwan-semiconductor" },
  { slug: "orcl", symbol: "ORCL", name: "Oracle", category: "Equity", pricePrefix: "$", logo: "oracle" },
  { slug: "nflx", symbol: "NFLX", name: "Netflix", category: "Equity", pricePrefix: "$", logo: "netflix" },
  { slug: "pltr", symbol: "PLTR", name: "Palantir Technologies", category: "Equity", pricePrefix: "$", logo: "palantir" },
  { slug: "crm", symbol: "CRM", name: "Salesforce", category: "Equity", pricePrefix: "$", logo: "salesforce" },
  { slug: "adbe", symbol: "ADBE", name: "Adobe", category: "Equity", pricePrefix: "$", logo: "adobe" },
  { slug: "brk-b", symbol: "BRK-B", name: "Berkshire Hathaway", category: "Equity", pricePrefix: "$", logo: "berkshire-hathaway" },
  { slug: "jpm", symbol: "JPM", name: "JPMorgan Chase", category: "Equity", pricePrefix: "$", logo: "jpmorgan-chase" },
  { slug: "bac", symbol: "BAC", name: "Bank of America", category: "Equity", pricePrefix: "$", logo: "bank-of-america" },
  { slug: "gs", symbol: "GS", name: "Goldman Sachs", category: "Equity", pricePrefix: "$", logo: "goldman-sachs" },
  { slug: "v", symbol: "V", name: "Visa", category: "Equity", pricePrefix: "$", logo: "visa" },
  { slug: "ma", symbol: "MA", name: "Mastercard", category: "Equity", pricePrefix: "$", logo: "mastercard" },
  { slug: "lly", symbol: "LLY", name: "Eli Lilly", category: "Equity", pricePrefix: "$", logo: "eli-lilly" },
  { slug: "unh", symbol: "UNH", name: "UnitedHealth Group", category: "Equity", pricePrefix: "$", logo: "unitedhealth" },
  { slug: "jnj", symbol: "JNJ", name: "Johnson & Johnson", category: "Equity", pricePrefix: "$", logo: "johnson-and-johnson" },
  { slug: "xom", symbol: "XOM", name: "Exxon Mobil", category: "Equity", pricePrefix: "$", logo: "exxon" },
  { slug: "cvx", symbol: "CVX", name: "Chevron", category: "Equity", pricePrefix: "$", logo: "chevron" },
  { slug: "wmt", symbol: "WMT", name: "Walmart", category: "Equity", pricePrefix: "$", logo: "walmart" },
  { slug: "cost", symbol: "COST", name: "Costco", category: "Equity", pricePrefix: "$", logo: "costco-wholesale" },
  { slug: "hd", symbol: "HD", name: "Home Depot", category: "Equity", pricePrefix: "$", logo: "home-depot" },
  { slug: "ko", symbol: "KO", name: "Coca-Cola", category: "Equity", pricePrefix: "$", logo: "coca-cola" },
  { slug: "pg", symbol: "PG", name: "Procter & Gamble", category: "Equity", pricePrefix: "$", logo: "procter-and-gamble" },
  { slug: "dis", symbol: "DIS", name: "Walt Disney", category: "Equity", pricePrefix: "$", logo: "walt-disney" },
  { slug: "ba", symbol: "BA", name: "Boeing", category: "Equity", pricePrefix: "$", logo: "boeing" },
  { slug: "cat", symbol: "CAT", name: "Caterpillar", category: "Equity", pricePrefix: "$", logo: "caterpillar" },
  { slug: "uber", symbol: "UBER", name: "Uber Technologies", category: "Equity", pricePrefix: "$", logo: "uber" },
  { slug: "coin", symbol: "COIN", name: "Coinbase", category: "Equity", pricePrefix: "$", logo: "coinbase" },
  { slug: "hood", symbol: "HOOD", name: "Robinhood Markets", category: "Equity", pricePrefix: "$", logo: "robinhood" },
  { slug: "spcx", symbol: "SPCX", name: "SpaceX", category: "Equity", pricePrefix: "$", logo: "spacex" },
  { slug: "spy", symbol: "SPY", name: "SPDR S&P 500 ETF", category: "ETF", pricePrefix: "$" },
  { slug: "qqq", symbol: "QQQ", name: "Invesco QQQ Trust", category: "ETF", pricePrefix: "$" },
  { slug: "iwm", symbol: "IWM", name: "iShares Russell 2000 ETF", category: "ETF", pricePrefix: "$" },
  { slug: "dia", symbol: "DIA", name: "SPDR Dow Jones Industrial Average ETF", category: "ETF", pricePrefix: "$" },
  { slug: "rsp", symbol: "RSP", name: "Invesco S&P 500 Equal Weight ETF", category: "ETF", pricePrefix: "$" },
  { slug: "tlt", symbol: "TLT", name: "iShares 20+ Year Treasury Bond ETF", category: "ETF", pricePrefix: "$" },
  { slug: "gld", symbol: "GLD", name: "SPDR Gold Shares", category: "ETF", pricePrefix: "$" },
  { slug: "slv", symbol: "SLV", name: "iShares Silver Trust", category: "ETF", pricePrefix: "$" },
  { slug: "smh", symbol: "SMH", name: "VanEck Semiconductor ETF", category: "ETF", pricePrefix: "$" },
  { slug: "eem", symbol: "EEM", name: "iShares MSCI Emerging Markets ETF", category: "ETF", pricePrefix: "$" },
  { slug: "efa", symbol: "EFA", name: "iShares MSCI EAFE ETF", category: "ETF", pricePrefix: "$" },
  { slug: "arkk", symbol: "ARKK", name: "ARK Innovation ETF", category: "ETF", pricePrefix: "$" },
  { slug: "xlk", symbol: "XLK", name: "Technology", category: "Sector ETF", pricePrefix: "$" },
  { slug: "xlf", symbol: "XLF", name: "Financials", category: "Sector ETF", pricePrefix: "$" },
  { slug: "xle", symbol: "XLE", name: "Energy", category: "Sector ETF", pricePrefix: "$" },
  { slug: "xlv", symbol: "XLV", name: "Healthcare", category: "Sector ETF", pricePrefix: "$" },
  { slug: "xli", symbol: "XLI", name: "Industrials", category: "Sector ETF", pricePrefix: "$" },
  { slug: "xly", symbol: "XLY", name: "Consumer Discretionary", category: "Sector ETF", pricePrefix: "$" },
  { slug: "xlp", symbol: "XLP", name: "Consumer Staples", category: "Sector ETF", pricePrefix: "$" },
  { slug: "xlre", symbol: "XLRE", name: "Real Estate", category: "Sector ETF", pricePrefix: "$" },
  { slug: "xlu", symbol: "XLU", name: "Utilities", category: "Sector ETF", pricePrefix: "$" },
  { slug: "xlb", symbol: "XLB", name: "Materials", category: "Sector ETF", pricePrefix: "$" },
  { slug: "xlc", symbol: "XLC", name: "Communication Services", category: "Sector ETF", pricePrefix: "$" },
  { slug: "hyg", symbol: "HYG", name: "iShares High Yield Corporate Bond ETF", category: "Credit", pricePrefix: "$" },
  { slug: "lqd", symbol: "LQD", name: "iShares Investment Grade Corporate Bond ETF", category: "Credit", pricePrefix: "$" },
  { slug: "tip", symbol: "TIP", name: "iShares TIPS Bond ETF", category: "Rates", pricePrefix: "$" },
];

/** Treasury yields are quoted in percent and move in basis points. */
export function isYieldAsset(asset: AssetDefinition) {
  return asset.category === "Rates" && asset.priceSuffix === "%";
}

export const assetCategories: AssetDefinition["category"][] = ["Index", "Equity", "ETF", "Sector ETF", "Rates", "Credit", "Volatility", "FX", "Commodity", "Crypto"];

export const assetBySlug = Object.fromEntries(assetCatalog.map((asset) => [asset.slug, asset]));
export const assetBySymbol = Object.fromEntries(assetCatalog.map((asset) => [asset.symbol, asset]));
