import { createApp } from "vue";
import ProteinViewer from "../../src/components/common/ProteinViewer.vue";
// Two synthetic peptide chains with repeated residue IDs test chain isolation.
let serial = 0;
const lines = [];
for (const [chain, offset] of [
  ["A", 0],
  ["B", 15],
]) {
  for (let i = 1; i <= 25; i++) {
    const theta = (i * 100 * Math.PI) / 180;
    for (const [name, dx, element] of [
      ["N", -0.7, "N"],
      ["CA", 0, "C"],
      ["C", 0.7, "C"],
      ["O", 1.1, "O"],
      ["CB", 0.2, "C"],
    ]) {
      const x = offset + 2.3 * Math.cos(theta) + dx,
        y = 2.3 * Math.sin(theta) + (name === "CB" ? 1 : 0),
        z = i * 1.5;
      lines.push(
        `ATOM  ${String(++serial).padStart(5)} ${name.padStart(4)} ALA ${chain}${String(i).padStart(4)}    ${x.toFixed(3).padStart(8)}${y.toFixed(3).padStart(8)}${z.toFixed(3).padStart(8)}  1.00${(i % 2 ? 95 : 65).toFixed(2).padStart(6)}          ${element.padStart(2)}`,
      );
    }
  }
  lines.push("TER");
}
createApp(ProteinViewer, {
  structure: lines.join("\n") + "\nEND\n",
  title: "Synthetic two-chain peptide",
  confidenceType: "plddt",
  sites: [
    {
      key: "0",
      position: 8,
      residue: "ALA",
      type: "Catalytic Site",
      confidence: 0.95,
      chain: null,
    },
    {
      key: "1",
      position: 14,
      residue: "ALA",
      type: "Binding Site",
      confidence: 0.72,
      chain: "B",
    },
  ],
}).mount("#app");
