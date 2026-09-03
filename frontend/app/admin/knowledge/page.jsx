"use client";

import { useState } from "react";
import Button from "@/app/admin/_components/ui/Button";
import Badge from "@/app/admin/_components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import Modal from "@/app/admin/_components/ui/Modal";
import { knowledgeArticles } from "@/app/admin/data";

export default function KnowledgePage() {
  const [open, setOpen] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Knowledge base</h1>
          <p className="mt-1 text-xs text-text-secondary">
            Articles used to ground Vocira&apos;s answers.
          </p>
        </div>
        <Button onClick={() => setOpen(true)}>Add Article</Button>
      </div>

      <Table>
        <THead>
          <TR>
            <TH>Title</TH>
            <TH>Category</TH>
            <TH>Last Updated</TH>
            <TH>Status</TH>
            <TH className="text-right">Actions</TH>
          </TR>
        </THead>
        <TBody>
          {knowledgeArticles.map((a) => (
            <TR key={a.title}>
              <TD className="text-xs text-white">{a.title}</TD>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {a.category}
              </TD>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {a.updated}
              </TD>
              <TD>
                <Badge
                  label={a.status}
                  variant={a.status === "Published" ? "success" : "warning"}
                />
              </TD>
              <TD className="whitespace-nowrap text-right">
                <div className="flex justify-end gap-1">
                  <Button variant="ghost">Edit</Button>
                  <Button variant="ghost">Delete</Button>
                </div>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <Modal open={open} onClose={() => setOpen(false)} title="Add article">
        <div className="grid gap-3">
          <label className="space-y-1 text-xs">
            <span className="font-semibold text-text-secondary">Title</span>
            <input
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white placeholder:text-text-secondary/70 outline-none focus:ring-2 focus:ring-accent-primary/60"
              placeholder="e.g. Attendance policy"
            />
          </label>
          <label className="space-y-1 text-xs">
            <span className="font-semibold text-text-secondary">Category</span>
            <input
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white placeholder:text-text-secondary/70 outline-none focus:ring-2 focus:ring-accent-primary/60"
              placeholder="e.g. Logistics"
            />
          </label>
          <label className="space-y-1 text-xs">
            <span className="font-semibold text-text-secondary">Content</span>
            <textarea
              rows={6}
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white placeholder:text-text-secondary/70 outline-none focus:ring-2 focus:ring-accent-primary/60"
              placeholder="Write the article content here..."
            />
          </label>
          <div className="mt-2 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button>Save</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

