<template>
  <div class="scientific-data">
    <template v-if="Array.isArray(value)">
      <p v-if="!value.length" class="data-empty">No entries returned.</p>
      <ResultPreview v-else-if="tableColumns.length" :title="title" :note="`${value.length} rows · ${tableColumns.length} columns in this result view`">
      <div class="data-table-scroll">
        <table>
          <thead>
            <tr>
              <th v-for="column in tableColumns" :key="column" scope="col">
                {{ label(column) }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in value" :key="index">
              <td v-for="column in tableColumns" :key="column" :class="{ 'numeric-value': typeof row[column] === 'number' }">
                {{ display(row[column]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      </ResultPreview>
      <ol v-else>
        <li v-for="(item, index) in value" :key="index">
          <ScientificData :value="item" :depth="depth + 1" :column-order="columnOrder" :title="title" />
        </li>
      </ol>
    </template>
    <template v-else-if="value && typeof value === 'object'">
      <template v-for="[key, item] in entries" :key="key"
        ><dl v-if="isScalar(item)">
          <dt>{{ label(key) }}</dt>
          <dd :class="{ sequence: isSequence(key, item) }">
            {{ display(item) }}
          </dd>
        </dl>
        <details v-else :open="depth === 0">
          <summary>
            {{ label(key) }}
            <span v-if="Array.isArray(item)">{{ item.length }} entries</span>
          </summary>
          <ScientificData :value="item" :depth="depth + 1" :column-order="columnOrder" :title="label(key)" /></details
      ></template>
    </template>
    <span v-else>{{ display(value) }}</span>
  </div>
</template>
<script setup>
import { computed } from "vue";
import ResultPreview from './ResultPreview.vue';
const props = defineProps({
  value: { required: true },
  depth: { type: Number, default: 0 },
  columnOrder: { type: Array, default: () => [] },
  title: { type: String, default: 'Result table' },
});
const omitted = new Set([
  "success",
  "structure_data",
  "pdb_content",
  "pdb_text",
  "structure_html",
  "html",
  "workspace_result",
  "active_data",
  "residue_labels",
  "alignments",
  "markdown",
  "formatted",
]);
const entries = computed(() =>
  Object.entries(props.value || {}).filter(([key]) => !omitted.has(key)),
);
const isScalar = (value) => value === null || typeof value !== "object";
const label = (key) =>
  key
    .replaceAll("_", " ")
    .replace(
      /\b(ec|pdb|uniprot|smiles|km|kcat|vmax)\b/gi,
      (m) =>
        ({ ec: "EC", pdb: "PDB", uniprot: "UniProt", smiles: "SMILES", km: "Km", kcat: "kcat", vmax: "Vmax" })[
          m.toLowerCase()
        ],
    );
const display = (value) =>
  value === null || value === undefined || value === ""
    ? "—"
    : typeof value === "boolean"
      ? value
        ? "Yes"
        : "No"
      : String(value);
const isSequence = (key, value) =>
  /sequence|fasta/i.test(key) && typeof value === "string";
const tableColumns = computed(() => {
  if (
    !Array.isArray(props.value) ||
    !props.value.length ||
    !props.value.every(
      (row) => row && typeof row === "object" && !Array.isArray(row),
    )
  )
    return [];
  const keys = [...new Set(props.value.flatMap(Object.keys))].filter(
    (k) => !omitted.has(k),
  );
  const columns = [...new Set([...props.columnOrder.filter(k => keys.includes(k)), ...keys])];
  return columns.length <= 8 &&
    props.value.every((row) => columns.every((k) => isScalar(row[k])))
    ? columns
    : [];
});
</script>
<style scoped>
.scientific-data {
  font-size: 13px;
  color: var(--color-text-secondary);
  min-width: 0;
}
.scientific-data dl {
  display: grid;
  grid-template-columns: minmax(100px, 30%) minmax(0, 1fr);
  gap: 16px;
  margin: 0;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-background-alt);
}
.scientific-data dt {
  text-transform: capitalize;
  font-size: 12px;
  color: var(--color-text-muted);
}
.scientific-data dd {
  margin: 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
.sequence {
  font-family: var(--font-mono);
  font-size: 11px;
  max-height: 180px;
  overflow: auto;
}
.scientific-data details {
  border: 1px solid var(--color-background-alt);
  border-radius: var(--radius-md);
  margin: 12px 0;
  padding: 12px;
}
.scientific-data summary {
  cursor: pointer;
  text-transform: capitalize;
  font-weight: 600;
}
.scientific-data summary span {
  font-weight: 400;
  font-size: 10px;
  color: var(--color-text-muted);
  margin-left: 8px;
}
.scientific-data ol {
  padding-left: 22px;
}
.scientific-data li {
  padding: 5px;
}
.data-table-scroll {
  max-height: 400px;
  overflow: auto;
}
.scientific-data table {
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
}
.scientific-data th {
  background: var(--color-background-alt);
  position: sticky;
  top: 0;
  text-transform: capitalize;
}
.scientific-data th,
.scientific-data td {
  text-align: left;
  border-bottom: 1px solid var(--color-background-alt);
  padding: 9px;
  overflow-wrap: anywhere;
  max-width: 260px;
}
.data-empty {
  color: var(--color-text-muted);
  font-size: 12px;
  margin: 12px 0;
}
</style>
