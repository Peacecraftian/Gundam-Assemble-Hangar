const fs = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require("playwright");

async function main() {
  const mode = process.argv[2];
  const battlefield = mode === "--battlefield";
  const specialTerrain = battlefield || mode === "--special-terrain";
  const root = path.resolve(process.env.CARD_RENDER_ROOT || path.join(__dirname, ".."));
  const tokens = await fs.realpath(path.join(root, "Tokens"));
  const decals = ["water", "impassable-terrain", "debris-fields", "minovsky-particles"];
  const names = specialTerrain
    ? decals
    : ["red-deployment-base", "blue-deployment-base", "red-garrison", "blue-garrison", "generic-upgrade"];
  const output = specialTerrain
    ? path.join(root, ".build", battlefield ? "battlefield-renders" : "terrain-renders")
    : path.join(tokens, "rendered");
  const executablePath = process.env.CARD_RENDER_CHROME;
  const browser = await chromium.launch(executablePath ? { executablePath } : { channel: "chrome" });
  try {
    const renders = new Map();
    const batches = specialTerrain ? [[names, 256, 256, 1]] : [[names, 360, 308, 2]];
    if (battlefield) batches.push([["objective", "special-objective"], 360, 308, 2]);
    for (const [assets, width, height, deviceScaleFactor] of batches) {
      const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor, javaScriptEnabled: false });
      await page.route("**/*", route => route.abort());
      for (const name of assets) {
        const source = await fs.realpath(path.join(tokens, name + ".svg"));
        if (path.dirname(source) !== tokens) throw new Error("SVG source must stay inside Tokens");
        const svg = await fs.readFile(source);
        await page.setContent(`
          <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'">
          <style>html,body{margin:0;background:transparent}img{display:block;width:${width}px;height:${height}px}</style>
          <img src="data:image/svg+xml;base64,${svg.toString("base64")}">
        `);
        await page.locator("img").evaluate(image => image.decode());
        renders.set(name, await page.screenshot({ omitBackground: true }));
      }
      await page.close();
    }
    await fs.mkdir(output, { recursive: true });
    for (const [name, png] of renders) {
      await fs.writeFile(path.join(output, name + ".png"), png);
    }
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
