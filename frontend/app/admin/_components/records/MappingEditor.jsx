"use client";

/*
 * The mapping step: which of the source's columns fills each of Vocira's
 * fields for one table. Vocira suggests a column for every field it can
 * recognise ("Adm No" for the student ID); the admin only fixes what it
 * could not. Fields marked * must have a column.
 */

import { LABEL, SELECT } from "./shared";

export default function MappingEditor({ table, columns, value, onChange }) {
  if (!table) return null;
  const mapping = value || {};
  const used = new Set(Object.values(mapping).filter(Boolean));

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {table.fields.map((field) => {
        const chosen = mapping[field.name] || "";
        return (
          <label key={field.name} className="block min-w-0">
            <span className={LABEL}>
              {field.label}
              {field.required ? <span className="text-rose-300"> *</span> : null}
            </span>
            <select
              className={SELECT}
              value={chosen}
              onChange={(e) => onChange({ ...mapping, [field.name]: e.target.value })}
            >
              <option value="">— not in this data —</option>
              {columns.map((column) => (
                <option key={column} value={column} disabled={used.has(column) && column !== chosen}>
                  {column}
                </option>
              ))}
            </select>
          </label>
        );
      })}
    </div>
  );
}
