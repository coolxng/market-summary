import report from "../report_snapshot.json";
import DailyTape, { type DailyReport } from "./DailyTape";

export default function Home() {
  return <DailyTape report={report as unknown as DailyReport} />;
}
