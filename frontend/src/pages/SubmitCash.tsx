import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, errorText } from "../api/client";
import type { Collection } from "../api/types";
import { Alert, Amount, Button, Card, Field, PageHeader, Spinner, Table } from "../components/ui";
import { formatDateTime, formatINR } from "../lib/format";
import { useList } from "../lib/hooks";
import { compare, isValidAmount, subtract, sumMoney } from "../lib/money";

export default function SubmitCash() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data, isLoading } = useList<Collection>("/collections/", { status: "COLLECTED", mode: "CASH", page_size: 200, ordering: "collected_at" });
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [declared, setDeclared] = useState("");
  const [note, setNote] = useState("");

  const rows = data?.results ?? [];
  const chosen = rows.filter((c) => picked.has(c.id));
  const expected = sumMoney(chosen.map((c) => c.amount));
  const declaredValue = declared || expected;
  const diff = isValidAmount(declaredValue) ? subtract(expected, declaredValue) : null;

  const m = useMutation({
    mutationFn: () => api.post("/submissions/", { collection_ids: [...picked], declared_amount: declaredValue, note }),
    onSuccess: () => { qc.invalidateQueries(); nav("/submissions"); },
  });

  const toggle = (id: number) => setPicked((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const allOn = rows.length > 0 && picked.size === rows.length;

  return (
    <div>
      <PageHeader title="Submit cash to branch" subtitle="Select the cash collections you are handing over. The branch manager will count and verify them." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Cash in hand" className="lg:col-span-2" padded={false}
          actions={rows.length > 0 && <button className="text-xs font-medium text-brand-700" onClick={() => setPicked(allOn ? new Set() : new Set(rows.map((r) => r.id)))}>{allOn ? "Clear" : "Select all"}</button>}>
          {isLoading ? <Spinner /> : (
            <Table empty={!rows.length} head={<tr><th className="th w-8" /><th className="th">Receipt</th><th className="th">Collected</th><th className="th">Customer</th><th className="th num">Amount</th></tr>}>
              {rows.map((c) => (
                <tr key={c.id} className="cursor-pointer hover:bg-slate-50" onClick={() => toggle(c.id)}>
                  <td className="td"><input type="checkbox" checked={picked.has(c.id)} onChange={() => toggle(c.id)} onClick={(e) => e.stopPropagation()} className="h-4 w-4 rounded border-slate-300 text-brand-600" /></td>
                  <td className="td font-mono text-xs">{c.receipt_number}</td>
                  <td className="td">{formatDateTime(c.collected_at)}</td>
                  <td className="td">{c.customer_name}</td>
                  <td className="td num"><Amount value={c.amount} /></td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
        <Card title="Handover summary">
          <div className="space-y-4">
            <div className="flex justify-between text-sm"><span className="text-slate-500">Collections selected</span><span className="font-medium">{picked.size}</span></div>
            <div className="flex justify-between text-sm"><span className="text-slate-500">Expected cash</span><span className="text-lg font-semibold tabular-nums">{formatINR(expected)}</span></div>
            <Field label="Cash you are handing over (₹)" hint="Leave blank if it equals the expected amount.">
              <input className="input tabular-nums" inputMode="decimal" placeholder={expected} value={declared} onChange={(e) => setDeclared(e.target.value.replace(/[^\d.]/g, ""))} />
            </Field>
            {diff && compare(diff, "0") !== 0 && <Alert kind="warning">Declared amount differs from expected by {formatINR(diff)}. Add a note explaining why.</Alert>}
            <Field label="Note (optional)"><input className="input" maxLength={255} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
            {m.isError && <Alert>{errorText(m.error)}</Alert>}
            <Button className="w-full" loading={m.isPending} disabled={!picked.size || !isValidAmount(declaredValue)} onClick={() => m.mutate()}>Submit to branch</Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
