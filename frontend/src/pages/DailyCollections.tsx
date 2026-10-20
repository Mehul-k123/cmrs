import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../api/client";
import type { Collection } from "../api/types";
import { Amount, Card, PageHeader, Spinner, Stat, StatusBadge, Table } from "../components/ui";
import { formatDateTime, formatINR, todayISO } from "../lib/format";

interface Daily {
  date: string;
  count: number;
  total: string;
  cash_in_hand: string;
  by_status: Record<string, { count: number; amount: string }>;
  results: Collection[];
}

export default function DailyCollections() {
  const [date, setDate] = useState(todayISO());
  const { data, isLoading } = useQuery({
    queryKey: ["/collections/daily/", date],
    queryFn: async () => (await api.get<Daily>("/collections/daily/", { params: { date, page_size: 200 } })).data,
  });

  return (
    <div>
      <PageHeader title="Daily collections" subtitle="Everything you collected on a given day."
        actions={<input type="date" className="input w-auto" value={date} max={todayISO()} onChange={(e) => setDate(e.target.value)} />} />
      {isLoading || !data ? <Spinner /> : (
        <>
          <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Collections" value={data.count} />
            <Stat label="Total collected" value={formatINR(data.total)} tone="good" />
            <Stat label="Cash in hand" value={formatINR(data.cash_in_hand)} tone={Number(data.cash_in_hand) ? "warn" : "default"} sub="Not yet submitted to branch" />
            <Stat label="Submitted" value={formatINR(data.by_status.SUBMITTED?.amount ?? "0")} sub="Pending branch verification" />
          </div>
          <Card padded={false}>
            <Table empty={!data.results.length} head={
              <tr><th className="th">Receipt</th><th className="th">Time</th><th className="th">Customer</th><th className="th">Loan</th><th className="th num">Amount</th><th className="th">Status</th></tr>
            }>
              {data.results.map((c) => (
                <tr key={c.id}>
                  <td className="td font-mono text-xs">{c.receipt_number}</td>
                  <td className="td">{formatDateTime(c.collected_at)}</td>
                  <td className="td">{c.customer_name}</td>
                  <td className="td">{c.loan_number}</td>
                  <td className="td num"><Amount value={c.amount} /></td>
                  <td className="td"><StatusBadge status={c.status} /></td>
                </tr>
              ))}
            </Table>
          </Card>
        </>
      )}
    </div>
  );
}
