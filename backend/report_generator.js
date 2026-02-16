/**
 * FinSight Word Report Generator
 * Creates a professional client-facing financial analysis report (.docx)
 *
 * Usage: node report_generator.js <analysis_json_path> <output_docx_path>
 */

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageBreak, LevelFormat, PageNumber, TabStopType, TabStopPosition,
  PositionalTab, PositionalTabAlignment, PositionalTabRelativeTo, PositionalTabLeader,
} = require("docx");

const args = process.argv.slice(2);
if (args.length < 2) {
  console.error("Usage: node report_generator.js <analysis.json> <output.docx>");
  process.exit(1);
}

const analysisPath = args[0];
const outputPath = args[1];
const analysis = JSON.parse(fs.readFileSync(analysisPath, "utf8"));

// Helpers
const fmt = (n) => {
  const abs = Math.abs(n);
  const s = abs.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return n < 0 ? `-$${s}` : `$${s}`;
};
const pct = (n) => `${(n * 100).toFixed(1)}%`;

// Style constants
const PRIMARY = "1E40AF";
const DARK = "1E293B";
const LIGHT_BG = "F1F5F9";
const GREEN = "10B981";
const RED = "EF4444";

const border = { style: BorderStyle.SINGLE, size: 1, color: "D1D5DB" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };

function makeHeaderCell(text, width) {
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: PRIMARY, type: ShadingType.CLEAR },
    margins: cellMargins,
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, bold: true, font: "Arial", size: 18, color: "FFFFFF" })],
    })],
  });
}

function makeCell(text, width, opts = {}) {
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
    margins: cellMargins,
    children: [new Paragraph({
      alignment: opts.align || AlignmentType.LEFT,
      children: [new TextRun({
        text: String(text),
        font: "Arial",
        size: opts.size || 18,
        bold: opts.bold || false,
        color: opts.color || "333333",
      })],
    })],
  });
}

// Build document content
const children = [];

// Title Page
children.push(
  new Paragraph({ spacing: { before: 3000 }, children: [] }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: [new TextRun({ text: "FINANCIAL ANALYSIS REPORT", font: "Arial", size: 56, bold: true, color: PRIMARY })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 100 },
    children: [new TextRun({ text: "Comprehensive Budget Review & Recommendations", font: "Arial", size: 24, color: "64748B" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    border: { top: { style: BorderStyle.SINGLE, size: 6, color: PRIMARY, space: 1 } },
    spacing: { before: 400, after: 400 },
    children: [],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 100 },
    children: [new TextRun({ text: `Analysis Period: ${(analysis.num_periods || []).join(", ") || "N/A"}`, font: "Arial", size: 22, color: "475569" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 100 },
    children: [new TextRun({ text: `Generated: ${new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}`, font: "Arial", size: 22, color: "475569" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 100 },
    children: [new TextRun({ text: "Prepared by FinSight Financial Analysis Platform", font: "Arial", size: 20, italics: true, color: "94A3B8" })],
  }),
  new Paragraph({ children: [new PageBreak()] }),
);

// Executive Summary
children.push(
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text: "1. Executive Summary" })],
  }),
  new Paragraph({
    spacing: { after: 200 },
    children: [new TextRun({
      text: `Over the ${analysis.num_months || 0}-month analysis period, total income was ${fmt(analysis.total_income || 0)} ` +
        `with total expenses of ${fmt(analysis.total_expenses || 0)}, resulting in net savings of ${fmt(analysis.net_savings || 0)}. ` +
        `The current savings rate is ${pct(analysis.savings_rate || 0)}, which ` +
        `${(analysis.savings_rate || 0) >= 0.20 ? "meets" : "falls below"} the recommended target of 20%.`,
      font: "Arial", size: 22,
    })],
  }),
  new Paragraph({
    spacing: { after: 200 },
    children: [new TextRun({
      text: `Based on our analysis, we have identified ${(analysis.recommendations || []).length} areas where spending can be optimized, ` +
        `with a total potential monthly savings of ${fmt(analysis.total_potential_monthly_savings || 0)}. ` +
        `Implementing these recommendations could increase the savings rate to approximately ` +
        `${pct(((analysis.avg_monthly_savings || 0) + (analysis.total_potential_monthly_savings || 0)) / (analysis.avg_monthly_income || 1))}.`,
      font: "Arial", size: 22,
    })],
  }),
);

