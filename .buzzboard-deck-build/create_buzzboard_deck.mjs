import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "/Users/etu/Documents/Code/GitHub/gameTouch";
const SKILL_DIR = "/Users/etu/.codex/plugins/cache/openai-primary-runtime/presentations/26.921.11914/skills/presentations";
const TMP_DIR = path.join(workspaceDir, ".buzzboard-deck-build");
const FINAL_PPTX = path.join(workspaceDir, "buzzboard-deck", "buzzboard-presentation-v3.pptx");
const RUNTIME_PYTHON = "/Users/etu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3";
const { resolvePresentationFont, finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href,
);

await fs.mkdir(TMP_DIR, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });
const family = resolvePresentationFont({ fontFamily: "Arial" });
const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });

const black = "#0B0B0B";
const yellow = "#FFD21F";
const offWhite = "#F7F4EA";
const gray = "#BBB8AE";
const darkGray = "#191919";

function box(slide, x, y, w, h, fill, radius = false) {
  return slide.shapes.add({
    geometry: radius ? "roundRect" : "rect",
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { fill: "none", width: 0 },
  });
}

function text(slide, value, x, y, w, h, size, color = offWhite, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  shape.text = value;
  shape.text.style = {
    typeface: family,
    fontSize: size,
    bold: opts.bold ?? false,
    color,
    autoFit: "shrinkText",
    verticalAlignment: opts.verticalAlignment ?? "top",
    align: opts.align ?? "left",
  };
  return shape;
}

function base(slide, number) {
  slide.background.fill = black;
  box(slide, 64, 52, 74, 8, yellow);
  text(slide, `0${number}`, 1130, 56, 84, 28, 16, yellow, { bold: true, align: "right" });
}

// Title slide
{
  const slide = presentation.slides.add();
  slide.background.fill = black;
  box(slide, 66, 70, 90, 10, yellow);
  text(slide, "BUZZBOARD", 66, 138, 850, 110, 76, yellow, { bold: true });
  text(slide, "Feel the game in real time", 70, 265, 630, 58, 34, offWhite, { bold: true });
  text(slide, "A tactile sports experience for people who are visually impaired", 70, 340, 610, 66, 23, gray);
  text(slide, "Hackathon project", 70, 616, 350, 28, 17, gray);
  // Minimal tactile grid motif, representing the physical 5x4 board.
  for (let row = 0; row < 4; row += 1) {
    for (let col = 0; col < 5; col += 1) {
      const active = (row === 1 && col === 3) || (row === 2 && col === 2);
      box(slide, 812 + col * 70, 186 + row * 70, 48, 48, active ? yellow : darkGray, true);
    }
  }
  text(slide, "5 × 4 tactile grid", 812, 510, 340, 32, 20, gray);
  slide.speakerNotes.textFrame.setText("Buzzboard hackathon presentation.");
}

// Problem and approach
{
  const slide = presentation.slides.add();
  base(slide, 2);
  text(slide, "The experience", 66, 106, 650, 64, 44, offWhite, { bold: true });
  text(slide, "Sports are social. Following the action should not depend on seeing the field.", 66, 184, 780, 56, 24, gray);
  text(slide, "Our approach", 66, 330, 380, 34, 20, yellow, { bold: true });
  text(slide, "Track the ball from live video and turn its location into a vibration on a physical field.", 66, 380, 760, 98, 34, offWhite, { bold: true });
  box(slide, 914, 177, 236, 366, yellow, true);
  text(slide, "WATCH\n→\nTRACK\n→\nFEEL", 951, 250, 164, 210, 31, black, { bold: true, align: "center" });
  text(slide, "Video to touch", 913, 575, 244, 28, 17, gray, { align: "center" });
  slide.speakerNotes.textFrame.setText("Problem framing based on the team's stated goal.");
}

// How it works
{
  const slide = presentation.slides.add();
  base(slide, 3);
  text(slide, "How Buzzboard works", 66, 106, 750, 64, 44, offWhite, { bold: true });
  const steps = [
    ["01", "Live sports video", "A camera feed gives us the game view."],
    ["02", "Ball detection", "OpenCV processes each frame to locate the ball."],
    ["03", "Tactile output", "The closest of 20 motors vibrates on the board."],
  ];
  steps.forEach(([n, title, body], i) => {
    const y = 220 + i * 132;
    text(slide, n, 70, y, 72, 44, 26, yellow, { bold: true });
    text(slide, title, 180, y, 390, 40, 27, offWhite, { bold: true });
    text(slide, body, 180, y + 47, 470, 48, 18, gray);
    box(slide, 812, y + 4, 300, 62, i === 2 ? yellow : darkGray, true);
    text(slide, i === 0 ? "INPUT" : i === 1 ? "VISION" : "5 × 4 MOTOR GRID", 836, y + 24, 250, 24, 16, i === 2 ? black : yellow, { bold: true, align: "center" });
  });
  slide.speakerNotes.textFrame.setText("Technical flow: live video, OpenCV ball detection, and 20-motor tactile output.");
}

