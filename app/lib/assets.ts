export type AssetDefinition = {
  slug: string;
  symbol: string;
  name: string;
  category: "Index" | "Volatility" | "Rates" | "FX" | "Commodity" | "Crypto" | "Equity" | "Sector ETF" | "Credit";
  pricePrefix?: string;
  priceSuffix?: string;
  digits?: number;
};

export const assetCatalog: AssetDefinition[] = [
  { slug: "spx", symbol: "^GSPC", name: "S&P 500", category: "Index" },
  { slug: "nasdaq", symbol: "^IXIC", name: "Nasdaq Composite", category: "Index" },
  { slug: "dow", symbol: "^DJI", name: "Dow Jones", category: "Index" },
  { slug: "russell-2000", symbol: "^RUT", name: "Russell 2000", category: "Index" },
  { slug: "vix", symbol: "^VIX", name: "CBOE Volatility Index", category: "Volatility" },
  { slug: "us-3m", symbol: "^IRX", name: "U.S. 13-Week Treasury Yield", category: "Rates", priceSuffix: "%" },
  { slug: "us-5y", symbol: "^FVX", name: "U.S. 5-Year Treasury Yield", category: "Rates", priceSuffix: "%" },
  { slug: "us-10y", symbol: "^TNX", name: "U.S. 10-Year Treasury Yield", category: "Rates", priceSuffix: "%" },
  { slug: "us-30y", symbol: "^TYX", name: "U.S. 30-Year Treasury Yield", category: "Rates", priceSuffix: "%" },
  { slug: "dxy", symbol: "DX-Y.NYB", name: "U.S. Dollar Index", category: "FX" },
  { slug: "gold", symbol: "GC=F", name: "Gold", category: "Commodity", pricePrefix: "$" },
  { slug: "wti", symbol: "CL=F", name: "WTI Crude", category: "Commodity", pricePrefix: "$" },
  { slug: "bitcoin", symbol: "BTC-USD", name: "Bitcoin", category: "Crypto", pricePrefix: "$", digits: 0 },
  { slug: "ethereum", symbol: "ETH-USD", name: "Ethereum", category: "Crypto", pricePrefix: "$", digits: 0 },
  { slug: "solana", symbol: "SOL-USD", name: "Solana", category: "Crypto", pricePrefix: "$" },
  { slug: "xrp", symbol: "XRP-USD", name: "XRP", category: "Crypto", pricePrefix: "$", digits: 4 },
  { slug: "aapl", symbol: "AAPL", name: "Apple", category: "Equity", pricePrefix: "$" },
  { slug: "msft", symbol: "MSFT", name: "Microsoft", category: "Equity", pricePrefix: "$" },
  { slug: "nvda", symbol: "NVDA", name: "Nvidia", category: "Equity", pricePrefix: "$" },
  { slug: "amzn", symbol: "AMZN", name: "Amazon", category: "Equity", pricePrefix: "$" },
  { slug: "meta", symbol: "META", name: "Meta Platforms", category: "Equity", pricePrefix: "$" },
  { slug: "sndk", symbol: "SNDK", name: "SanDisk", category: "Equity", pricePrefix: "$" },
  { slug: "amd", symbol: "AMD", name: "Advanced Micro Devices", category: "Equity", pricePrefix: "$" },
  { slug: "intc", symbol: "INTC", name: "Intel", category: "Equity", pricePrefix: "$" },
  { slug: "mu", symbol: "MU", name: "Micron Technology", category: "Equity", pricePrefix: "$" },
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

export const assetBySlug = Object.fromEntries(assetCatalog.map((asset) => [asset.slug, asset]));
export const assetBySymbol = Object.fromEntries(assetCatalog.map((asset) => [asset.symbol, asset]));
