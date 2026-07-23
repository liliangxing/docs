const fs = require("fs");
const path = require("path");
const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  AlignmentType,
  Table,
  TableRow,
  TableCell,
  BorderStyle,
  WidthType,
  ShadingType,
  PageNumber,
  Footer,
  Header,
  convertInchesToTwip,
} = require("docx");

// ========== 颜色常量 ==========
const COLORS = {
  primary: "1A73E8",
  secondary: "34A853",
  warning: "EA4335",
  highlight: "FFF3CD",
  codeBg: "F5F5F5",
  codeText: "D63384",
  headingBg: "E8F0FE",
  tableBorder: "DADCE0",
  tableHeaderBg: "1A73E8",
  tableHeaderText: "FFFFFF",
  tableAltRowBg: "F8F9FA",
  warningBg: "FFF3CD",
  warningBorder: "FFCC00",
};

// ========== 读取 MD 内容 ==========
const mdContent = fs.readFileSync(
  path.join(__dirname, "Codebase-Indexing-搭建指南.md"),
  "utf-8"
);

// ========== 解析 Markdown 为段落结构 ==========
function parseMarkdown(content) {
  const lines = content.split("\n");
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // 标题
    if (trimmed.startsWith("# ")) {
      blocks.push({ type: "h1", text: trimmed.replace(/^#\s*/, "") });
    } else if (trimmed.startsWith("## ")) {
      blocks.push({ type: "h2", text: trimmed.replace(/^##\s*/, "") });
    } else if (trimmed.startsWith("### ")) {
      blocks.push({ type: "h3", text: trimmed.replace(/^###\s*/, "") });
    } else if (trimmed.startsWith("#### ")) {
      blocks.push({ type: "h4", text: trimmed.replace(/^####\s*/, "") });
    }
    // 引用块
    else if (trimmed.startsWith("> ")) {
      const quoteLines = [];
      while (i < lines.length && lines[i].trim().startsWith("> ")) {
        quoteLines.push(lines[i].trim().replace(/^>\s*/, ""));
        i++;
      }
      blocks.push({ type: "quote", text: quoteLines.join("\n") });
      continue;
    }
    // 分隔线
    else if (trimmed.startsWith("---")) {
      blocks.push({ type: "hr" });
    }
    // 表格
    else if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      const tableRows = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        const cells = lines[i]
          .trim()
          .split("|")
          .slice(1, -1)
          .map((c) => c.trim());
        // 跳过对齐行
        if (!cells[0]?.includes("---")) {
          tableRows.push(cells);
        }
        i++;
      }
      if (tableRows.length > 0) {
        blocks.push({ type: "table", rows: tableRows });
      }
      continue;
    }
    // 代码块（反引号）
    else if (trimmed.startsWith("```")) {
      const lang = trimmed.replace(/^```/, "").trim();
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      blocks.push({ type: "code", lang, code: codeLines.join("\n") });
    }
    // 无序列表
    else if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      const items = [];
      while (i < lines.length && (lines[i].trim().startsWith("- ") || lines[i].trim().startsWith("* "))) {
        items.push(lines[i].trim().replace(/^[-*]\s*/, ""));
        i++;
      }
      blocks.push({ type: "ul", items });
      continue;
    }
    // 编号列表
    else if (/^\d+\.\s/.test(trimmed)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+\.\s*/, ""));
        i++;
      }
      blocks.push({ type: "ol", items });
      continue;
    }
    // 普通段落
    else if (trimmed.length > 0) {
      const lines_collected = [trimmed];
      i++;
      while (
        i < lines.length &&
        lines[i].trim().length > 0 &&
        !lines[i].trim().startsWith("#") &&
        !lines[i].trim().startsWith("|") &&
        !lines[i].trim().startsWith("- ") &&
        !lines[i].trim().startsWith("* ") &&
        !lines[i].trim().startsWith("```") &&
        !lines[i].trim().startsWith(">") &&
        !/^\d+\.\s/.test(lines[i].trim()) &&
        !lines[i].trim().startsWith("---")
      ) {
        lines_collected.push(lines[i].trim());
        i++;
      }
      blocks.push({ type: "p", text: lines_collected.join(" ") });
      continue;
    }

    i++;
  }

  return blocks;
}

// ========== 渲染内联格式（粗体、代码、链接） ==========
function renderInline(text) {
  if (!text) return [new TextRun({ text: text || "", size: 22 })];
  const parts = [];
  let remaining = text;

  // 处理 **粗体**
  const boldRegex = /\*\*(.+?)\*\*/g;
  let lastIdx = 0;
  let match;

  while ((match = boldRegex.exec(remaining)) !== null) {
    if (match.index > lastIdx) {
      const before = remaining.slice(lastIdx, match.index);
      parts.push(...renderInlineCode(before));
    }
    parts.push(
      new TextRun({
        text: match[1],
        bold: true,
        size: 22,
        color: COLORS.primary,
      })
    );
    lastIdx = match.index + match[0].length;
  }

  if (lastIdx < remaining.length) {
    parts.push(...renderInlineCode(remaining.slice(lastIdx)));
  }

  return parts.length > 0 ? parts : [new TextRun({ text: text, size: 22 })];
}

function renderInlineCode(text) {
  const parts = [];
  const codeRegex = /`([^`]+)`/g;
  let lastIdx = 0;
  let match;

  while ((match = codeRegex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(
        new TextRun({ text: text.slice(lastIdx, match.index), size: 22 })
      );
    }
    parts.push(
      new TextRun({
        text: match[1],
        font: "Consolas",
        size: 20,
        color: COLORS.codeText,
        shading: { type: ShadingType.CLEAR, color: COLORS.codeBg, fill: COLORS.codeBg },
      })
    );
    lastIdx = match.index + match[0].length;
  }

  if (lastIdx < text.length) {
    parts.push(new TextRun({ text: text.slice(lastIdx), size: 22 }));
  }

  return parts;
}

// ========== 构建文档段落 ==========
function buildParagraphs(blocks) {
  const paragraphs = [];

  for (const block of blocks) {
    switch (block.type) {
      case "h1": {
        paragraphs.push(
          new Paragraph({
            text: block.text,
            heading: HeadingLevel.HEADING_1,
            spacing: { before: 400, after: 200 },
            shading: { type: ShadingType.CLEAR, color: COLORS.headingBg, fill: COLORS.headingBg },
            border: {
              bottom: { color: COLORS.primary, size: 6, style: BorderStyle.SINGLE, space: 4 },
            },
          })
        );
        // 截图占位
        paragraphs.push(
          new Paragraph({
            children: [new TextRun({
              text: `[截图位置：${block.text} — 请在此处插入截图]`,
              size: 18,
              color: "999999",
              italics: true,
            })],
            spacing: { after: 100 },
            alignment: AlignmentType.CENTER,
          })
        );
        break;
      }
      case "h2": {
        paragraphs.push(
          new Paragraph({
            text: block.text,
            heading: HeadingLevel.HEADING_2,
            spacing: { before: 300, after: 150 },
            shading: { type: ShadingType.CLEAR, color: COLORS.headingBg, fill: COLORS.headingBg },
          })
        );
        break;
      }
      case "h3": {
        paragraphs.push(
          new Paragraph({
            text: block.text,
            heading: HeadingLevel.HEADING_3,
            spacing: { before: 200, after: 100 },
          })
        );
        break;
      }
      case "h4": {
        paragraphs.push(
          new Paragraph({
            text: block.text,
            heading: HeadingLevel.HEADING_4,
            spacing: { before: 150, after: 80 },
          })
        );
        break;
      }
      case "p": {
        paragraphs.push(
          new Paragraph({
            children: renderInline(block.text),
            spacing: { after: 100 },
            alignment: AlignmentType.JUSTIFIED,
          })
        );
        break;
      }
      case "quote": {
        const quoteLines = block.text.split("\n");
        quoteLines.forEach((line) => {
          paragraphs.push(
            new Paragraph({
              children: renderInline(line),
              spacing: { before: 40, after: 40 },
              indent: { left: 600, right: 400 },
              shading: {
                type: ShadingType.CLEAR,
                color: COLORS.warningBg,
                fill: COLORS.warningBg,
              },
              border: {
                left: { color: COLORS.warningBorder, size: 12, style: BorderStyle.SINGLE, space: 8 },
              },
            })
          );
        });
        paragraphs.push(new Paragraph({ spacing: { after: 80 } }));
        break;
      }
      case "code": {
        const codeLines = block.code.split("\n");
        codeLines.forEach((line, idx) => {
          paragraphs.push(
            new Paragraph({
              children: [
                new TextRun({
                  text: line || " ",
                  font: "Consolas",
                  size: 18,
                  color: "2D2D2D",
                }),
              ],
              spacing: { before: 0, after: 0 },
              shading: {
                type: ShadingType.CLEAR,
                color: COLORS.codeBg,
                fill: COLORS.codeBg,
              },
              indent: { left: 400, right: 400 },
            })
          );
        });
        // 代码块后加空行
        paragraphs.push(
          new Paragraph({
            spacing: { before: 60, after: 60 },
            shading: {
              type: ShadingType.CLEAR,
              color: COLORS.codeBg,
              fill: COLORS.codeBg,
            },
            indent: { left: 400, right: 400 },
            children: [new TextRun({ text: " ", size: 10 })],
          })
        );
        break;
      }
      case "ul": {
        block.items.forEach((item) => {
          const parts = renderInline(item);
          parts.unshift(
            new TextRun({ text: "•  ", size: 22, color: COLORS.primary })
          );
          paragraphs.push(
            new Paragraph({
              children: parts,
              spacing: { after: 60 },
              indent: { left: 400 },
            })
          );
        });
        break;
      }
      case "ol": {
        block.items.forEach((item, idx) => {
          const parts = renderInline(item);
          parts.unshift(
            new TextRun({
              text: `${idx + 1}. `,
              size: 22,
              color: COLORS.primary,
              bold: true,
            })
          );
          paragraphs.push(
            new Paragraph({
              children: parts,
              spacing: { after: 60 },
              indent: { left: 400 },
            })
          );
        });
        break;
      }
      case "hr": {
        paragraphs.push(
          new Paragraph({
            spacing: { before: 200, after: 200 },
            border: {
              bottom: {
                color: COLORS.tableBorder,
                size: 6,
                style: BorderStyle.SINGLE,
                space: 1,
              },
            },
          })
        );
        break;
      }
      case "table": {
        if (block.rows.length === 0) break;

        const headers = block.rows[0];
        const dataRows = block.rows.slice(1);

        const tableRows = [];

        // 表头
        tableRows.push(
          new TableRow({
            tableHeader: true,
            children: headers.map(
              (h) =>
                new TableCell({
                  children: [
                    new Paragraph({
                      children: [
                        new TextRun({
                          text: h,
                          bold: true,
                          size: 20,
                          color: COLORS.tableHeaderText,
                        }),
                      ],
                      alignment: AlignmentType.CENTER,
                    }),
                  ],
                  shading: {
                    type: ShadingType.CLEAR,
                    color: COLORS.tableHeaderBg,
                    fill: COLORS.tableHeaderBg,
                  },
                  width: { size: 20, type: WidthType.PERCENTAGE },
                })
            ),
          })
        );

        // 数据行
        dataRows.forEach((row, rowIdx) => {
          const maxCols = Math.max(headers.length, row.length);
          const cells = [];
          for (let c = 0; c < maxCols; c++) {
            const cellText = c < row.length ? row[c] : "";
            cells.push(
              new TableCell({
                children: [
                  new Paragraph({
                    children: renderInline(cellText),
                    size: 20,
                  }),
                ],
                shading:
                  rowIdx % 2 === 1
                    ? {
                        type: ShadingType.CLEAR,
                        color: COLORS.tableAltRowBg,
                        fill: COLORS.tableAltRowBg,
                      }
                    : undefined,
              })
            );
          }
          tableRows.push(new TableRow({ children: cells }));
        });

        paragraphs.push(
          new Table({
            rows: tableRows,
            width: { size: 100, type: WidthType.PERCENTAGE },
            borders: {
              top: { color: COLORS.tableBorder, size: 1, style: BorderStyle.SINGLE },
              bottom: { color: COLORS.tableBorder, size: 1, style: BorderStyle.SINGLE },
              left: { color: COLORS.tableBorder, size: 1, style: BorderStyle.SINGLE },
              right: { color: COLORS.tableBorder, size: 1, style: BorderStyle.SINGLE },
              insideHorizontal: { color: COLORS.tableBorder, size: 1, style: BorderStyle.SINGLE },
              insideVertical: { color: COLORS.tableBorder, size: 1, style: BorderStyle.SINGLE },
            },
          })
        );

        // 表格后空行
        paragraphs.push(new Paragraph({ spacing: { after: 100 } }));
        break;
      }
    }
  }

  return paragraphs;
}

// ========== 创建 Document ==========
async function main() {
  const blocks = parseMarkdown(mdContent);
  const paragraphs = buildParagraphs(blocks);

  // 文档属性
  const doc = new Document({
    creator: "CatPaw AI Assistant",
    title: "Codebase Indexing 完整搭建指南",
    description: "Windows 10 环境下配置 Roo Cline / Kilo Code Codebase Indexing 的完整指南",
    styles: {
      default: {
        document: {
          run: {
            size: "22pt",
            font: "Microsoft YaHei",
          },
          paragraph: {
            spacing: {
              after: 100,
            },
          },
        },
      },
    },
    sections: [
      {
        properties: {
          page: {
            margin: {
              top: convertInchesToTwip(0.8),
              right: convertInchesToTwip(0.8),
              bottom: convertInchesToTwip(0.8),
              left: convertInchesToTwip(0.8),
            },
          },
        },
        headers: {
          default: new Header({
            children: [
              new Paragraph({
                alignment: AlignmentType.RIGHT,
                children: [
                  new TextRun({
                    text: "Codebase Indexing 完整搭建指南",
                    size: 16,
                    color: "999999",
                    italics: true,
                  }),
                ],
              }),
            ],
          }),
        },
        footers: {
          default: new Footer({
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [
                  new TextRun({
                    children: [PageNumber.CURRENT],
                    size: 16,
                    color: "999999",
                  }),
                  new TextRun({
                    text: " / ",
                    size: 16,
                    color: "999999",
                  }),
                  new TextRun({
                    children: [PageNumber.TOTAL_PAGES],
                    size: 16,
                    color: "999999",
                  }),
                ],
              }),
            ],
          }),
        },
        children: paragraphs,
      },
    ],
  });

  // 生成 DOCX
  const buffer = await Packer.toBuffer(doc);
  const outputPath = path.join(__dirname, "Codebase-Indexing-搭建指南.docx");
  fs.writeFileSync(outputPath, buffer);

  console.log(`✅ DOCX 生成成功: ${outputPath}`);
  console.log(`   文件大小: ${(buffer.length / 1024).toFixed(1)} KB`);
}

main().catch(console.error);
