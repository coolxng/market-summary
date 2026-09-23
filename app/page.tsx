import report from "../data/report_snapshot.json";
import DailyTape, { type DailyReport } from "./DailyTape";
import { archivedReports } from "./lib/archive";
import { buildRegimeTimeline } from "./lib/regime";

const latest = report as unknown as DailyReport;

export default function Home() {
  const timeline = buildRegimeTimeline(latest, archivedReports().map(({ date, report: issue }) => ({ report: issue, href: `${date}/` })));
  return <DailyTape report={latest} regimeTimeline={timeline} regimeHrefBase="./reports/" />;
}