// Key Metrics Table
const metricsWidth = 9360;
const col1 = 5000;
const col2 = 4360;

children.push(
  new Paragraph({ spacing: { before: 300 }, children: [] }),
  new Table({
    width: { size: metricsWidth, type: WidthType.DXA },
    columnWidths: [col1, col2],
    rows: [
      new TableRow({ children: [makeHeaderCell("Metric", col1), makeHeaderCell("Value", col2)] }),
      new TableRow({ children: [makeCell("Average Monthly Income", col1), makeCell(fmt(analysis.avg_monthly_income || 0), col2, { align: AlignmentType.RIGHT, bold: true, color: GREEN })] }),
      new TableRow({ children: [makeCell("Average Monthly Expenses", col1, { fill: LIGHT_BG }), makeCell(fmt(analysis.avg_monthly_expenses || 0), col2, { align: AlignmentType.RIGHT, bold: true, color: RED, fill: LIGHT_BG })] }),
      new TableRow({ children: [makeCell("Average Monthly Savings", col1), makeCell(fmt(analysis.avg_monthly_savings || 0), col2, { align: AlignmentType.RIGHT, bold: true, color: PRIMARY })] }),
      new TableRow({ children: [makeCell("Current Savings Rate", col1, { fill: LIGHT_BG }), makeCell(pct(analysis.savings_rate || 0), col2, { align: AlignmentType.RIGHT, bold: true, fill: LIGHT_BG })] }),
      new TableRow({ children: [makeCell("Total Transactions Analyzed", col1), makeCell(String(analysis.total_transactions || 0), col2, { align: AlignmentType.RIGHT })] }),
    ],
  }),
  new Paragraph({ children: [new PageBreak()] }),
);

// Category Breakdown
children.push(
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text: "2. Spending by Category" })],
  }),
  new Paragraph({
    spacing: { after: 200 },
    children: [new TextRun({
      text: "The following table breaks down average monthly spending by category, compared against recommended budget allocations based on the client's income level.",
      font: "Arial", size: 22,
    })],
  }),
);

const catCols = [2200, 1600, 1800, 1600, 2160];
const catRows = [
  new TableRow({
    children: ["Category", "Actual/Mo", "Budget/Mo", "Difference", "Status"].map((h, i) => makeHeaderCell(h, catCols[i])),
  }),
];

for (const cat of (analysis.category_breakdown || [])) {
  const diff = cat.budget - cat.actual;
  const statusColor = cat.status === "Over Budget" ? RED : cat.status === "Under Budget" ? GREEN : "F59E0B";
  const statusFill = cat.status === "Over Budget" ? "FEE2E2" : cat.status === "Under Budget" ? "DCFCE7" : "FEF9C3";

  catRows.push(new TableRow({
    children: [
      makeCell(cat.name, catCols[0], { bold: true }),
      makeCell(fmt(cat.actual), catCols[1], { align: AlignmentType.RIGHT }),
      makeCell(fmt(cat.budget), catCols[2], { align: AlignmentType.RIGHT }),
      makeCell(fmt(diff), catCols[3], { align: AlignmentType.RIGHT, color: diff >= 0 ? GREEN : RED, bold: true }),
      makeCell(cat.status, catCols[4], { align: AlignmentType.CENTER, color: statusColor, fill: statusFill, bold: true }),
    ],
  }));
}

children.push(
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: catCols,
    rows: catRows,
  }),
  new Paragraph({ children: [new PageBreak()] }),
);

// Recommendations
children.push(
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text: "3. Savings Recommendations" })],
  }),
  new Paragraph({
    spacing: { after: 200 },
    children: [new TextRun({
      text: "The following recommendations are prioritized by potential monthly savings impact. " +
        "Implementing all recommendations could result in additional monthly savings of " +
        `${fmt(analysis.total_potential_monthly_savings || 0)}.`,
      font: "Arial", size: 22,
    })],
  }),
);