// What we built
{
  const slide = presentation.slides.add();
  base(slide, 4);
  text(slide, "What we built", 66, 106, 650, 64, 44, offWhite, { bold: true });
  text(slide, "A physical board designed to make the field readable by touch.", 66, 184, 770, 44, 23, gray);
  box(slide, 66, 286, 520, 328, darkGray, true);
  text(slide, "20 vibration motors", 104, 334, 360, 38, 28, yellow, { bold: true });
  text(slide, "A 5 × 4 grid maps a ball position to a clear vibration point.", 104, 391, 398, 60, 20, offWhite);
  text(slide, "Custom field inserts", 104, 486, 360, 38, 28, yellow, { bold: true });
  text(slide, "Ridges mark important lines, and magnetic inserts let us change sports.", 104, 543, 398, 56, 20, offWhite);
  text(slide, "FIELD INSERT", 778, 280, 320, 22, 16, yellow, { bold: true, align: "center" });
  box(slide, 735, 324, 400, 204, yellow, true);
  box(slide, 766, 354, 338, 144, black, true);
  for (let i = 1; i < 5; i += 1) box(slide, 766 + i * 67.5, 354, 3, 144, yellow);
  for (let i = 1; i < 4; i += 1) box(slide, 766, 354 + i * 36, 338, 3, yellow);
  text(slide, "Interchangeable sport layouts", 737, 620, 395, 30, 19, gray, { align: "center" });
  slide.speakerNotes.textFrame.setText("Physical board details based on the team's project description.");
}

// Challenges
{
  const slide = presentation.slides.add();
  base(slide, 5);
  text(slide, "Challenges we faced", 66, 106, 750, 64, 44, offWhite, { bold: true });
  const challenges = [
    ["Keeping up with the game", "Ball detection must follow fast movement from imperfect video frames."],
    ["Mapping video to touch", "We had to turn a camera position into one meaningful point on a 5 × 4 grid."],
    ["Building for more than one sport", "The board needed field markings without locking the project to one layout."],
  ];
  challenges.forEach(([title, body], i) => {
    const y = 212 + i * 128;
    box(slide, 66, y, 18, 84, yellow, true);
    text(slide, title, 116, y, 530, 38, 26, offWhite, { bold: true });
    text(slide, body, 116, y + 47, 540, 56, 18, gray);
  });
  box(slide, 778, 194, 386, 360, darkGray, true);
  text(slide, "What helped", 820, 246, 300, 38, 28, yellow, { bold: true, align: "center" });
  text(slide, "A simple 20-cell contract kept the vision system, Jetson, relay matrix, and board aligned.", 830, 326, 280, 96, 22, offWhite, { align: "center" });
  slide.speakerNotes.textFrame.setText("Challenges and response, summarized from the implementation approach.");
}

// Future
{
  const slide = presentation.slides.add();
  base(slide, 6);
  text(slide, "What comes next", 66, 106, 690, 64, 44, offWhite, { bold: true });
  text(slide, "We want to turn a working prototype into a more reliable shared game-day experience.", 66, 184, 790, 54, 23, gray);
  const plans = [
    ["More reliable tracking", "Improve ball detection across broadcast angles and faster plays."],
    ["More sports", "Expand the interchangeable field inserts and tracking rules."],
    ["User testing", "Learn directly from visually impaired sports fans what feels useful during a live game."],
  ];
  plans.forEach(([title, body], i) => {
    const x = 66 + i * 386;
    box(slide, x, 325, 340, 210, i === 1 ? yellow : darkGray, true);
    text(slide, title, x + 30, 359, 278, 58, 25, i === 1 ? black : yellow, { bold: true, align: "center" });
    text(slide, body, x + 30, 433, 278, 74, 18, i === 1 ? black : offWhite, { align: "center" });
  });
  text(slide, "Buzzboard", 66, 627, 220, 28, 18, yellow, { bold: true });
  text(slide, "Thank you", 996, 627, 216, 28, 18, gray, { align: "right" });
  slide.speakerNotes.textFrame.setText("Future plans are proposed next steps, not completed features.");
}

const candidatePath = path.join(TMP_DIR, "buzzboard-draft.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
const requirements = {
  explicitTotalSlideCount: 6,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
};
const result = await finalizePresentation({
  ...requirements,
  workspaceDir,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-bullet-geometry", "--validate-heading-fit"],
  fontPolicy: { basis: "design", families: [family] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(TMP_DIR, "buzzboard-presentation-v3.validation.json"),
});
console.log(JSON.stringify({ finalPath: FINAL_PPTX, result }, null, 2));