for (const [i, rec] of (analysis.recommendations || []).entries()) {
  children.push(
    new Paragraph({
      heading: HeadingLevel.HEADING_2,
      children: [new TextRun({ text: `3.${i + 1}  ${rec.area} — Save ${fmt(rec.savings)}/month` })],
    }),
    new Paragraph({
      spacing: { after: 80 },
      children: [
        new TextRun({ text: "Current: ", font: "Arial", size: 20, bold: true }),
        new TextRun({ text: `${fmt(rec.current)}/mo`, font: "Arial", size: 20, color: RED }),
        new TextRun({ text: "    Target: ", font: "Arial", size: 20, bold: true }),
        new TextRun({ text: `${fmt(rec.target)}/mo`, font: "Arial", size: 20, color: GREEN }),
        new TextRun({ text: `    Priority: ${rec.priority}`, font: "Arial", size: 20, bold: true }),
      ],
    }),
    new Paragraph({
      spacing: { after: 200 },
      children: [new TextRun({ text: rec.detail, font: "Arial", size: 22 })],
    }),
  );
}

children.push(new Paragraph({ children: [new PageBreak()] }));

// Investment Projections
const proj = analysis.investment_projection || {};
children.push(
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text: "4. Wealth Growth Projections" })],
  }),
  new Paragraph({
    spacing: { after: 200 },
    children: [new TextRun({
      text: `If the recommended changes are implemented, the projected monthly investment capacity would be ` +
        `${fmt(proj.monthly_investment || 0)}. Assuming an average annual return of ${pct(proj.assumed_annual_return || 0.07)} ` +
        `(historical stock market average), the following growth trajectory is projected:`,
      font: "Arial", size: 22,
    })],
  }),
);

const projCols = [4680, 4680];
const projRows = [
  new TableRow({ children: ["Time Horizon", "Projected Portfolio Value"].map((h, i) => makeHeaderCell(h, projCols[i])) }),
];
for (const [key, label] of [["1_year", "1 Year"], ["3_year", "3 Years"], ["5_year", "5 Years"], ["10_year", "10 Years"], ["15_year", "15 Years"], ["20_year", "20 Years"], ["30_year", "30 Years"]]) {
  if (proj[key] !== undefined) {
    projRows.push(new TableRow({
      children: [
        makeCell(label, projCols[0], { bold: true }),
        makeCell(fmt(proj[key]), projCols[1], { align: AlignmentType.RIGHT, bold: true, color: PRIMARY }),
      ],
    }));
  }
}

children.push(
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: projCols,
    rows: projRows,
  }),
  new Paragraph({
    spacing: { before: 300, after: 200 },
    children: [new TextRun({
      text: "Note: These projections are for illustrative purposes only and assume consistent monthly contributions " +
        "and a constant rate of return. Actual investment returns will vary. Past performance is not indicative of future results. " +
        "Consult with a licensed financial advisor before making investment decisions.",
      font: "Arial", size: 18, italics: true, color: "94A3B8",
    })],
  }),
  new Paragraph({ children: [new PageBreak()] }),
);

// Conclusion
children.push(
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text: "5. Conclusion & Next Steps" })],
  }),
  new Paragraph({
    spacing: { after: 200 },
    children: [new TextRun({
      text: `This analysis reveals a solid financial foundation with a current savings rate of ${pct(analysis.savings_rate || 0)}. ` +
        `However, there is meaningful room for improvement. By implementing the ${(analysis.recommendations || []).length} recommendations outlined above, ` +
        `the client can potentially save an additional ${fmt(analysis.total_potential_monthly_savings || 0)} per month, ` +
        `bringing the total monthly savings capacity to approximately ${fmt((analysis.avg_monthly_savings || 0) + (analysis.total_potential_monthly_savings || 0))}.`,
      font: "Arial", size: 22,
    })],
  }),
  new Paragraph({
    spacing: { after: 200 },
    children: [new TextRun({
      text: "Recommended next steps: (1) Review and prioritize the savings recommendations based on personal lifestyle preferences. " +
        "(2) Set up automatic transfers to a dedicated savings/investment account for the targeted savings amount. " +
        "(3) Schedule a follow-up review in 90 days to assess progress and adjust the plan as needed. " +
        "(4) Consult with a licensed financial advisor regarding specific investment allocation strategies.",
      font: "Arial", size: 22,
    })],
  }),
);

// Create document
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: PRIMARY },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: "334155" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 },
      },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "FinSight Financial Analysis", font: "Arial", size: 16, color: "94A3B8", italics: true })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "Page ", font: "Arial", size: 16, color: "94A3B8" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: "94A3B8" }),
            new TextRun({ text: " — Confidential", font: "Arial", size: 16, color: "94A3B8" }),
          ],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(outputPath, buffer);
  console.log(`Report generated: ${outputPath}`);
});
